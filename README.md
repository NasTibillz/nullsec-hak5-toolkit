# NullSec Hak5 Toolkit

<p align="center">
  <img src="https://img.shields.io/badge/NullSec-Hak5_Toolkit-red?style=for-the-badge&logo=hack-the-box&logoColor=white" alt="NullSec Hak5 Toolkit">
  <img src="https://img.shields.io/badge/Python-3.8+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License MIT">
</p>

> **Universal command-line toolkit for the entire Hak5 device ecosystem**

A modular Python framework for managing, deploying payloads, and running operations across all Hak5 devices from a single interface.

## Supported Devices

| Device | Module | Status |
|--------|--------|--------|
| 🍍 WiFi Pineapple (Pager/MK7) | `pineapple` | ✅ Full Support |
| 🐰 Bash Bunny (MK1/MK2) | `bashbunny` | ✅ Full Support |
| 🦆 USB Rubber Ducky (MK1/MK2/3) | `rubberducky` | ✅ Full Support |
| 🦑 Packet Squirrel (MK1/MK2) | `packetsquirrel` | ✅ Full Support |
| 🐊 Key Croc | `keycroc` | ✅ Full Support |
| 🦈 Shark Jack | `sharkjack` | ✅ Full Support |

## Features

### Core Framework
- **Unified CLI** — Single `hak5` command for all devices
- **Device Discovery** — Auto-detect connected Hak5 devices via USB/Network
- **Payload Manager** — Deploy, list, backup payloads across devices
- **Loot Collector** — Pull and organize exfiltrated data from all devices
- **Config Manager** — Backup/restore device configurations
- **Report Generator** — Create engagement reports from loot data

### Per-Device Modules
- **Pineapple** — Recon scans, evil twin, deauth, handshake capture, PineAP management
- **Bash Bunny** — Payload deploy, switch config, LED control, extension management
- **Rubber Ducky** — DuckyScript compilation, payload encoding, deploy via USB
- **Packet Squirrel** — MITM setup, DNS spoofing, packet capture, OpenVPN tunneling
- **Key Croc** — Keylog management, match patterns, payload triggers
- **Shark Jack** — Nmap scanning, loot retrieval, payload management

## Quick Start

```bash
# Install
git clone https://github.com/bad-antics/nullsec-hak5-toolkit
cd nullsec-hak5-toolkit
pip install -e .

# Discover connected devices
hak5 discover

# List available payloads
hak5 payloads list --device pineapple

# Deploy a payload
hak5 deploy recon/wifi-survey --device pineapple --target 172.16.42.1

# Collect loot from all devices
hak5 loot pull --all

# Run a full engagement workflow
hak5 engage --profile red-team --devices pineapple,bashbunny
```

## Architecture

```
nullsec-hak5-toolkit/
├── core/               # Framework core
│   ├── cli.py          # Main CLI entry point
│   ├── device.py       # Device abstraction layer
│   ├── discovery.py    # USB/Network device discovery
│   ├── payload.py      # Payload management
│   ├── loot.py         # Loot collection & organization
│   └── config.py       # Configuration management
├── modules/            # Per-device modules
│   ├── pineapple/      # WiFi Pineapple operations
│   ├── bashbunny/      # Bash Bunny operations
│   ├── rubberducky/    # USB Rubber Ducky operations
│   ├── packetsquirrel/ # Packet Squirrel operations
│   ├── keycroc/        # Key Croc operations
│   └── sharkjack/      # Shark Jack operations
├── payloads/           # Payload library
├── docs/               # Documentation
└── tests/              # Test suite
```

## Configuration

```yaml
# ~/.config/hak5-toolkit/config.yaml
devices:
  pineapple:
    host: 172.16.42.1
    api_key: your-pineapple-api-key
  bashbunny:
    mount: /media/bashbunny
  packetsquirrel:
    host: 172.16.32.1

loot:
  output_dir: ~/hak5-loot
  auto_organize: true

reports:
  template: default
  output_format: html
```

## Contributing

We welcome contributions! See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

## Contact

- **GitHub**: [@bad-antics](https://github.com/bad-antics)
- **Email**: badxantics@gmail.com
- **Project**: Part of the [NullSec Framework](https://github.com/bad-antics/nullsec)

## License

MIT License — See [LICENSE](LICENSE) for details.
