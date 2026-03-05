"""
NullSec Hak5 Toolkit - Key Croc Module

Supports: Key Croc
Connection: Mass storage (YOURCROC volume) + Serial
"""

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

from core.device import (
    Hak5Device, DeviceType, ConnectionType, DeviceInfo, PayloadResult
)


CROC_MOUNT_PATTERNS = [
    "/media/KeyCroc",
    "/media/YOURCROC",
    "/media/*/KeyCroc",
    "/media/*/YOURCROC",
    "/mnt/KeyCroc",
    "/Volumes/KeyCroc",
]


class KeycrocDevice(Hak5Device):
    """
    Key Croc device interface.

    The Key Croc is a keylogger + injection tool that sits between
    keyboard and computer. Payloads trigger on keyword detection.
    """

    DEVICE_TYPE = DeviceType.KEY_CROC

    def __init__(self, config: Dict[str, Any] = None):
        config = config or {}
        self.mount_path = Path(config.get("mount", "/media/KeyCroc"))
        self._connected = False

    def connect(self) -> bool:
        """Verify the Key Croc is mounted (YOURCROC volume)."""
        if self.mount_path.exists() and self._is_croc(self.mount_path):
            self._connected = True
            return True

        for pattern in CROC_MOUNT_PATTERNS:
            from glob import glob
            for path in glob(pattern):
                p = Path(path)
                if p.exists() and self._is_croc(p):
                    self.mount_path = p
                    self._connected = True
                    return True

        raise ConnectionError(
            "Key Croc not found. Hold the button while plugging in for arming mode."
        )

    def disconnect(self) -> None:
        """Safely sync."""
        self._connected = False
        try:
            subprocess.run(["sync"], check=True)
        except Exception:
            pass

    def get_info(self) -> DeviceInfo:
        """Get Key Croc device information."""
        self._require_connection()

        version_file = self.mount_path / "version.txt"
        firmware = "unknown"
        if version_file.exists():
            firmware = version_file.read_text().strip()

        return DeviceInfo(
            name="Key Croc",
            device_type=DeviceType.KEY_CROC,
            firmware_version=firmware,
            serial_number="N/A",
            connection_type=ConnectionType.MASS_STORAGE,
            connection_address=str(self.mount_path),
            extra={
                "payloads_count": len(self._list_payload_files()),
                "keylog_size": self._get_keylog_size(),
                "free_space": self._get_free_space(),
                "matches_count": self._count_match_rules(),
            },
        )

    def deploy_payload(self, payload_path: Path) -> PayloadResult:
        """Deploy a payload to the Key Croc."""
        self._require_connection()

        try:
            payloads_dir = self.mount_path / "payloads"
            payloads_dir.mkdir(exist_ok=True)

            if payload_path.is_dir():
                dest = payloads_dir / payload_path.name
                shutil.copytree(payload_path, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(payload_path, payloads_dir / payload_path.name)

            subprocess.run(["sync"], check=True)

            return PayloadResult(
                success=True,
                output=f"Deployed {payload_path.name} to Key Croc",
                device_type=DeviceType.KEY_CROC,
            )
        except Exception as e:
            return PayloadResult(
                success=False, error=str(e), device_type=DeviceType.KEY_CROC,
            )

    def list_payloads(self) -> List[str]:
        """List payloads on the Key Croc."""
        self._require_connection()
        return self._list_payload_files()

    def get_loot(self) -> List[Dict[str, Any]]:
        """Get keylog data and other loot."""
        self._require_connection()
        loot = []

        # Keylogs
        loot_dir = self.mount_path / "loot"
        if loot_dir.exists():
            for f in loot_dir.rglob("*"):
                if f.is_file():
                    loot.append({
                        "type": "keylog" if "key" in f.name.lower() else "loot",
                        "filename": f.name,
                        "path": str(f.relative_to(self.mount_path)),
                        "size": f.stat().st_size,
                    })

        # croc_char.log - main keylog
        charlog = self.mount_path / "croc_char.log"
        if charlog.exists():
            loot.append({
                "type": "keylog",
                "filename": "croc_char.log",
                "path": "croc_char.log",
                "size": charlog.stat().st_size,
            })

        # croc_raw.log - raw USB keylog
        rawlog = self.mount_path / "croc_raw.log"
        if rawlog.exists():
            loot.append({
                "type": "raw_keylog",
                "filename": "croc_raw.log",
                "path": "croc_raw.log",
                "size": rawlog.stat().st_size,
            })

        return loot

    def backup_config(self, output_path: Path = None) -> Path:
        """Backup Key Croc configuration and keylogs."""
        self._require_connection()
        output = output_path or Path(f"keycroc_backup_{int(time.time())}")
        output.mkdir(parents=True, exist_ok=True)

        # Backup config
        config_file = self.mount_path / "config.txt"
        if config_file.exists():
            shutil.copy2(config_file, output / "config.txt")

        # Backup payloads
        payloads = self.mount_path / "payloads"
        if payloads.exists():
            shutil.copytree(payloads, output / "payloads", dirs_exist_ok=True)

        # Backup keylogs
        for logfile in ["croc_char.log", "croc_raw.log"]:
            src = self.mount_path / logfile
            if src.exists():
                shutil.copy2(src, output / logfile)

        # Backup loot
        loot_dir = self.mount_path / "loot"
        if loot_dir.exists():
            shutil.copytree(loot_dir, output / "loot", dirs_exist_ok=True)

        return output

    def restore_config(self, config_path: Path) -> bool:
        """Restore Key Croc from backup."""
        self._require_connection()
        try:
            for item in config_path.iterdir():
                dest = self.mount_path / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)
            subprocess.run(["sync"], check=True)
            return True
        except Exception:
            return False

    # ── Key Croc-specific methods ──

    def add_match_rule(self, keyword: str, payload_name: str) -> bool:
        """Add a keyword match rule that triggers a payload."""
        self._require_connection()
        match_file = self.mount_path / "payloads" / payload_name
        if not match_file.exists():
            return False

        # Add MATCH keyword to payload
        content = match_file.read_text()
        if f"MATCH {keyword}" not in content:
            with open(match_file, "r+") as f:
                old = f.read()
                f.seek(0)
                f.write(f"MATCH {keyword}\n{old}")

        return True

    def get_keylogs(self, tail: int = 100) -> str:
        """Get recent keylog entries."""
        self._require_connection()
        charlog = self.mount_path / "croc_char.log"
        if not charlog.exists():
            return ""

        lines = charlog.read_text().splitlines()
        return "\n".join(lines[-tail:])

    def clear_keylogs(self) -> bool:
        """Clear keylog files."""
        self._require_connection()
        try:
            for logfile in ["croc_char.log", "croc_raw.log"]:
                path = self.mount_path / logfile
                if path.exists():
                    path.write_text("")
            return True
        except Exception:
            return False

    def set_wifi(self, ssid: str, password: str) -> bool:
        """Configure WiFi for remote access."""
        self._require_connection()
        config_file = self.mount_path / "config.txt"
        config_lines = []

        if config_file.exists():
            config_lines = config_file.read_text().splitlines()

        # Update or add WiFi config
        updated = False
        for i, line in enumerate(config_lines):
            if line.startswith("WIFI_SSID"):
                config_lines[i] = f'WIFI_SSID "{ssid}"'
                updated = True
            elif line.startswith("WIFI_PASS"):
                config_lines[i] = f'WIFI_PASS "{password}"'
                updated = True

        if not updated:
            config_lines.append(f'WIFI_SSID "{ssid}"')
            config_lines.append(f'WIFI_PASS "{password}"')

        config_file.write_text("\n".join(config_lines) + "\n")
        return True

    # ── Internal helpers ──

    def _require_connection(self):
        if not self._connected:
            raise ConnectionError("Key Croc not connected. Call connect() first.")

    def _is_croc(self, path: Path) -> bool:
        """Check if path looks like a Key Croc."""
        indicators = ["payloads", "config.txt", "croc_char.log", "version.txt"]
        return any((path / i).exists() for i in indicators)

    def _list_payload_files(self) -> List[str]:
        """List all payload files."""
        payloads_dir = self.mount_path / "payloads"
        if not payloads_dir.exists():
            return []
        return [f.name for f in payloads_dir.rglob("*") if f.is_file()]

    def _get_keylog_size(self) -> str:
        """Get size of the keylog file."""
        charlog = self.mount_path / "croc_char.log"
        if charlog.exists():
            size = charlog.stat().st_size
            if size > 1024 * 1024:
                return f"{size / (1024 * 1024):.1f} MB"
            return f"{size / 1024:.1f} KB"
        return "0 KB"

    def _count_match_rules(self) -> int:
        """Count MATCH rules across all payloads."""
        count = 0
        payloads_dir = self.mount_path / "payloads"
        if payloads_dir.exists():
            for f in payloads_dir.rglob("*"):
                if f.is_file():
                    try:
                        content = f.read_text()
                        count += content.count("MATCH ")
                    except Exception:
                        pass
        return count

    def _get_free_space(self) -> str:
        try:
            stat = os.statvfs(str(self.mount_path))
            free = stat.f_frsize * stat.f_bavail
            return f"{free / (1024 * 1024):.1f} MB"
        except Exception:
            return "unknown"
