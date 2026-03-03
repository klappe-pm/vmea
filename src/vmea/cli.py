"""VMEA CLI – Command-line interface for Voice Memo Export Automation."""

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from vmea import __version__
from vmea.cleanup import cleanup_transcript
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


def quote_toml_string(value: str) -> str:
    """Quote a string for a simple TOML assignment."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def render_config_content(config: VMEAConfig) -> str:
    """Render a minimal TOML config without external dependencies."""
    output_folder = quote_toml_string(str(config.output_folder))
    audio_output_folder = quote_toml_string(str(config.audio_output_folder)) if config.audio_output_folder else ""
    source_override = quote_toml_string(str(config.source_path_override)) if config.source_path_override else ""
    cleanup_path = (
        quote_toml_string(str(config.cleanup_instructions_path))
        if config.cleanup_instructions_path
        else ""
    )
    ollama_host = quote_toml_string(config.ollama_host)
    ollama_model = quote_toml_string(config.ollama_model)

    return f'''# VMEA Configuration
# Generated on {datetime.now().isoformat()}

# Output
output_folder = "{output_folder}"
audio_output_folder = "{audio_output_folder}"
audio_export_mode = "{config.audio_export_mode}"
audio_fallback_to_source_link = {str(config.audio_fallback_to_source_link).lower()}
default_domain = "{quote_toml_string(config.default_domain)}"

# Source
source_path_override = "{source_override}"

# Transcript settings
include_native_transcript = {str(config.include_native_transcript).lower()}
transcript_source_priority = "{config.transcript_source_priority}"

# LLM cleanup
llm_cleanup_enabled = {str(config.llm_cleanup_enabled).lower()}
ollama_model = "{ollama_model}"
ollama_host = "{ollama_host}"
ollama_timeout = {config.ollama_timeout}
cleanup_instructions_path = "{cleanup_path}"
keep_original_transcript = {str(config.keep_original_transcript).lower()}

# Reconciliation
conflict_resolution = "{config.conflict_resolution}"
state_file = "{quote_toml_string(config.state_file)}"
'''


def choose_folder(prompt_text: str) -> Path:
    """Prompt for a folder using AppleScript when available, else CLI input."""
    console.print(prompt_text)
    try:
        result = subprocess.run(
            [
                "osascript",
                "-e",
                f'set folderPath to POSIX path of (choose folder with prompt "{prompt_text}")',
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            console.print("[red]Folder selection cancelled.[/red]")
            raise typer.Exit(1)
        return Path(result.stdout.strip()).expanduser()
    except subprocess.TimeoutExpired:
        console.print("[red]Folder selection timed out.[/red]")
        raise typer.Exit(1)
    except FileNotFoundError:
        folder_str = typer.prompt(prompt_text)
        return Path(folder_str).expanduser()


def prompt_path_with_default(prompt_text: str, default_path: Path) -> Path:
    """Prompt for a filesystem path using the configured value as the default."""
    value = typer.prompt(prompt_text, default=str(default_path.expanduser())).strip()
    return Path(value).expanduser()


def resolve_export_destinations(
    config: VMEAConfig,
    *,
    use_config_paths: bool = False,
) -> tuple[Path, Path]:
    """Resolve note/audio destinations, prompting on interactive manual exports."""
    note_folder = config.output_folder.expanduser()
    audio_folder = (config.audio_output_folder or config.output_folder).expanduser()

    if use_config_paths or not sys.stdin.isatty():
        return note_folder, audio_folder

    console.print("[bold]Export Destinations[/bold]")
    note_folder = prompt_path_with_default("Markdown output folder", note_folder)
    audio_folder = prompt_path_with_default("Audio output folder", audio_folder)
    console.print(f"  notes: {note_folder}")
    console.print(f"  audio: {audio_folder}")
    return note_folder, audio_folder


def parse_ollama_model_list(output: str) -> list[str]:
    """Parse `ollama list` output into a list of model names."""
    models: list[str] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        first = stripped.split()[0]
        if first.upper() == "NAME":
            continue
        models.append(first)
    return models


def list_ollama_models(host: str) -> tuple[list[str], Optional[str]]:
    """List locally available Ollama models for the configured host."""
    if shutil.which("ollama") is None:
        return [], "Ollama CLI is not installed."

    env = os.environ.copy()
    env["OLLAMA_HOST"] = host

    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return [], "Timed out while contacting Ollama."

    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Failed to list Ollama models."
        return [], message

    return parse_ollama_model_list(result.stdout), None


def prompt_ollama_model(saved_model: str, host: str) -> str:
    """Prompt for the preferred Ollama model, showing the saved and available options."""
    models, error_message = list_ollama_models(host)

    if models:
        console.print("[bold]Available Ollama models:[/bold]")
        for model in models:
            label = " [dim](saved preference)[/dim]" if model == saved_model else ""
            console.print(f"  - {model}{label}")
        if saved_model not in models:
            console.print(
                f"[yellow]Saved preferred model not currently listed:[/yellow] {saved_model}"
            )
    elif error_message:
        console.print(f"[yellow]Could not list Ollama models:[/yellow] {error_message}")

    return typer.prompt("Preferred Ollama model", default=saved_model).strip()


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
    existing_config: Optional[VMEAConfig] = None
    if config_path.exists():
        try:
            existing_config = load_config(config_path)
        except Exception:
            existing_config = None
        if not typer.confirm("Config already exists. Overwrite?"):
            raise typer.Exit(0)

    output_folder = choose_folder("Select the folder where Markdown notes should be saved")

    audio_output_folder: Optional[Path] = None
    if typer.confirm("Store exported audio in a separate folder?", default=True):
        audio_output_folder = choose_folder("Select the folder where audio files should be saved")

    # Detect source path
    source_path = find_source_path()
    if source_path:
        console.print(f"[green]✓[/green] Found Voice Memos at: {source_path}")
        use_detected_source = typer.confirm("Use this Voice Memos source folder?", default=True)
        if not use_detected_source:
            source_path = None
    else:
        console.print("[yellow]⚠[/yellow] Voice Memos folder not found (will check again on export)")

    source_override: Optional[Path] = source_path
    if source_override is None:
        source_input = typer.prompt(
            "Enter the folder containing your Voice Memo .m4a files (leave blank to auto-detect later)",
            default="",
        ).strip()
        source_override = Path(source_input).expanduser() if source_input else None

    llm_cleanup_enabled = typer.confirm(
        "Use a local Ollama model to revise transcripts before writing notes?",
        default=existing_config.llm_cleanup_enabled if existing_config else True,
    )
    ollama_model = existing_config.ollama_model if existing_config else "llama3.2:3b"
    ollama_host = existing_config.ollama_host if existing_config else "http://localhost:11434"
    if llm_cleanup_enabled:
        ollama_host = typer.prompt("Ollama host", default=ollama_host).strip()
        ollama_model = prompt_ollama_model(ollama_model, ollama_host)

    # Create config
    config = VMEAConfig(
        output_folder=output_folder,
        audio_output_folder=audio_output_folder,
        audio_export_mode="copy",
        audio_fallback_to_source_link=False,
        source_path_override=source_override,
        llm_cleanup_enabled=llm_cleanup_enabled,
        ollama_model=ollama_model,
        ollama_host=ollama_host,
        keep_original_transcript=True,
    )
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_content = render_config_content(config)
    config_path.write_text(config_content)

    console.print(f"\n[green]✓[/green] Config saved to: {config_path}")
    console.print(f"[green]✓[/green] Output folder: {output_folder}")
    console.print(
        f"[green]✓[/green] Audio destination: "
        f"{audio_output_folder or output_folder} (copy)"
    )
    if source_override:
        console.print(f"[green]✓[/green] Source folder: {source_override}")
    if llm_cleanup_enabled:
        console.print(f"[green]✓[/green] Ollama model: {ollama_model}")
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
    use_config_paths: Annotated[
        bool,
        typer.Option("--use-config-paths", hidden=True),
    ] = False,
) -> None:
    """Export voice memos to Markdown notes."""
    config = get_config_or_exit()
    if config.audio_export_mode != "copy":
        console.print("[red]✗[/red] Audio export mode must be set to [bold]copy[/bold].")
        console.print("  Re-run [bold]vmea init[/bold] to save audio files locally.")
        raise typer.Exit(1)
    if config.audio_fallback_to_source_link:
        console.print("[red]✗[/red] Source-link fallback is disabled for normal exports.")
        console.print("  Re-run [bold]vmea init[/bold] to save audio files locally.")
        raise typer.Exit(1)

    # Find source
    source_path = find_source_path(config.source_path_override)
    if not source_path:
        console.print("[red]✗[/red] Voice Memos folder not found.")
        console.print("  Check Full Disk Access in System Settings > Privacy & Security")
        raise typer.Exit(1)

    # Initialize state store
    output_folder, audio_output_folder = resolve_export_destinations(
        config,
        use_config_paths=use_config_paths,
    )
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
            if not config.include_native_transcript:
                metadata.transcript = None

            if metadata.transcript:
                metadata.revised_transcript = metadata.transcript
                if config.llm_cleanup_enabled:
                    try:
                        metadata.revised_transcript = cleanup_transcript(
                            transcript=metadata.transcript,
                            model=config.ollama_model,
                            host=config.ollama_host,
                            timeout=config.ollama_timeout,
                            instructions_path=config.cleanup_instructions_path,
                        )
                    except Exception as exc:
                        console.print(
                            f"  [yellow]warn[/yellow] {memo_pair.memo_id}: "
                            f"Ollama cleanup failed, using original transcript ({exc})"
                        )

            # Write note and copy audio
            note_path, audio_path = write_note(
                metadata=metadata,
                output_folder=output_folder,
                audio_source=memo_pair.audio_path,
                audio_output_folder=audio_output_folder,
                audio_export_mode=config.audio_export_mode,
                audio_fallback_to_source_link=config.audio_fallback_to_source_link,
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
                    subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "vmea",
                            "export",
                            "--use-config-paths",
                            "--memo-id",
                            memo_id,
                        ],
                        check=True,
                    )
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
    subprocess.run([sys.executable, "-m", "vmea", "export", "--use-config-paths"])


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
    console.print(f"  audio_folder: {cfg.audio_output_folder or cfg.output_folder}")
    console.print(f"  audio_export_mode: {cfg.audio_export_mode}")
    console.print(f"  audio_fallback_to_source_link: {cfg.audio_fallback_to_source_link}")
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
        console.print(f"  host: {cfg.ollama_host}")


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
