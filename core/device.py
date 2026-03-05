"""
NullSec Hak5 Toolkit - Device Abstraction Layer

Base classes and interfaces for all Hak5 device modules.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from pathlib import Path
import json
import time


class DeviceType(Enum):
    """Supported Hak5 device types."""
    PINEAPPLE = "pineapple"
    BASH_BUNNY = "bashbunny"
    RUBBER_DUCKY = "rubberducky"
    PACKET_SQUIRREL = "packetsquirrel"
    KEY_CROC = "keycroc"
    SHARK_JACK = "sharkjack"


class ConnectionType(Enum):
    """Device connection methods."""
    USB = "usb"
    NETWORK = "network"
    SERIAL = "serial"
    MASS_STORAGE = "mass_storage"


@dataclass
class DeviceInfo:
    """Device identification and status information."""
    device_type: DeviceType
    name: str
    connection: ConnectionType
    address: Optional[str] = None
    serial: Optional[str] = None
    firmware_version: Optional[str] = None
    mac_address: Optional[str] = None
    connected: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.device_type.value,
            "name": self.name,
            "connection": self.connection.value,
            "address": self.address,
            "serial": self.serial,
            "firmware": self.firmware_version,
            "mac": self.mac_address,
            "connected": self.connected,
            "metadata": self.metadata,
        }


@dataclass
class PayloadResult:
    """Result of a payload execution."""
    success: bool
    device: str
    payload_name: str
    output: str = ""
    loot: List[str] = field(default_factory=list)
    duration: float = 0.0
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


class Hak5Device(ABC):
    """
    Abstract base class for all Hak5 device modules.

    Each device module must implement these methods to integrate
    with the unified toolkit framework.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._info: Optional[DeviceInfo] = None
        self._connected = False

    @property
    @abstractmethod
    def device_type(self) -> DeviceType:
        """Return the device type enum value."""
        ...

    @property
    @abstractmethod
    def supported_connections(self) -> List[ConnectionType]:
        """Return list of supported connection types."""
        ...

    @abstractmethod
    def connect(self, address: str = None, **kwargs) -> bool:
        """
        Establish connection to the device.

        Args:
            address: IP address, serial port, or mount point
            **kwargs: Device-specific connection parameters

        Returns:
            True if connection was successful
        """
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the device."""
        ...

    @abstractmethod
    def get_info(self) -> DeviceInfo:
        """Get device information and status."""
        ...

    @abstractmethod
    def deploy_payload(self, payload_path: Path, **kwargs) -> PayloadResult:
        """
        Deploy a payload to the device.

        Args:
            payload_path: Path to the payload file/directory
            **kwargs: Device-specific deployment options

        Returns:
            PayloadResult with execution status and any loot
        """
        ...

    @abstractmethod
    def list_payloads(self) -> List[Dict[str, str]]:
        """List payloads currently on the device."""
        ...

    @abstractmethod
    def get_loot(self, output_dir: Path = None) -> List[Path]:
        """
        Retrieve loot/exfiltrated data from the device.

        Args:
            output_dir: Directory to save loot files

        Returns:
            List of paths to retrieved loot files
        """
        ...

    @abstractmethod
    def backup_config(self, output_path: Path) -> bool:
        """Backup device configuration."""
        ...

    @abstractmethod
    def restore_config(self, config_path: Path) -> bool:
        """Restore device configuration from backup."""
        ...

    @property
    def is_connected(self) -> bool:
        return self._connected

    def __repr__(self) -> str:
        status = "connected" if self._connected else "disconnected"
        return f"<{self.__class__.__name__} [{status}]>"
