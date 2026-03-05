"""
NullSec Hak5 Toolkit - Configuration Manager

Manages toolkit and device configurations.
"""

import os
import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional


DEFAULT_CONFIG = {
    "devices": {
        "pineapple": {
            "host": "172.16.42.1",
            "port": 1471,
            "api_key": "",
        },
        "bashbunny": {
            "mount": "/media/BashBunny",
        },
        "packetsquirrel": {
            "host": "172.16.32.1",
        },
        "keycroc": {
            "mount": "/media/KeyCroc",
        },
        "sharkjack": {
            "host": "172.16.24.1",
        },
    },
    "loot": {
        "output_dir": "~/hak5-loot",
        "auto_organize": True,
        "dedup": True,
    },
    "reports": {
        "template": "default",
        "output_format": "html",
        "output_dir": "~/hak5-reports",
    },
    "discovery": {
        "usb": True,
        "network": True,
        "serial": True,
        "mass_storage": True,
    },
    "logging": {
        "level": "INFO",
        "file": "~/.config/hak5-toolkit/toolkit.log",
    },
}


class ConfigManager:
    """
    Manages toolkit configuration with YAML persistence.

    Config file location: ~/.config/hak5-toolkit/config.yaml
    """

    def __init__(self, config_path: Path = None):
        self.config_dir = config_path or Path.home() / ".config" / "hak5-toolkit"
        self.config_file = self.config_dir / "config.yaml"
        self._config: Dict[str, Any] = {}
        self._load()

    def _load(self):
        """Load configuration from disk, creating defaults if needed."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if self.config_file.exists():
            with open(self.config_file) as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = DEFAULT_CONFIG.copy()
            self._save()

        # Merge defaults for any missing keys
        self._merge_defaults(self._config, DEFAULT_CONFIG)

    def _save(self):
        """Save current configuration to disk."""
        with open(self.config_file, "w") as f:
            yaml.dump(self._config, f, default_flow_style=False, sort_keys=False)

    def _merge_defaults(self, config: dict, defaults: dict):
        """Recursively merge default values into config."""
        for key, value in defaults.items():
            if key not in config:
                config[key] = value
            elif isinstance(value, dict) and isinstance(config.get(key), dict):
                self._merge_defaults(config[key], value)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a config value using dot notation.

        Example: config.get("devices.pineapple.host")
        """
        parts = key.split(".")
        current = self._config
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current

    def set(self, key: str, value: Any) -> None:
        """
        Set a config value using dot notation.

        Example: config.set("devices.pineapple.api_key", "abc123")
        """
        parts = key.split(".")
        current = self._config
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
        self._save()

    def get_device_config(self, device: str) -> Dict[str, Any]:
        """Get configuration for a specific device."""
        return self._config.get("devices", {}).get(device, {})

    def set_device_config(self, device: str, config: Dict[str, Any]) -> None:
        """Set configuration for a specific device."""
        if "devices" not in self._config:
            self._config["devices"] = {}
        self._config["devices"][device] = config
        self._save()

    @property
    def all(self) -> Dict[str, Any]:
        """Return the full configuration dictionary."""
        return self._config.copy()

    def reset(self) -> None:
        """Reset configuration to defaults."""
        self._config = DEFAULT_CONFIG.copy()
        self._save()

    def export_json(self) -> str:
        """Export config as JSON string."""
        return json.dumps(self._config, indent=2)
