"""
NullSec Hak5 Toolkit - WiFi Pineapple Module

Supports: WiFi Pineapple Mark VII, WiFi Pineapple Pager
Connection: REST API over network (default: 172.16.42.1:1471)
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    import requests
except ImportError:
    requests = None

from core.device import (
    Hak5Device, DeviceType, ConnectionType, DeviceInfo, PayloadResult
)


class PineappleDevice(Hak5Device):
    """
    WiFi Pineapple device interface.

    Communicates via the Pineapple REST API. Supports MK7 and Pager variants.
    """

    DEVICE_TYPE = DeviceType.PINEAPPLE

    def __init__(self, config: Dict[str, Any] = None):
        config = config or {}
        self.host = config.get("host", "172.16.42.1")
        self.port = config.get("port", 1471)
        self.api_key = config.get("api_key", "")
        self.base_url = f"https://{self.host}:{self.port}/api"
        self.session = None
        self._connected = False
        self._verify_ssl = False

    def connect(self) -> bool:
        """Establish connection to the Pineapple API."""
        if requests is None:
            raise ImportError("requests library required: pip install requests")

        self.session = requests.Session()
        self.session.verify = self._verify_ssl
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

        try:
            resp = self._api_get("/status")
            self._connected = resp is not None
            return self._connected
        except Exception as e:
            raise ConnectionError(f"Cannot connect to Pineapple at {self.host}: {e}")

    def disconnect(self) -> None:
        """Close the API session."""
        if self.session:
            self.session.close()
        self._connected = False

    def get_info(self) -> DeviceInfo:
        """Get Pineapple device information."""
        self._require_connection()
        status = self._api_get("/status") or {}
        return DeviceInfo(
            name=f"WiFi Pineapple ({status.get('variant', 'MK7')})",
            device_type=DeviceType.PINEAPPLE,
            firmware_version=status.get("firmware", "unknown"),
            serial_number=status.get("serial", "unknown"),
            connection_type=ConnectionType.NETWORK,
            connection_address=f"{self.host}:{self.port}",
            extra={
                "mac": status.get("mac", ""),
                "uptime": status.get("uptime", ""),
                "cpu_usage": status.get("cpu", ""),
                "mem_usage": status.get("memory", ""),
            },
        )

    def deploy_payload(self, payload_path: Path) -> PayloadResult:
        """Deploy a payload module to the Pineapple."""
        self._require_connection()
        try:
            with open(payload_path) as f:
                payload_data = f.read()

            # Upload to the Pineapple modules directory
            resp = self._api_post("/modules/install", {
                "name": payload_path.stem,
                "payload": payload_data,
            })

            if resp and resp.get("success"):
                return PayloadResult(
                    success=True,
                    output=f"Deployed {payload_path.name} successfully",
                    device_type=DeviceType.PINEAPPLE,
                )
            else:
                return PayloadResult(
                    success=False,
                    error=resp.get("error", "Unknown error"),
                    device_type=DeviceType.PINEAPPLE,
                )
        except Exception as e:
            return PayloadResult(success=False, error=str(e), device_type=DeviceType.PINEAPPLE)

    def list_payloads(self) -> List[str]:
        """List installed modules/payloads on the Pineapple."""
        self._require_connection()
        resp = self._api_get("/modules") or {}
        return [m.get("name", "unknown") for m in resp.get("modules", [])]

    def get_loot(self) -> List[Dict[str, Any]]:
        """Get loot/captured data from the Pineapple."""
        self._require_connection()
        loot_items = []

        # Handshakes
        handshakes = self._api_get("/recon/handshakes") or {}
        for h in handshakes.get("handshakes", []):
            loot_items.append({"type": "handshake", "data": h})

        # Captured credentials
        creds = self._api_get("/campaigns/loot") or {}
        for c in creds.get("loot", []):
            loot_items.append({"type": "credential", "data": c})

        return loot_items

    def backup_config(self, output_path: Path = None) -> Path:
        """Backup Pineapple configuration."""
        self._require_connection()
        config_data = self._api_get("/settings/all") or {}
        output = output_path or Path(f"pineapple_backup_{int(time.time())}.json")
        with open(output, "w") as f:
            json.dump(config_data, f, indent=2)
        return output

    def restore_config(self, config_path: Path) -> bool:
        """Restore Pineapple configuration from backup."""
        self._require_connection()
        with open(config_path) as f:
            config_data = json.load(f)
        resp = self._api_post("/settings/restore", config_data)
        return resp and resp.get("success", False)

    # ── Pineapple-specific methods ──

    def start_recon(self, duration: int = 30) -> Dict[str, Any]:
        """Start a recon scan."""
        self._require_connection()
        return self._api_post("/recon/start", {"duration": duration}) or {}

    def get_recon_results(self) -> Dict[str, Any]:
        """Get recon scan results."""
        self._require_connection()
        return self._api_get("/recon/results") or {}

    def start_evil_portal(self, portal_name: str) -> bool:
        """Start an Evil Portal campaign."""
        self._require_connection()
        resp = self._api_post("/evilportal/start", {"name": portal_name})
        return resp and resp.get("success", False)

    def deauth(self, target_mac: str, channel: int = None) -> bool:
        """Send deauthentication frames."""
        self._require_connection()
        data = {"target": target_mac}
        if channel:
            data["channel"] = channel
        resp = self._api_post("/recon/deauth", data)
        return resp and resp.get("success", False)

    def get_clients(self) -> List[Dict[str, Any]]:
        """List connected/seen clients."""
        self._require_connection()
        resp = self._api_get("/recon/clients") or {}
        return resp.get("clients", [])

    def get_ssid_pool(self) -> List[str]:
        """Get the SSID pool for PineAP."""
        self._require_connection()
        resp = self._api_get("/pineap/ssids") or {}
        return resp.get("ssids", [])

    def add_ssid(self, ssid: str) -> bool:
        """Add an SSID to the PineAP pool."""
        self._require_connection()
        resp = self._api_post("/pineap/ssids/add", {"ssid": ssid})
        return resp and resp.get("success", False)

    # ── Internal helpers ──

    def _require_connection(self):
        if not self._connected:
            raise ConnectionError("Not connected to Pineapple. Call connect() first.")

    def _api_get(self, endpoint: str) -> Optional[Dict]:
        try:
            resp = self.session.get(f"{self.base_url}{endpoint}", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def _api_post(self, endpoint: str, data: dict = None) -> Optional[Dict]:
        try:
            resp = self.session.post(
                f"{self.base_url}{endpoint}",
                json=data or {},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None
