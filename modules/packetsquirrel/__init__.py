"""
NullSec Hak5 Toolkit - Packet Squirrel Module

Supports: Packet Squirrel Mark I, Mark II
Connection: SSH/Network (default: 172.16.32.1) or Serial
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


class PacketsquirrelDevice(Hak5Device):
    """
    Packet Squirrel device interface.

    Communicates via SSH. The Squirrel is an inline network implant
    that can capture, modify, and forward network traffic.
    """

    DEVICE_TYPE = DeviceType.PACKET_SQUIRREL

    def __init__(self, config: Dict[str, Any] = None):
        config = config or {}
        self.host = config.get("host", "172.16.32.1")
        self.port = config.get("ssh_port", 22)
        self.username = config.get("username", "root")
        self.password = config.get("password", "hak5squirrel")
        self.ssh = None
        self._connected = False

    def connect(self) -> bool:
        """Establish SSH connection to the Packet Squirrel."""
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
            raise ConnectionError(f"Cannot connect to Packet Squirrel: {e}")

    def disconnect(self) -> None:
        """Close the SSH connection."""
        if self.ssh:
            self.ssh.close()
        self._connected = False

    def get_info(self) -> DeviceInfo:
        """Get Packet Squirrel device information."""
        self._require_connection()

        firmware = self._exec("cat /etc/squirrel_version 2>/dev/null || echo unknown").strip()
        serial = self._exec("cat /sys/class/net/eth0/address 2>/dev/null || echo unknown").strip()
        uptime = self._exec("uptime -p 2>/dev/null || uptime").strip()

        return DeviceInfo(
            name="Packet Squirrel",
            device_type=DeviceType.PACKET_SQUIRREL,
            firmware_version=firmware,
            serial_number=serial,
            connection_type=ConnectionType.NETWORK,
            connection_address=f"{self.host}:{self.port}",
            extra={
                "uptime": uptime,
                "switch_position": self._get_switch_position(),
                "interfaces": self._get_interfaces(),
            },
        )

    def deploy_payload(self, payload_path: Path) -> PayloadResult:
        """Deploy a payload to the Packet Squirrel."""
        self._require_connection()

        try:
            sftp = self.ssh.open_sftp()

            if payload_path.is_dir():
                # Deploy entire payload directory
                remote_dir = f"/root/payloads/{payload_path.name}"
                self._exec(f"mkdir -p {remote_dir}")
                for f in payload_path.iterdir():
                    if f.is_file():
                        sftp.put(str(f), f"{remote_dir}/{f.name}")
            else:
                # Deploy single payload
                remote_path = f"/root/payloads/{payload_path.name}"
                sftp.put(str(payload_path), remote_path)
                self._exec(f"chmod +x {remote_path}")

            sftp.close()

            return PayloadResult(
                success=True,
                output=f"Deployed {payload_path.name} to Packet Squirrel",
                device_type=DeviceType.PACKET_SQUIRREL,
            )
        except Exception as e:
            return PayloadResult(
                success=False,
                error=str(e),
                device_type=DeviceType.PACKET_SQUIRREL,
            )

    def list_payloads(self) -> List[str]:
        """List payloads on the Packet Squirrel."""
        self._require_connection()
        output = self._exec("ls -1 /root/payloads/ 2>/dev/null")
        return [p.strip() for p in output.splitlines() if p.strip()]

    def get_loot(self) -> List[Dict[str, Any]]:
        """Get captured loot from the Packet Squirrel."""
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
        """Backup Packet Squirrel configuration."""
        self._require_connection()
        output = output_path or Path(f"squirrel_backup_{int(time.time())}")
        output.mkdir(parents=True, exist_ok=True)

        sftp = self.ssh.open_sftp()

        # Backup config files
        configs = ["/etc/config/", "/root/payloads/"]
        for cfg in configs:
            local_dir = output / cfg.strip("/").replace("/", "_")
            local_dir.mkdir(exist_ok=True)

            try:
                for f in sftp.listdir(cfg):
                    try:
                        sftp.get(f"{cfg}{f}", str(local_dir / f))
                    except Exception:
                        pass
            except Exception:
                pass

        sftp.close()
        return output

    def restore_config(self, config_path: Path) -> bool:
        """Restore configuration from backup."""
        self._require_connection()
        try:
            sftp = self.ssh.open_sftp()
            for local_file in config_path.rglob("*"):
                if local_file.is_file():
                    remote_name = local_file.name
                    sftp.put(str(local_file), f"/root/{remote_name}")
            sftp.close()
            return True
        except Exception:
            return False

    # ── Squirrel-specific methods ──

    def start_tcpdump(self, interface: str = "eth0", output_file: str = None,
                      filter_expr: str = None, duration: int = 60) -> str:
        """Start packet capture with tcpdump."""
        self._require_connection()
        outfile = output_file or f"/root/loot/capture_{int(time.time())}.pcap"
        cmd = f"timeout {duration} tcpdump -i {interface} -w {outfile}"
        if filter_expr:
            cmd += f" '{filter_expr}'"
        cmd += " &"
        return self._exec(cmd)

    def start_dns_spoof(self, domain: str, redirect_ip: str) -> str:
        """Start DNS spoofing."""
        self._require_connection()
        self._exec(f"echo '{redirect_ip} {domain}' >> /etc/hosts_spoof")
        return self._exec("nohup dnsspoof -f /etc/hosts_spoof &")

    def get_arp_table(self) -> List[Dict[str, str]]:
        """Get the current ARP table."""
        self._require_connection()
        output = self._exec("arp -n")
        entries = []
        for line in output.splitlines()[1:]:  # skip header
            parts = line.split()
            if len(parts) >= 3:
                entries.append({
                    "ip": parts[0],
                    "hw_type": parts[1] if len(parts) > 1 else "",
                    "mac": parts[2] if len(parts) > 2 else "",
                })
        return entries

    def enable_nat(self, wan: str = "eth0", lan: str = "eth1") -> str:
        """Enable NAT forwarding between interfaces."""
        self._require_connection()
        cmds = [
            "echo 1 > /proc/sys/net/ipv4/ip_forward",
            f"iptables -t nat -A POSTROUTING -o {wan} -j MASQUERADE",
            f"iptables -A FORWARD -i {lan} -o {wan} -j ACCEPT",
            f"iptables -A FORWARD -i {wan} -o {lan} -m state --state RELATED,ESTABLISHED -j ACCEPT",
        ]
        return self._exec(" && ".join(cmds))

    # ── Internal helpers ──

    def _require_connection(self):
        if not self._connected:
            raise ConnectionError("Not connected to Packet Squirrel. Call connect() first.")

    def _exec(self, command: str) -> str:
        """Execute a command via SSH and return output."""
        _, stdout, stderr = self.ssh.exec_command(command, timeout=30)
        return stdout.read().decode("utf-8", errors="replace")

    def _get_switch_position(self) -> str:
        """Get the current switch position."""
        return self._exec("cat /tmp/switch_position 2>/dev/null || echo unknown").strip()

    def _get_interfaces(self) -> List[str]:
        """List network interfaces."""
        output = self._exec("ls /sys/class/net/")
        return [i.strip() for i in output.split() if i.strip()]
