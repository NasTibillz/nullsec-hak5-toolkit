"""
NullSec Hak5 Toolkit - Payload Manager

Manages payload storage, deployment, and organization across devices.
"""

import os
import shutil
import json
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field


@dataclass
class PayloadMeta:
    """Metadata for a payload."""
    name: str
    category: str
    device: str
    description: str = ""
    author: str = "NullSec"
    version: str = "1.0"
    target_os: str = "any"
    tags: List[str] = field(default_factory=list)
    path: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "device": self.device,
            "description": self.description,
            "author": self.author,
            "version": self.version,
            "target_os": self.target_os,
            "tags": self.tags,
        }


class PayloadManager:
    """
    Manages the payload library for all Hak5 devices.

    Payloads are organized by device type and category:
    payloads/
    ├── pineapple/
    │   ├── recon/
    │   ├── attack/
    │   └── capture/
    ├── bashbunny/
    │   ├── credentials/
    │   ├── exfiltration/
    │   └── recon/
    └── ...
    """

    CATEGORIES = {
        "pineapple": ["recon", "attack", "capture", "stealth", "utility", "automation"],
        "bashbunny": ["credentials", "exfiltration", "recon", "remote_access", "prank", "execution"],
        "rubberducky": ["credentials", "exfiltration", "recon", "remote_access", "prank", "execution"],
        "packetsquirrel": ["mitm", "capture", "dns", "vpn", "recon", "utility"],
        "keycroc": ["credentials", "keylog", "recon", "execution", "utility"],
        "sharkjack": ["recon", "scan", "exfiltration", "utility"],
    }

    def __init__(self, payload_dir: Path = None):
        self.payload_dir = payload_dir or Path(__file__).parent.parent / "payloads"
        self._ensure_structure()

    def _ensure_structure(self):
        """Ensure the payload directory structure exists."""
        for device, categories in self.CATEGORIES.items():
            for cat in categories:
                (self.payload_dir / device / cat).mkdir(parents=True, exist_ok=True)

    def list_payloads(self, device: str = None, category: str = None) -> List[PayloadMeta]:
        """
        List available payloads, optionally filtered by device and category.
        """
        payloads = []
        devices = [device] if device else list(self.CATEGORIES.keys())

        for dev in devices:
            dev_dir = self.payload_dir / dev
            if not dev_dir.exists():
                continue

            cats = [category] if category else self.CATEGORIES.get(dev, [])
            for cat in cats:
                cat_dir = dev_dir / cat
                if not cat_dir.exists():
                    continue

                for item in sorted(cat_dir.iterdir()):
                    if item.is_dir():
                        meta = self._load_meta(item, dev, cat)
                        payloads.append(meta)
                    elif item.suffix in (".txt", ".sh", ".ps1", ".py"):
                        meta = PayloadMeta(
                            name=item.stem,
                            category=cat,
                            device=dev,
                            path=item,
                        )
                        payloads.append(meta)

        return payloads

    def _load_meta(self, payload_dir: Path, device: str, category: str) -> PayloadMeta:
        """Load payload metadata from a directory."""
        meta_file = payload_dir / "payload.json"
        if meta_file.exists():
            with open(meta_file) as f:
                data = json.load(f)
                return PayloadMeta(
                    name=data.get("name", payload_dir.name),
                    category=category,
                    device=device,
                    description=data.get("description", ""),
                    author=data.get("author", "NullSec"),
                    version=data.get("version", "1.0"),
                    target_os=data.get("target_os", "any"),
                    tags=data.get("tags", []),
                    path=payload_dir,
                )

        return PayloadMeta(
            name=payload_dir.name,
            category=category,
            device=device,
            path=payload_dir,
        )

    def add_payload(self, source: Path, device: str, category: str, name: str = None) -> PayloadMeta:
        """
        Add a payload to the library.

        Args:
            source: Path to the payload file or directory
            device: Target device type
            category: Payload category
            name: Optional custom name (defaults to source name)
        """
        if device not in self.CATEGORIES:
            raise ValueError(f"Unknown device: {device}. Valid: {list(self.CATEGORIES.keys())}")
        if category not in self.CATEGORIES[device]:
            raise ValueError(f"Unknown category '{category}' for {device}. Valid: {self.CATEGORIES[device]}")

        payload_name = name or source.stem
        dest = self.payload_dir / device / category / payload_name

        if source.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(source, dest)
        else:
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest / source.name)

        return PayloadMeta(
            name=payload_name,
            category=category,
            device=device,
            path=dest,
        )

    def remove_payload(self, device: str, category: str, name: str) -> bool:
        """Remove a payload from the library."""
        path = self.payload_dir / device / category / name
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            return True
        return False

    def search(self, query: str) -> List[PayloadMeta]:
        """Search payloads by name, description, or tags."""
        query_lower = query.lower()
        results = []
        for payload in self.list_payloads():
            if (query_lower in payload.name.lower() or
                query_lower in payload.description.lower() or
                any(query_lower in tag.lower() for tag in payload.tags)):
                results.append(payload)
        return results

    def export_payload(self, device: str, category: str, name: str, output_dir: Path) -> Path:
        """Export a payload to a directory for deployment."""
        source = self.payload_dir / device / category / name
        if not source.exists():
            raise FileNotFoundError(f"Payload not found: {device}/{category}/{name}")

        dest = output_dir / name
        if source.is_dir():
            shutil.copytree(source, dest, dirs_exist_ok=True)
        else:
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)

        return dest
