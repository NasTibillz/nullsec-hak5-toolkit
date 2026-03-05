"""
NullSec Hak5 Toolkit - Loot Collector

Collects, organizes, and manages exfiltrated data from Hak5 devices.
"""

import os
import shutil
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field


@dataclass
class LootItem:
    """A single piece of collected loot."""
    filename: str
    device: str
    category: str
    size: int
    sha256: str
    collected_at: str
    source_path: str
    local_path: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class LootCollector:
    """
    Manages loot collection and organization from Hak5 devices.

    Loot is organized by date and device:
    loot/
    ├── 2026-03-04/
    │   ├── pineapple/
    │   │   ├── handshakes/
    │   │   ├── pcaps/
    │   │   └── probes/
    │   ├── bashbunny/
    │   │   ├── credentials/
    │   │   └── exfil/
    │   └── manifest.json
    └── latest -> 2026-03-04/
    """

    LOOT_PATHS = {
        "pineapple": {
            "network": "/root/loot",
            "mass_storage": None,
        },
        "bashbunny": {
            "mass_storage": "loot",
            "network": None,
        },
        "packetsquirrel": {
            "network": "/root/loot",
            "mass_storage": "loot",
        },
        "keycroc": {
            "mass_storage": "loot",
            "network": None,
        },
        "sharkjack": {
            "network": "/root/loot",
            "mass_storage": "loot",
        },
    }

    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path.home() / "hak5-loot"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._manifest: List[LootItem] = []
        self._load_manifest()

    def _load_manifest(self):
        """Load the global loot manifest."""
        manifest_path = self.output_dir / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path) as f:
                data = json.load(f)
                self._manifest = [LootItem(**item) for item in data]

    def _save_manifest(self):
        """Save the global loot manifest."""
        manifest_path = self.output_dir / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(
                [vars(item) for item in self._manifest],
                f, indent=2,
            )

    def collect_from_path(self, source_dir: Path, device: str,
                          category: str = "uncategorized") -> List[LootItem]:
        """
        Collect loot files from a local path (e.g., mounted device).

        Args:
            source_dir: Directory containing loot files
            device: Device type the loot came from
            category: Loot category for organization
        """
        if not source_dir.exists():
            return []

        today = datetime.now().strftime("%Y-%m-%d")
        dest_dir = self.output_dir / today / device / category
        dest_dir.mkdir(parents=True, exist_ok=True)

        collected = []
        for item in source_dir.rglob("*"):
            if item.is_file():
                # Calculate hash
                sha256 = hashlib.sha256(item.read_bytes()).hexdigest()

                # Skip duplicates
                if any(l.sha256 == sha256 for l in self._manifest):
                    continue

                # Copy to loot dir
                rel_path = item.relative_to(source_dir)
                dest_path = dest_dir / rel_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest_path)

                loot = LootItem(
                    filename=item.name,
                    device=device,
                    category=category,
                    size=item.stat().st_size,
                    sha256=sha256,
                    collected_at=datetime.now().isoformat(),
                    source_path=str(item),
                    local_path=str(dest_path),
                )
                collected.append(loot)
                self._manifest.append(loot)

        self._save_manifest()

        # Update symlink to latest
        latest = self.output_dir / "latest"
        if latest.is_symlink():
            latest.unlink()
        latest.symlink_to(today)

        return collected

    def search(self, query: str = None, device: str = None,
               category: str = None, since: str = None) -> List[LootItem]:
        """Search collected loot."""
        results = self._manifest

        if device:
            results = [l for l in results if l.device == device]
        if category:
            results = [l for l in results if l.category == category]
        if since:
            results = [l for l in results if l.collected_at >= since]
        if query:
            q = query.lower()
            results = [l for l in results
                      if q in l.filename.lower() or q in str(l.tags).lower()]

        return results

    def stats(self) -> Dict[str, Any]:
        """Get loot collection statistics."""
        total_size = sum(l.size for l in self._manifest)
        by_device = {}
        for l in self._manifest:
            by_device.setdefault(l.device, {"count": 0, "size": 0})
            by_device[l.device]["count"] += 1
            by_device[l.device]["size"] += l.size

        return {
            "total_items": len(self._manifest),
            "total_size_bytes": total_size,
            "total_size_human": self._human_size(total_size),
            "by_device": by_device,
        }

    @staticmethod
    def _human_size(size: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
