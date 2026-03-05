"""
NullSec Hak5 Toolkit - CLI Entry Point

Universal command-line interface for all Hak5 devices.
"""

import click
import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from pathlib import Path

from .config import ConfigManager
from .discovery import discover_all, discover_usb_devices, discover_network_devices
from .payload import PayloadManager
from .loot import LootCollector
from .device import DeviceType

console = Console()
config = ConfigManager()

BANNER = """
╔═══════════════════════════════════════════════════╗
║     ███╗   ██╗██╗   ██╗██╗     ██╗     ███████╗  ║
║     ████╗  ██║██║   ██║██║     ██║     ██╔════╝  ║
║     ██╔██╗ ██║██║   ██║██║     ██║     ███████╗  ║
║     ██║╚██╗██║██║   ██║██║     ██║     ╚════██║  ║
║     ██║ ╚████║╚██████╔╝███████╗███████╗███████║  ║
║     ╚═╝  ╚═══╝ ╚═════╝ ╚══════╝╚══════╝╚══════╝  ║
║              HAK5 TOOLKIT v1.0.0                  ║
║         Universal Device Management Suite         ║
╚═══════════════════════════════════════════════════╝
"""


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--config-path", type=click.Path(), help="Custom config file path")
@click.pass_context
def main(ctx, verbose, config_path):
    """NullSec Hak5 Toolkit - Universal Hak5 device management."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    if config_path:
        ctx.obj["config"] = ConfigManager(Path(config_path))
    else:
        ctx.obj["config"] = config


@main.command()
def banner():
    """Display the toolkit banner."""
    console.print(BANNER, style="bold green")


# ──────────────────────────── DISCOVER ────────────────────────────


@main.command()
@click.option("--usb", "scan_usb", is_flag=True, help="Scan USB only")
@click.option("--network", "scan_net", is_flag=True, help="Scan network only")
@click.option("--serial", "scan_serial", is_flag=True, help="Scan serial only")
@click.option("--storage", "scan_storage", is_flag=True, help="Scan mass storage only")
@click.pass_context
def discover(ctx, scan_usb, scan_net, scan_serial, scan_storage):
    """Auto-discover connected Hak5 devices."""
    console.print("\n[bold cyan]🔍 Scanning for Hak5 devices...[/bold cyan]\n")

    scan_all = not any([scan_usb, scan_net, scan_serial, scan_storage])
    devices = discover_all(
        usb=scan_usb or scan_all,
        network=scan_net or scan_all,
        serial=scan_serial or scan_all,
        mass_storage=scan_storage or scan_all,
    )

    if not devices:
        console.print("[yellow]No Hak5 devices found.[/yellow]")
        console.print("Tips:")
        console.print("  • Ensure device is powered on and connected")
        console.print("  • Check USB cables and network connections")
        console.print("  • Try running with sudo for USB detection")
        return

    table = Table(title="Discovered Devices")
    table.add_column("Device", style="green", no_wrap=True)
    table.add_column("Type", style="cyan")
    table.add_column("Connection", style="yellow")
    table.add_column("Address", style="white")

    for dev in devices:
        table.add_row(
            dev.get("name", "Unknown"),
            dev.get("type", "Unknown"),
            dev.get("connection", "Unknown"),
            dev.get("address", "N/A"),
        )

    console.print(table)
    console.print(f"\n[bold green]Found {len(devices)} device(s)[/bold green]")


# ──────────────────────────── PAYLOADS ────────────────────────────


@main.group()
def payloads():
    """Manage payloads for Hak5 devices."""
    pass


@payloads.command("list")
@click.argument("device", type=click.Choice(
    ["pineapple", "bashbunny", "rubberducky", "packetsquirrel", "keycroc", "sharkjack"],
    case_sensitive=False,
))
@click.option("--category", "-c", help="Filter by category")
def payloads_list(device, category):
    """List available payloads for a device."""
    pm = PayloadManager()
    found = pm.list_payloads(device, category=category)

    if not found:
        console.print(f"[yellow]No payloads found for {device}[/yellow]")
        return

    table = Table(title=f"Payloads: {device.upper()}")
    table.add_column("Name", style="green")
    table.add_column("Category", style="cyan")
    table.add_column("Author", style="yellow")
    table.add_column("Description", style="white")

    for p in found:
        table.add_row(p.name, p.category, p.author, p.description[:60])

    console.print(table)


@payloads.command("search")
@click.argument("query")
@click.option("--device", "-d", help="Filter by device")
def payloads_search(query, device):
    """Search payloads by keyword."""
    pm = PayloadManager()
    results = pm.search(query, device_type=device)

    if not results:
        console.print(f"[yellow]No payloads matching '{query}'[/yellow]")
        return

    table = Table(title=f"Search Results: '{query}'")
    table.add_column("Name", style="green")
    table.add_column("Device", style="cyan")
    table.add_column("Category", style="yellow")

    for p in results:
        table.add_row(p.name, p.device_type, p.category)

    console.print(table)


@payloads.command("add")
@click.argument("device")
@click.argument("payload_file", type=click.Path(exists=True))
@click.option("--category", "-c", required=True, help="Payload category")
@click.option("--name", "-n", help="Payload name (defaults to filename)")
@click.option("--author", "-a", default="NullSec", help="Payload author")
@click.option("--description", "-d", default="", help="Payload description")
def payloads_add(device, payload_file, category, name, author, description):
    """Add a new payload for a device."""
    pm = PayloadManager()
    result = pm.add_payload(
        device_type=device,
        name=name or Path(payload_file).stem,
        category=category,
        payload_path=Path(payload_file),
        author=author,
        description=description,
    )

    if result:
        console.print(f"[bold green]✅ Payload added: {result.name}[/bold green]")
    else:
        console.print("[red]Failed to add payload[/red]")


# ──────────────────────────── LOOT ────────────────────────────


@main.group()
def loot():
    """Manage and collect loot from Hak5 devices."""
    pass


@loot.command("pull")
@click.argument("device", type=click.Choice(
    ["pineapple", "bashbunny", "packetsquirrel", "keycroc", "sharkjack"],
    case_sensitive=False,
))
@click.option("--output", "-o", type=click.Path(), help="Output directory")
def loot_pull(device, output):
    """Pull loot from a connected device."""
    output_dir = Path(output) if output else Path(config.get("loot.output_dir", "~/hak5-loot")).expanduser()

    lc = LootCollector(output_dir=output_dir)
    console.print(f"\n[bold cyan]📥 Pulling loot from {device.upper()}...[/bold cyan]\n")

    items = lc.collect_from_device(device)

    if not items:
        console.print("[yellow]No loot found on device.[/yellow]")
        return

    table = Table(title="Collected Loot")
    table.add_column("File", style="green")
    table.add_column("Size", style="cyan")
    table.add_column("Hash", style="yellow")

    for item in items:
        table.add_row(
            item.filename,
            f"{item.size:,} bytes",
            item.sha256[:16] + "..." if item.sha256 else "N/A",
        )

    console.print(table)
    console.print(f"\n[bold green]✅ Collected {len(items)} loot item(s)[/bold green]")


@loot.command("stats")
def loot_stats():
    """Show loot collection statistics."""
    output_dir = Path(config.get("loot.output_dir", "~/hak5-loot")).expanduser()
    lc = LootCollector(output_dir=output_dir)
    stats = lc.stats()

    panel = Panel(
        f"[cyan]Total items:[/cyan] {stats.get('total_items', 0)}\n"
        f"[cyan]Total size:[/cyan] {stats.get('total_size', 0):,} bytes\n"
        f"[cyan]Unique hashes:[/cyan] {stats.get('unique_hashes', 0)}\n"
        f"[cyan]Duplicates skipped:[/cyan] {stats.get('duplicates', 0)}\n"
        f"[cyan]Devices:[/cyan] {', '.join(stats.get('devices', []))}",
        title="Loot Statistics",
        border_style="green",
    )
    console.print(panel)


@loot.command("search")
@click.argument("query")
def loot_search(query):
    """Search collected loot by keyword."""
    output_dir = Path(config.get("loot.output_dir", "~/hak5-loot")).expanduser()
    lc = LootCollector(output_dir=output_dir)
    results = lc.search(query)

    if not results:
        console.print(f"[yellow]No loot matching '{query}'[/yellow]")
        return

    for item in results:
        console.print(f"  [green]{item.filename}[/green] ({item.size:,} bytes)")


# ──────────────────────────── CONFIG ────────────────────────────


@main.group("config")
def config_cmd():
    """View and modify toolkit configuration."""
    pass


@config_cmd.command("show")
def config_show():
    """Display current configuration."""
    import yaml as _yaml
    console.print(Panel(
        _yaml.dump(config.all, default_flow_style=False),
        title="Toolkit Configuration",
        border_style="cyan",
    ))


@config_cmd.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key, value):
    """Set a configuration value (dot notation)."""
    # Attempt type coercion
    if value.lower() in ("true", "yes"):
        value = True
    elif value.lower() in ("false", "no"):
        value = False
    elif value.isdigit():
        value = int(value)

    config.set(key, value)
    console.print(f"[bold green]✅ Set {key} = {value}[/bold green]")


@config_cmd.command("get")
@click.argument("key")
def config_get(key):
    """Get a configuration value (dot notation)."""
    val = config.get(key)
    if val is None:
        console.print(f"[yellow]Key '{key}' not found[/yellow]")
    else:
        console.print(f"[cyan]{key}[/cyan] = {val}")


@config_cmd.command("reset")
@click.confirmation_option(prompt="Reset all config to defaults?")
def config_reset():
    """Reset configuration to defaults."""
    config.reset()
    console.print("[bold green]✅ Configuration reset to defaults[/bold green]")


# ──────────────────────────── ENGAGE ────────────────────────────


@main.command()
@click.argument("device", type=click.Choice(
    ["pineapple", "bashbunny", "rubberducky", "packetsquirrel", "keycroc", "sharkjack"],
    case_sensitive=False,
))
@click.option("--interactive", "-i", is_flag=True, help="Interactive shell mode")
@click.pass_context
def engage(ctx, device, interactive):
    """Connect to and interact with a Hak5 device."""
    console.print(f"\n[bold cyan]🔌 Engaging {device.upper()}...[/bold cyan]\n")

    # Dynamic module import
    try:
        mod = __import__(f"modules.{device}", fromlist=[device])
        device_class = getattr(mod, f"{device.title().replace(' ', '')}Device", None)

        if device_class is None:
            console.print(f"[red]Module for {device} not fully implemented yet.[/red]")
            return

        dev = device_class(config.get_device_config(device))
        dev.connect()

        if interactive:
            console.print(f"[green]Connected to {device.upper()} - Interactive mode[/green]")
            console.print("[dim]Type 'help' for commands, 'exit' to disconnect[/dim]\n")
            _interactive_loop(dev)
        else:
            info = dev.get_info()
            console.print(Panel(
                f"[cyan]Device:[/cyan] {info.name}\n"
                f"[cyan]Firmware:[/cyan] {info.firmware_version}\n"
                f"[cyan]Serial:[/cyan] {info.serial_number}\n"
                f"[cyan]Connection:[/cyan] {info.connection_type}",
                title=f"{device.upper()} Info",
                border_style="green",
            ))
            dev.disconnect()

    except ImportError:
        console.print(f"[red]Module for {device} not installed.[/red]")
        console.print(f"[dim]Install with: pip install nullsec-hak5-toolkit[{device}][/dim]")
    except ConnectionError as e:
        console.print(f"[red]Connection failed: {e}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def _interactive_loop(device):
    """Run interactive device shell."""
    while True:
        try:
            cmd = console.input("[bold green]hak5>[/bold green] ").strip()
            if cmd in ("exit", "quit", "q"):
                device.disconnect()
                console.print("[dim]Disconnected.[/dim]")
                break
            elif cmd == "help":
                console.print("  [cyan]info[/cyan]       - Device information")
                console.print("  [cyan]payloads[/cyan]   - List payloads on device")
                console.print("  [cyan]loot[/cyan]       - List loot on device")
                console.print("  [cyan]backup[/cyan]     - Backup device config")
                console.print("  [cyan]exit[/cyan]       - Disconnect and exit")
            elif cmd == "info":
                info = device.get_info()
                console.print(f"  {info}")
            elif cmd == "payloads":
                for p in device.list_payloads():
                    console.print(f"  [green]{p}[/green]")
            elif cmd == "loot":
                for l in device.get_loot():
                    console.print(f"  [cyan]{l}[/cyan]")
            elif cmd == "backup":
                device.backup_config()
                console.print("  [green]✅ Config backed up[/green]")
            elif cmd:
                console.print(f"  [yellow]Unknown command: {cmd}[/yellow]")
        except KeyboardInterrupt:
            device.disconnect()
            console.print("\n[dim]Disconnected.[/dim]")
            break
        except Exception as e:
            console.print(f"  [red]Error: {e}[/red]")


# ──────────────────────────── DEPLOY ────────────────────────────


@main.command()
@click.argument("device", type=click.Choice(
    ["pineapple", "bashbunny", "rubberducky", "packetsquirrel", "keycroc", "sharkjack"],
    case_sensitive=False,
))
@click.argument("payload", type=click.Path(exists=True))
@click.option("--force", "-f", is_flag=True, help="Force deploy without confirmation")
@click.pass_context
def deploy(ctx, device, payload, force):
    """Deploy a payload to a connected device."""
    payload_path = Path(payload)
    console.print(f"\n[bold cyan]🚀 Deploying {payload_path.name} to {device.upper()}...[/bold cyan]\n")

    if not force:
        if not click.confirm(f"Deploy {payload_path.name} to {device}?"):
            console.print("[dim]Cancelled.[/dim]")
            return

    try:
        mod = __import__(f"modules.{device}", fromlist=[device])
        device_class = getattr(mod, f"{device.title().replace(' ', '')}Device")
        dev = device_class(config.get_device_config(device))
        dev.connect()
        result = dev.deploy_payload(payload_path)
        dev.disconnect()

        if result.success:
            console.print(f"[bold green]✅ Payload deployed successfully![/bold green]")
            if result.output:
                console.print(f"[dim]{result.output}[/dim]")
        else:
            console.print(f"[red]❌ Deployment failed: {result.error}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


# ──────────────────────────── STATUS ────────────────────────────


@main.command()
def status():
    """Show toolkit status and version info."""
    from . import __version__

    console.print(BANNER, style="bold green")

    table = Table(title="Toolkit Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")

    table.add_row("Version", __version__)
    table.add_row("Config", str(config.config_file))
    table.add_row("Loot Dir", config.get("loot.output_dir", "~/hak5-loot"))

    # Check for device modules
    devices = ["pineapple", "bashbunny", "rubberducky", "packetsquirrel", "keycroc", "sharkjack"]
    for dev in devices:
        try:
            __import__(f"modules.{dev}")
            table.add_row(f"Module: {dev}", "✅ Loaded")
        except ImportError:
            table.add_row(f"Module: {dev}", "⚠️  Not installed")

    console.print(table)


if __name__ == "__main__":
    main()
