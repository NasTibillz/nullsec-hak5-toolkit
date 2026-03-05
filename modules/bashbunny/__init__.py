"""
NullSec Hak5 Toolkit - Bash Bunny Module

Supports: Bash Bunny Mark I, Mark II
Connection: Mass storage (arming mode) + Serial
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


# Common Bash Bunny mount paths
BUNNY_MOUNT_PATHS = [
    "/media/BashBunny",
    "/media/bashbunny",
    "/mnt/BashBunny",
    "/run/media/*/BashBunny",
    "/Volumes/BashBunny",  # macOS
]

SWITCH_POSITIONS = ["switch1", "switch2"]


class BashbunnyDevice(Hak5Device):
    """
    Bash Bunny device interface.

    In arming mode, the Bunny mounts as mass storage.
    Payloads go in /payloads/switch1/ or /payloads/switch2/.
    """

    DEVICE_TYPE = DeviceType.BASH_BUNNY

    def __init__(self, config: Dict[str, Any] = None):
        config = config or {}
        self.mount_path = Path(config.get("mount", "/media/BashBunny"))
        self._connected = False
        self._serial_port = config.get("serial_port", "/dev/ttyACM0")

    def connect(self) -> bool:
        """Verify the Bash Bunny is mounted and accessible."""
        # Try configured mount first, then scan common paths
        if self.mount_path.exists() and self._is_bunny(self.mount_path):
            self._connected = True
            return True

        # Scan common mount points
        for pattern in BUNNY_MOUNT_PATHS:
            from glob import glob
            for path in glob(pattern):
                p = Path(path)
                if p.exists() and self._is_bunny(p):
                    self.mount_path = p
                    self._connected = True
                    return True

        raise ConnectionError(
            "Bash Bunny not found. Ensure it's in arming mode (switch position 3)."
        )

    def disconnect(self) -> None:
        """Safely unmount the Bash Bunny."""
        self._connected = False
        try:
            subprocess.run(["sync"], check=True)
        except Exception:
            pass

    def get_info(self) -> DeviceInfo:
        """Get Bash Bunny device information."""
        self._require_connection()

        version_file = self.mount_path / "version.txt"
        firmware = "unknown"
        if version_file.exists():
            firmware = version_file.read_text().strip()

        serial_file = self.mount_path / "config.txt"
        serial = "unknown"
        if serial_file.exists():
            for line in serial_file.read_text().splitlines():
                if "SERIAL" in line:
                    serial = line.split("=", 1)[-1].strip()
                    break

        return DeviceInfo(
            name="Bash Bunny",
            device_type=DeviceType.BASH_BUNNY,
            firmware_version=firmware,
            serial_number=serial,
            connection_type=ConnectionType.MASS_STORAGE,
            connection_address=str(self.mount_path),
            extra={
                "switch1_payload": self._get_active_payload("switch1"),
                "switch2_payload": self._get_active_payload("switch2"),
                "free_space": self._get_free_space(),
            },
        )

    def deploy_payload(self, payload_path: Path, switch: str = "switch1") -> PayloadResult:
        """Deploy a payload to a switch position."""
        self._require_connection()

        if switch not in SWITCH_POSITIONS:
            return PayloadResult(
                success=False,
                error=f"Invalid switch: {switch}. Use 'switch1' or 'switch2'.",
                device_type=DeviceType.BASH_BUNNY,
            )

        target_dir = self.mount_path / "payloads" / switch
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            if payload_path.is_dir():
                # Deploy entire payload directory
                for f in payload_path.iterdir():
                    shutil.copy2(f, target_dir / f.name)
            else:
                # Deploy single payload file
                shutil.copy2(payload_path, target_dir / "payload.txt")

            subprocess.run(["sync"], check=True)

            return PayloadResult(
                success=True,
                output=f"Deployed to {switch}: {payload_path.name}",
                device_type=DeviceType.BASH_BUNNY,
            )
        except Exception as e:
            return PayloadResult(
                success=False,
                error=str(e),
                device_type=DeviceType.BASH_BUNNY,
            )

    def list_payloads(self) -> List[str]:
        """List payloads in both switch positions."""
        self._require_connection()
        payloads = []

        for switch in SWITCH_POSITIONS:
            switch_dir = self.mount_path / "payloads" / switch
            if switch_dir.exists():
                for f in switch_dir.iterdir():
                    payloads.append(f"{switch}/{f.name}")

        return payloads

    def get_loot(self) -> List[Dict[str, Any]]:
        """Get loot collected by the Bash Bunny."""
        self._require_connection()
        loot_dir = self.mount_path / "loot"
        loot_items = []

        if loot_dir.exists():
            for f in loot_dir.rglob("*"):
                if f.is_file():
                    loot_items.append({
                        "filename": f.name,
                        "path": str(f.relative_to(self.mount_path)),
                        "size": f.stat().st_size,
                        "modified": f.stat().st_mtime,
                    })

        return loot_items

    def backup_config(self, output_path: Path = None) -> Path:
        """Backup Bash Bunny configuration and payloads."""
        self._require_connection()
        output = output_path or Path(f"bashbunny_backup_{int(time.time())}")
        output.mkdir(parents=True, exist_ok=True)

        # Backup payloads
        src_payloads = self.mount_path / "payloads"
        if src_payloads.exists():
            shutil.copytree(src_payloads, output / "payloads", dirs_exist_ok=True)

        # Backup config
        config_file = self.mount_path / "config.txt"
        if config_file.exists():
            shutil.copy2(config_file, output / "config.txt")

        # Backup loot
        loot_dir = self.mount_path / "loot"
        if loot_dir.exists():
            shutil.copytree(loot_dir, output / "loot", dirs_exist_ok=True)

        return output

    def restore_config(self, config_path: Path) -> bool:
        """Restore Bash Bunny configuration from backup."""
        self._require_connection()

        try:
            if (config_path / "payloads").exists():
                shutil.copytree(
                    config_path / "payloads",
                    self.mount_path / "payloads",
                    dirs_exist_ok=True,
                )

            if (config_path / "config.txt").exists():
                shutil.copy2(config_path / "config.txt", self.mount_path / "config.txt")

            subprocess.run(["sync"], check=True)
            return True
        except Exception:
            return False

    # ── Bunny-specific methods ──

    def install_tool(self, tool_name: str) -> bool:
        """Install a tool from the Bash Bunny tools repository."""
        self._require_connection()
        tools_dir = self.mount_path / "tools"
        tools_dir.mkdir(exist_ok=True)

        # Tools are typically installed via the tools_installer payload
        installer = self.mount_path / "tools_installer"
        if installer.exists():
            req_file = installer / "requirements.txt"
            with open(req_file, "a") as f:
                f.write(f"\n{tool_name}")
            return True
        return False

    def set_language(self, lang: str) -> bool:
        """Set the keyboard language for HID attacks."""
        self._require_connection()
        lang_dir = self.mount_path / "languages"
        lang_file = lang_dir / f"{lang}.json"
        return lang_file.exists()

    # ── Internal helpers ──

    def _require_connection(self):
        if not self._connected:
            raise ConnectionError("Bash Bunny not connected. Call connect() first.")

    def _is_bunny(self, path: Path) -> bool:
        """Check if a mount point looks like a Bash Bunny."""
        return (path / "payloads").exists() or (path / "version.txt").exists()

    def _get_active_payload(self, switch: str) -> str:
        """Get the active payload name for a switch position."""
        payload_file = self.mount_path / "payloads" / switch / "payload.txt"
        if payload_file.exists():
            first_line = payload_file.read_text().splitlines()[0] if payload_file.read_text() else ""
            if first_line.startswith("#"):
                return first_line.lstrip("# ").strip()
            return "payload.txt"
        return "none"

    def _get_free_space(self) -> str:
        """Get free space on the Bunny storage."""
        try:
            stat = os.statvfs(str(self.mount_path))
            free = stat.f_frsize * stat.f_bavail
            return f"{free / (1024 * 1024):.1f} MB"
        except Exception:
            return "unknown"
