"""
NullSec Hak5 Toolkit - USB Rubber Ducky Module

Supports: USB Rubber Ducky (Original + MK2)
Connection: Mass storage (via microSD reader)
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


# DuckyScript keywords for validation
DUCKYSCRIPT_KEYWORDS = {
    "REM", "DELAY", "STRING", "ENTER", "GUI", "WINDOWS", "ALT", "CTRL",
    "SHIFT", "TAB", "ESCAPE", "SPACE", "BACKSPACE", "DELETE", "HOME",
    "END", "INSERT", "PAGEUP", "PAGEDOWN", "UP", "DOWN", "LEFT", "RIGHT",
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
    "CAPSLOCK", "NUMLOCK", "SCROLLLOCK", "PRINTSCREEN", "PAUSE", "BREAK",
    "MENU", "APP", "REPEAT", "DEFINE", "VAR", "IF", "ELSE", "END_IF",
    "WHILE", "END_WHILE", "FUNCTION", "END_FUNCTION", "RETURN",
    "WAIT_FOR_BUTTON_PRESS", "BUTTON_DEF", "LED_OFF", "LED_R", "LED_G",
    "ATTACKMODE", "EXFIL", "SAVE_HOST_KEYBOARD_LOCK_STATE",
    "RESTORE_HOST_KEYBOARD_LOCK_STATE", "RANDOM_LOWERCASE_LETTER",
    "RANDOM_UPPERCASE_LETTER", "RANDOM_LETTER", "RANDOM_NUMBER",
    "RANDOM_SPECIAL_CHAR", "RANDOM_CHAR", "INJECT_MOD",
    "JITTER", "STRINGLN", "INT", "BOOL",
}


class RubberduckDevice(Hak5Device):
    """
    USB Rubber Ducky device interface.

    Payloads are DuckyScript files compiled to inject.bin.
    Deployed via microSD card reader.
    """

    DEVICE_TYPE = DeviceType.RUBBER_DUCKY

    def __init__(self, config: Dict[str, Any] = None):
        config = config or {}
        self.mount_path = Path(config.get("mount", "/media/DUCKY"))
        self.language = config.get("language", "us")
        self._connected = False

    def connect(self) -> bool:
        """Verify the Ducky SD card is mounted."""
        if self.mount_path.exists():
            self._connected = True
            return True

        # Scan for common mount patterns
        for pattern in ["/media/DUCKY", "/media/*/DUCKY", "/mnt/DUCKY", "/Volumes/DUCKY"]:
            from glob import glob
            for path in glob(pattern):
                p = Path(path)
                if p.exists():
                    self.mount_path = p
                    self._connected = True
                    return True

        raise ConnectionError(
            "Rubber Ducky SD card not found. Insert the microSD via a card reader."
        )

    def disconnect(self) -> None:
        """Safely sync and disconnect."""
        self._connected = False
        try:
            subprocess.run(["sync"], check=True)
        except Exception:
            pass

    def get_info(self) -> DeviceInfo:
        """Get Rubber Ducky device info."""
        self._require_connection()

        has_inject = (self.mount_path / "inject.bin").exists()
        has_script = any(self.mount_path.glob("*.txt"))

        return DeviceInfo(
            name="USB Rubber Ducky",
            device_type=DeviceType.RUBBER_DUCKY,
            firmware_version="MK2" if has_inject else "Original",
            serial_number="N/A",
            connection_type=ConnectionType.MASS_STORAGE,
            connection_address=str(self.mount_path),
            extra={
                "has_inject_bin": has_inject,
                "has_scripts": has_script,
                "language": self.language,
                "free_space": self._get_free_space(),
            },
        )

    def deploy_payload(self, payload_path: Path) -> PayloadResult:
        """
        Deploy a DuckyScript payload.

        Compiles .txt to inject.bin and copies to SD card.
        """
        self._require_connection()

        try:
            if payload_path.suffix == ".txt":
                # Validate DuckyScript
                if not self._validate_duckyscript(payload_path):
                    return PayloadResult(
                        success=False,
                        error="Invalid DuckyScript syntax",
                        device_type=DeviceType.RUBBER_DUCKY,
                    )

                # Try to compile with java encoder
                compiled = self._compile_duckyscript(payload_path)
                if compiled:
                    shutil.copy2(compiled, self.mount_path / "inject.bin")
                else:
                    # Copy raw script for MK2 (handles DuckyScript natively)
                    shutil.copy2(payload_path, self.mount_path / "payload.dd")

                # Also keep a copy of the source
                shutil.copy2(payload_path, self.mount_path / "payload_source.txt")

            elif payload_path.suffix == ".bin":
                shutil.copy2(payload_path, self.mount_path / "inject.bin")
            else:
                return PayloadResult(
                    success=False,
                    error=f"Unsupported file type: {payload_path.suffix}",
                    device_type=DeviceType.RUBBER_DUCKY,
                )

            subprocess.run(["sync"], check=True)
            return PayloadResult(
                success=True,
                output=f"Deployed {payload_path.name} to Rubber Ducky",
                device_type=DeviceType.RUBBER_DUCKY,
            )
        except Exception as e:
            return PayloadResult(
                success=False,
                error=str(e),
                device_type=DeviceType.RUBBER_DUCKY,
            )

    def list_payloads(self) -> List[str]:
        """List files on the Ducky SD card."""
        self._require_connection()
        payloads = []
        for f in self.mount_path.iterdir():
            if f.is_file() and f.suffix in (".txt", ".bin", ".dd"):
                payloads.append(f.name)
        return payloads

    def get_loot(self) -> List[Dict[str, Any]]:
        """Rubber Ducky doesn't typically store loot locally."""
        return []

    def backup_config(self, output_path: Path = None) -> Path:
        """Backup entire SD card contents."""
        self._require_connection()
        output = output_path or Path(f"ducky_backup_{int(time.time())}")
        output.mkdir(parents=True, exist_ok=True)

        for f in self.mount_path.iterdir():
            if f.is_file():
                shutil.copy2(f, output / f.name)

        return output

    def restore_config(self, config_path: Path) -> bool:
        """Restore SD card contents from backup."""
        self._require_connection()
        try:
            for f in config_path.iterdir():
                if f.is_file():
                    shutil.copy2(f, self.mount_path / f.name)
            subprocess.run(["sync"], check=True)
            return True
        except Exception:
            return False

    # ── Ducky-specific methods ──

    def compile_script(self, script_path: Path, output_path: Path = None) -> Optional[Path]:
        """Compile a DuckyScript .txt file to inject.bin."""
        output = output_path or script_path.with_suffix(".bin")
        return self._compile_duckyscript(script_path, output)

    def validate_script(self, script_path: Path) -> Dict[str, Any]:
        """Validate a DuckyScript file and return diagnostics."""
        issues = []
        line_count = 0

        with open(script_path) as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                line_count = i
                if not line or line.startswith("REM"):
                    continue

                first_word = line.split()[0] if line.split() else ""
                if first_word not in DUCKYSCRIPT_KEYWORDS:
                    issues.append({"line": i, "issue": f"Unknown keyword: {first_word}"})

        return {
            "valid": len(issues) == 0,
            "lines": line_count,
            "issues": issues,
        }

    # ── Internal helpers ──

    def _require_connection(self):
        if not self._connected:
            raise ConnectionError("Rubber Ducky not connected. Call connect() first.")

    def _validate_duckyscript(self, path: Path) -> bool:
        """Basic DuckyScript syntax validation."""
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("REM"):
                        continue
                    first_word = line.split()[0]
                    if first_word not in DUCKYSCRIPT_KEYWORDS:
                        return False
            return True
        except Exception:
            return False

    def _compile_duckyscript(self, script: Path, output: Path = None) -> Optional[Path]:
        """Attempt to compile DuckyScript using java encoder."""
        output = output or script.with_suffix(".bin")
        try:
            # Try hak5 encoder
            result = subprocess.run(
                ["java", "-jar", "duckencoder.jar",
                 "-i", str(script), "-o", str(output),
                 "-l", self.language],
                capture_output=True,
                timeout=30,
            )
            if result.returncode == 0 and output.exists():
                return output
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Try python-based encoder
        try:
            result = subprocess.run(
                ["ducky-encode", str(script), "-o", str(output)],
                capture_output=True,
                timeout=30,
            )
            if result.returncode == 0 and output.exists():
                return output
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return None

    def _get_free_space(self) -> str:
        try:
            stat = os.statvfs(str(self.mount_path))
            free = stat.f_frsize * stat.f_bavail
            return f"{free / (1024 * 1024):.1f} MB"
        except Exception:
            return "unknown"
