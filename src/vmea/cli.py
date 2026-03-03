"""VMEA CLI – Command-line interface for Voice Memo Export Automation."""

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from vmea import __version__
from vmea.config import VMEAConfig, get_config_path, load_config
from vmea.discovery import diagnose_paths, discover_memos, find_source_path
from vmea.parser import parse_memo
from vmea.state import StateStore, compute_source_hash, record_export, should_export
from vmea.writer import format_duration, write_note

app = typer.Typer(
    name="vmea",
    help="Voice Memo Export Automation – Export Apple Voice Memos to Markdown",
    no_args_is_help=True,
)
console = Console()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"vmea version {__version__}")
        raise typer.Exit()


def get_config_or_exit() -> VMEAConfig:
    """Load config or prompt user to run init."""
    config_path = get_config_path()
    if not config_path.exists():
        console.print("[red]No config found.[/red] Run [bold]vmea init[/bold] first.")
        raise typer.Exit(1)
    return load_config()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", "-v", callback=version_callback, is_eager=True),
    ] = None,
) -> None:
    """VMEA – Voice Memo Export Automation."""
    pass


@app.command()
def init() -> None:
    """First-run setup – select output folder and create config."""
    console.print("[bold blue]🎙️ VMEA Setup[/bold blue]\n")

    config_path = get_config_path()
    if config_path.exists():
        if not typer.confirm("Config already exists. Overwrite?"):
            raise typer.Exit(0)

    # Use macOS native folder picker
    console.print("Select your output folder (where notes will be saved)...")
    try:
        result = subprocess.run(
            [
                "osascript",
                "-e",
                'set folderPath to POSIX path of (choose folder with prompt "Select VMEA output folder")'
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            console.print("[red]Folder selection cancelled.[/red]")
            raise typer.Exit(1)
        output_folder = Path(result.stdout.strip())
    except subprocess.TimeoutExpired:
        console.print("[red]Folder selection timed out.[/red]")
        raise typer.Exit(1)
    except FileNotFoundError:
        # Fallback for non-macOS or no osascript
        output_folder_str = typer.prompt("Enter output folder path")
        output_folder = Path(output_folder_str).expanduser()

    # Detect source path
    source_path = find_source_path()
    if source_path:
        console.print(f"[green]✓[/green] Found Voice Memos at: {source_path}")
    else:
        console.print("[yellow]⚠[/yellow] Voice Memos folder not found (will check again on export)")

    # Create config
    config = VMEAConfig(output_folder=output_folder)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write config as TOML
    config_content = f'''# VMEA Configuration
# Generated on {datetime.now().isoformat()}

output_folder = "{output_folder}"
default_domain = "voice-memo"

# Transcript settings
include_native_transcript = true
transcript_source_priority = "both"

# Reconciliation
conflict_resolution = "update"
state_file = ".vmea-state.jsonl"

# LLM cleanup (optional)
llm_cleanup_enabled = false
ollama_model = "llama3.2:3b"
'''
    config_path.write_text(config_content)

    console.print(f"\n[green]✓[/green] Config saved to: {config_path}")
    console.print(f"[green]✓[/green] Output folder: {output_folder}")
    console.print("\n[bold]Next steps:[/bold]")
    console.print("  vmea list     – List discovered voice memos")
    console.print("  vmea export   – Export all memos")
    console.print("  vmea doctor   – Check system health")


@app.command()
def export(
    memo_id: Annotated[
        Optional[str],
        typer.Option("--memo-id", "-m", help="Export single memo by ID"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Show what would be exported without writing"),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force re-export even if unchanged"),
    ] = False,
) -> None:
    """Export voice memos to Markdown notes."""
    config = get_config_or_exit()

    # Find source
    source_path = find_source_path(config.source_path_override)
    if not source_path:
        console.print("[red]✗[/red] Voice Memos folder not found.")
        console.print("  Check Full Disk Access in System Settings > Privacy & Security")
        raise typer.Exit(1)

    # Initialize state store
    output_folder = config.output_folder.expanduser()
    output_folder.mkdir(parents=True, exist_ok=True)
    state_path = output_folder / config.state_file
    state = StateStore(path=state_path)

    # Discover memos
    memos = list(discover_memos(source_path))
    if memo_id:
        memos = [m for m in memos if m.memo_id == memo_id]
        if not memos:
            console.print(f"[red]✗[/red] Memo not found: {memo_id}")
            raise typer.Exit(1)

    if not memos:
        console.print("[yellow]No voice memos found.[/yellow]")
        raise typer.Exit(0)

    console.print(f"[bold blue]VMEA Export[/bold blue] – {len(memos)} memo(s) found\n")

    if dry_run:
        console.print("[dim](dry run mode – no files will be written)[/dim]\n")

    # Process each memo
    stats = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}
    conflict_mode = "overwrite" if force else config.conflict_resolution

    for memo_pair in memos:
        try:
            # Compute hash for change detection
            source_hash = compute_source_hash(memo_pair.audio_path, memo_pair.composition_path)

            # Get source file modification time for backup change detection
            source_mtime = datetime.fromtimestamp(memo_pair.audio_path.stat().st_mtime)

            # Check if we should export
            do_export, reason = should_export(
                memo_pair.memo_id, source_hash, state, conflict_mode, source_mtime
            )

            if not do_export and not force:
                console.print(f"  [dim]skip[/dim]  {memo_pair.memo_id} ({reason})")
                stats["skipped"] += 1
                continue

            # Parse metadata
            metadata = parse_memo(
                memo_pair.audio_path,
                memo_pair.composition_path,
                memo_pair.memo_id,
                config.transcript_source_priority,
            )

            # Write note and copy audio
            note_path, audio_path = write_note(
                metadata=metadata,
                output_folder=output_folder,
                audio_source=memo_pair.audio_path,
                domain=config.default_domain,
                additional_tags=config.additional_tags,
                date_format=config.filename_date_format,
                dry_run=dry_run,
            )

            # Record in state
            if not dry_run:
                record_export(
                    state=state,
                    memo_id=memo_pair.memo_id,
                    source_hash=source_hash,
                    note_path=note_path,
                    audio_path=audio_path,
                    source_modified=metadata.modified,
                    transcript_source=metadata.transcript_source,
                )

            action = "create" if reason == "new" else "update"
            color = "green" if action == "create" else "yellow"
            console.print(f"  [{color}]{action}[/{color}] {note_path.name}")
            stats["created" if reason == "new" else "updated"] += 1

        except Exception as e:
            console.print(f"  [red]fail[/red]  {memo_pair.memo_id}: {e}")
            stats["failed"] += 1

    # Summary
    console.print(f"\n[bold]Done:[/bold] {stats['created']} created, {stats['updated']} updated, {stats['skipped']} skipped, {stats['failed']} failed")


@app.command()
def watch() -> None:
    """Watch for new voice memos and export automatically."""
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
    import time

    config = get_config_or_exit()
    source_path = find_source_path(config.source_path_override)

    if not source_path:
        console.print("[red]✗[/red] Voice Memos folder not found.")
        raise typer.Exit(1)

    console.print(f"[bold blue]VMEA Watch[/bold blue]")
    console.print(f"Watching: {source_path}")
    console.print("Press Ctrl+C to stop\n")

    class MemoHandler(FileSystemEventHandler):
        def __init__(self):
            self.pending: dict[str, float] = {}
            self.debounce_seconds = config.watch_debounce_seconds

        def on_created(self, event):
            if event.is_directory or not event.src_path.endswith('.m4a'):
                return
            self.pending[event.src_path] = time.time()
            console.print(f"  [dim]detected[/dim] {Path(event.src_path).name}")

        def on_modified(self, event):
            if event.is_directory or not event.src_path.endswith('.m4a'):
                return
            self.pending[event.src_path] = time.time()

        def process_pending(self):
            now = time.time()
            ready = [p for p, t in self.pending.items() if now - t > self.debounce_seconds]
            for path in ready:
                del self.pending[path]
                memo_id = Path(path).stem
                console.print(f"  [green]export[/green] {memo_id}")
                # Trigger export for this memo
                try:
                    subprocess.run([sys.executable, "-m", "vmea", "export", "--memo-id", memo_id], check=True)
                except subprocess.CalledProcessError:
                    console.print(f"  [red]failed[/red] {memo_id}")

    handler = MemoHandler()
    observer = Observer()
    observer.schedule(handler, str(source_path), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
            handler.process_pending()
    except KeyboardInterrupt:
        observer.stop()
        console.print("\n[bold]Stopped watching.[/bold]")
    observer.join()


@app.command()
def doctor() -> None:
    """Check system health and configuration."""
    console.print("[bold blue]VMEA Doctor[/bold blue]\n")
    issues = 0

    # Check config
    config_path = get_config_path()
    if config_path.exists():
        console.print(f"[green]✓[/green] Config found: {config_path}")
        try:
            config = load_config()
        except Exception as e:
            console.print(f"[red]✗[/red] Config invalid: {e}")
            issues += 1
            config = None
    else:
        console.print(f"[red]✗[/red] Config not found. Run [bold]vmea init[/bold]")
        issues += 1
        config = None

    # Check source path
    source_path = find_source_path(config.source_path_override if config else None)
    if source_path:
        console.print(f"[green]✓[/green] Voice Memos folder: {source_path}")
        memo_count = len(list(source_path.glob("*.m4a")))
        console.print(f"  Found {memo_count} memo(s)")
    else:
        console.print("[red]✗[/red] Voice Memos folder not found")
        console.print("  [bold]Paths checked:[/bold]")
        for path, exists, count in diagnose_paths():
            status = f"[green]exists[/green] ({count} memos)" if exists else "[dim]not found[/dim]"
            console.print(f"    {path}")
            console.print(f"      {status}")
        console.print("\n  [bold yellow]To fix:[/bold yellow]")
        console.print("  1. Open the Voice Memos app on your Mac to trigger iCloud sync")
        console.print("  2. Wait for sync to complete (check Voice Memos app for recordings)")
        console.print("  3. Grant Full Disk Access in System Settings > Privacy & Security")
        issues += 1

    # Check output folder
    if config:
        output_folder = config.output_folder.expanduser()
        if output_folder.exists():
            console.print(f"[green]✓[/green] Output folder: {output_folder}")
            state_path = output_folder / config.state_file
            if state_path.exists():
                state = StateStore(path=state_path)
                console.print(f"  State: {len(state)} exported memo(s)")
        else:
            console.print(f"[yellow]⚠[/yellow] Output folder doesn't exist (will be created): {output_folder}")

    # Check Python version
    py_version = sys.version_info
    if py_version >= (3, 11):
        console.print(f"[green]✓[/green] Python {py_version.major}.{py_version.minor}.{py_version.micro}")
    else:
        console.print(f"[yellow]⚠[/yellow] Python {py_version.major}.{py_version.minor} (3.11+ recommended)")

    # Summary
    if issues == 0:
        console.print("\n[bold green]All checks passed![/bold green]")
    else:
        console.print(f"\n[bold red]{issues} issue(s) found[/bold red]")
        raise typer.Exit(1)


@app.command("retry-failed")
def retry_failed() -> None:
    """Retry previously failed exports."""
    config = get_config_or_exit()
    output_folder = config.output_folder.expanduser()
    state_path = output_folder / config.state_file

    if not state_path.exists():
        console.print("[yellow]No state file found. Nothing to retry.[/yellow]")
        raise typer.Exit(0)

    state = StateStore(path=state_path)
    failed = [s for s in state.all() if s.error]

    if not failed:
        console.print("[green]No failed exports to retry.[/green]")
        raise typer.Exit(0)

    console.print(f"[bold blue]Retrying {len(failed)} failed export(s)...[/bold blue]\n")

    for record in failed:
        console.print(f"  Retrying: {record.memo_id}")
        # Remove from state and re-export
        state.remove(record.memo_id)

    # Trigger export
    subprocess.run([sys.executable, "-m", "vmea", "export"])


@app.command("list")
def list_memos() -> None:
    """List discovered voice memos."""
    config_path = get_config_path()
    config = load_config() if config_path.exists() else None

    source_path = find_source_path(config.source_path_override if config else None)
    if not source_path:
        console.print("[red]✗[/red] Voice Memos folder not found.")
        console.print("  Check Full Disk Access in System Settings > Privacy & Security")
        raise typer.Exit(1)

    memos = list(discover_memos(source_path))

    if not memos:
        console.print("[yellow]No voice memos found.[/yellow]")
        raise typer.Exit(0)

    # Load state to show export status
    state: Optional[StateStore] = None
    if config:
        state_path = config.output_folder.expanduser() / config.state_file
        if state_path.exists():
            state = StateStore(path=state_path)

    table = Table(title=f"Voice Memos ({len(memos)})")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="white")
    table.add_column("Duration", justify="right")
    table.add_column("Date", style="dim")
    table.add_column("Status", justify="center")

    for memo_pair in sorted(memos, key=lambda m: m.audio_path.stat().st_mtime, reverse=True):
        # Parse to get metadata
        metadata = parse_memo(
            memo_pair.audio_path,
            memo_pair.composition_path,
            memo_pair.memo_id,
        )

        title = metadata.title or metadata.custom_label or "[untitled]"
        if len(title) > 40:
            title = title[:37] + "..."

        duration = format_duration(metadata.duration_seconds)
        date_str = metadata.created.strftime("%Y-%m-%d") if metadata.created else "unknown"

        # Check if exported
        if state and memo_pair.memo_id in state:
            status = "[green]✓[/green]"
        else:
            status = "[dim]–[/dim]"

        table.add_row(memo_pair.memo_id[:12] + "...", title, duration, date_str, status)

    console.print(table)


@app.command()
def config() -> None:
    """Show current configuration."""
    config_path = get_config_path()

    if not config_path.exists():
        console.print("[red]No config found.[/red] Run [bold]vmea init[/bold] first.")
        raise typer.Exit(1)

    console.print(f"[bold blue]VMEA Configuration[/bold blue]")
    console.print(f"[dim]Path: {config_path}[/dim]\n")

    cfg = load_config()
    console.print(f"[bold]Output:[/bold]")
    console.print(f"  folder: {cfg.output_folder}")
    console.print(f"  structure: {cfg.output_structure}")
    console.print(f"\n[bold]Source:[/bold]")
    if cfg.source_path_override:
        console.print(f"  path: {cfg.source_path_override} (override)")
    else:
        source = find_source_path()
        console.print(f"  path: {source or 'not found'} (auto-detected)")
    console.print(f"\n[bold]Reconciliation:[/bold]")
    console.print(f"  conflict_resolution: {cfg.conflict_resolution}")
    console.print(f"  state_file: {cfg.state_file}")
    console.print(f"\n[bold]LLM Cleanup:[/bold]")
    console.print(f"  enabled: {cfg.llm_cleanup_enabled}")
    if cfg.llm_cleanup_enabled:
        console.print(f"  model: {cfg.ollama_model}")


# Daemon subcommand group
daemon_app = typer.Typer(help="Manage background daemon")
app.add_typer(daemon_app, name="daemon")

LAUNCHD_PLIST_PATH = Path("~/Library/LaunchAgents/dev.vmea.agent.plist").expanduser()
LAUNCHD_PLIST_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>dev.vmea.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>-m</string>
        <string>vmea</string>
        <string>watch</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{log_path}/vmea-stdout.log</string>
    <key>StandardErrorPath</key>
    <string>{log_path}/vmea-stderr.log</string>
    <key>WorkingDirectory</key>
    <string>{home}</string>
</dict>
</plist>
'''


@daemon_app.command("install")
def daemon_install() -> None:
    """Install launchd daemon for background processing."""
    if LAUNCHD_PLIST_PATH.exists():
        console.print("[yellow]Daemon already installed.[/yellow] Use 'vmea daemon uninstall' first.")
        raise typer.Exit(1)

    # Create log directory
    log_path = Path("~/.local/share/vmea").expanduser()
    log_path.mkdir(parents=True, exist_ok=True)

    # Generate plist
    plist_content = LAUNCHD_PLIST_TEMPLATE.format(
        python_path=sys.executable,
        log_path=log_path,
        home=Path.home(),
    )

    LAUNCHD_PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    LAUNCHD_PLIST_PATH.write_text(plist_content)

    # Load the daemon
    result = subprocess.run(["launchctl", "load", str(LAUNCHD_PLIST_PATH)], capture_output=True)
    if result.returncode == 0:
        console.print("[green]✓[/green] Daemon installed and started")
        console.print(f"  Plist: {LAUNCHD_PLIST_PATH}")
        console.print(f"  Logs: {log_path}")
    else:
        console.print(f"[red]✗[/red] Failed to load daemon: {result.stderr.decode()}")
        raise typer.Exit(1)


@daemon_app.command("uninstall")
def daemon_uninstall() -> None:
    """Remove launchd daemon."""
    if not LAUNCHD_PLIST_PATH.exists():
        console.print("[yellow]Daemon not installed.[/yellow]")
        raise typer.Exit(0)

    # Unload the daemon
    subprocess.run(["launchctl", "unload", str(LAUNCHD_PLIST_PATH)], capture_output=True)

    # Remove plist
    LAUNCHD_PLIST_PATH.unlink()
    console.print("[green]✓[/green] Daemon uninstalled")


@daemon_app.command("status")
def daemon_status() -> None:
    """Check daemon status."""
    if not LAUNCHD_PLIST_PATH.exists():
        console.print("[dim]Daemon not installed[/dim]")
        raise typer.Exit(0)

    result = subprocess.run(
        ["launchctl", "list", "dev.vmea.agent"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        console.print("[green]✓[/green] Daemon is running")
        # Parse PID from output
        for line in result.stdout.strip().split("\n"):
            if "PID" in line or line.strip().startswith("-") or line.strip()[0].isdigit():
                console.print(f"  {line.strip()}")
    else:
        console.print("[yellow]⚠[/yellow] Daemon installed but not running")
        console.print("  Try: vmea daemon uninstall && vmea daemon install")


if __name__ == "__main__":
    app()
