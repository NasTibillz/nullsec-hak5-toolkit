"""
NullSec Hak5 Toolkit - Device Discovery

Auto-detect connected Hak5 devices via USB descriptors and network scanning.
"""

import subprocess
import re
import os
import json
from typing import List, Optional, Dict
from pathlib import Path

from .device import DeviceType, ConnectionType, DeviceInfo


# Known Hak5 USB VID/PID combinations
HAK5_USB_DEVICES = {
    # WiFi Pineapple
    ("0x2717", "0xff08"): (DeviceType.PINEAPPLE, "WiFi Pineapple MK7"),
    ("0x2717", "0xff09"): (DeviceType.PINEAPPLE, "WiFi Pineapple Pager"),
    # Bash Bunny
    ("0xf000", "0xfff0"): (DeviceType.BASH_BUNNY, "Bash Bunny MK1"),
    ("0xf000", "0xfff1"): (DeviceType.BASH_BUNNY, "Bash Bunny MK2"),
    # USB Rubber Ducky
    ("0x05ac", "0x021e"): (DeviceType.RUBBER_DUCKY, "USB Rubber Ducky"),  # Apple keyboard spoof
    ("0x0f0d", "0x0026"): (DeviceType.RUBBER_DUCKY, "USB Rubber Ducky"),  # Hori gamepad spoof
    # Packet Squirrel
    ("0x2717", "0xff0a"): (DeviceType.PACKET_SQUIRREL, "Packet Squirrel MK1"),
    ("0x2717", "0xff0b"): (DeviceType.PACKET_SQUIRREL, "Packet Squirrel MK2"),
    # Key Croc
    ("0x2717", "0xff0c"): (DeviceType.KEY_CROC, "Key Croc"),
    # Shark Jack
    ("0x2717", "0xff0d"): (DeviceType.SHARK_JACK, "Shark Jack"),
}

# Known Hak5 network signatures
HAK5_NETWORK_DEFAULTS = {
    "172.16.42.1": (DeviceType.PINEAPPLE, "WiFi Pineapple"),
    "172.16.32.1": (DeviceType.PACKET_SQUIRREL, "Packet Squirrel"),
    "172.16.24.1": (DeviceType.SHARK_JACK, "Shark Jack"),
}

# Mass storage labels
HAK5_VOLUME_LABELS = {
    "BashBunny": (DeviceType.BASH_BUNNY, "Bash Bunny"),
    "KeyCroc": (DeviceType.KEY_CROC, "Key Croc"),
}


def discover_usb_devices() -> List[DeviceInfo]:
    """Discover Hak5 devices connected via USB."""
    devices = []

    try:
        result = subprocess.run(
            ["lsusb"], capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return devices

        for line in result.stdout.strip().split("\n"):
            match = re.search(r"ID\s+([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\s+(.*)", line)
            if match:
                vid = f"0x{match.group(1)}"
                pid = f"0x{match.group(2)}"
                desc = match.group(3)

                key = (vid, pid)
                if key in HAK5_USB_DEVICES:
                    dev_type, name = HAK5_USB_DEVICES[key]
                    devices.append(DeviceInfo(
                        device_type=dev_type,
                        name=name,
                        connection=ConnectionType.USB,
                        serial=f"{vid}:{pid}",
                        connected=True,
                        metadata={"usb_desc": desc},
                    ))

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return devices


def discover_network_devices() -> List[DeviceInfo]:
    """Discover Hak5 devices on known network addresses."""
    devices = []

    for ip, (dev_type, name) in HAK5_NETWORK_DEFAULTS.items():
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "1", ip],
                capture_output=True, timeout=3,
            )
            if result.returncode == 0:
                devices.append(DeviceInfo(
                    device_type=dev_type,
                    name=name,
                    connection=ConnectionType.NETWORK,
                    address=ip,
                    connected=True,
                ))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    return devices


def discover_mass_storage_devices() -> List[DeviceInfo]:
    """Discover Hak5 devices in mass storage mode."""
    devices = []

    # Check common mount points
    mount_dirs = ["/media", "/mnt", "/run/media"]
    if os.environ.get("USER"):
        mount_dirs.append(f"/media/{os.environ['USER']}")
        mount_dirs.append(f"/run/media/{os.environ['USER']}")

    for mount_base in mount_dirs:
        if not os.path.isdir(mount_base):
            continue
        for entry in os.listdir(mount_base):
            if entry in HAK5_VOLUME_LABELS:
                dev_type, name = HAK5_VOLUME_LABELS[entry]
                mount_path = os.path.join(mount_base, entry)
                devices.append(DeviceInfo(
                    device_type=dev_type,
                    name=name,
                    connection=ConnectionType.MASS_STORAGE,
                    address=mount_path,
                    connected=True,
                    metadata={"mount_point": mount_path},
                ))

    return devices


def discover_serial_devices() -> List[DeviceInfo]:
    """Discover Hak5 devices on serial ports."""
    devices = []
    serial_patterns = ["/dev/ttyUSB*", "/dev/ttyACM*"]

    for pattern in serial_patterns:
        import glob
        for port in glob.glob(pattern):
            # Check if it's a known Hak5 serial device
            try:
                result = subprocess.run(
                    ["udevadm", "info", "-q", "property", port],
                    capture_output=True, text=True, timeout=3,
                )
                props = dict(
                    line.split("=", 1)
                    for line in result.stdout.strip().split("\n")
                    if "=" in line
                )
                vid = props.get("ID_VENDOR_ID", "")
                pid = props.get("ID_MODEL_ID", "")
                key = (f"0x{vid}", f"0x{pid}")
                if key in HAK5_USB_DEVICES:
                    dev_type, name = HAK5_USB_DEVICES[key]
                    devices.append(DeviceInfo(
                        device_type=dev_type,
                        name=name,
                        connection=ConnectionType.SERIAL,
                        address=port,
                        connected=True,
                    ))
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue

    return devices


def discover_all() -> List[DeviceInfo]:
    """
    Run all discovery methods and return a deduplicated list of found devices.
    """
    all_devices = []
    all_devices.extend(discover_usb_devices())
    all_devices.extend(discover_network_devices())
    all_devices.extend(discover_mass_storage_devices())
    all_devices.extend(discover_serial_devices())

    # Deduplicate by (device_type, serial/address)
    seen = set()
    unique = []
    for dev in all_devices:
        key = (dev.device_type, dev.serial or dev.address)
        if key not in seen:
            seen.add(key)
            unique.append(dev)

    return unique
