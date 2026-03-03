"""VMEA CLI – Command-line interface for Voice Memo Export Automation."""

import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from vmea import __version__
from vmea.cleanup import (
    cascade_cleanup_transcript,
    cleanup_transcript,
    generate_domains,
    generate_filename_title,
    generate_key_takeaways,
)
from vmea.config import VMEAConfig, get_config_path, load_config
from vmea.discovery import diagnose_paths, discover_memos, find_source_path
from vmea.ollama import (
    is_ollama_running,
    list_models,
    preload_model,
    pull_model,
    start_ollama,
)
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

    # Format ollama_models as TOML array
    ollama_models_str = "[" + ", ".join(f'"{quote_toml_string(m)}"' for m in config.ollama_models) + "]" if config.ollama_models else "[]"

    return f'''# VMEA Configuration
# Generated on {datetime.now().isoformat()}

# Output
output_folder = "{output_folder}"
audio_output_folder = "{audio_output_folder}"
audio_export_mode = "{config.audio_export_mode.value if hasattr(config.audio_export_mode, 'value') else config.audio_export_mode}"
audio_fallback_to_source_link = {str(config.audio_fallback_to_source_link).lower()}
default_domain = "{quote_toml_string(config.default_domain)}"

# Source
source_path_override = "{source_override}"

# Transcript settings
include_native_transcript = {str(config.include_native_transcript).lower()}
transcript_source_priority = "{config.transcript_source_priority.value if hasattr(config.transcript_source_priority, 'value') else config.transcript_source_priority}"

# LLM cleanup
llm_cleanup_enabled = {str(config.llm_cleanup_enabled).lower()}
ollama_model = "{ollama_model}"
ollama_models = {ollama_models_str}  # Cascade: [transcribe, revise, polish]
ollama_host = "{ollama_host}"
ollama_timeout = {config.ollama_timeout}
cleanup_instructions_path = "{cleanup_path}"
preserve_raw_transcript = {str(config.preserve_raw_transcript).lower()}

# Reconciliation
conflict_resolution = "{config.conflict_resolution.value if hasattr(config.conflict_resolution, 'value') else config.conflict_resolution}"
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
        raise typer.Exit(1) from None
    except FileNotFoundError:
        folder_str = typer.prompt(prompt_text)
        return Path(folder_str).expanduser()


def prompt_path_with_default(prompt_text: str, default_path: Path) -> Path:
    """Prompt for a filesystem path using the configured value as the default."""
    value = typer.prompt(prompt_text, default=str(default_path.expanduser())).strip()
    return Path(value).expanduser()


def prompt_output_folder(default_path: Path | None = None) -> Path:
    """Always prompt for output folder. Audio/ subfolder is created automatically."""
    if default_path:
        default_str = str(default_path.expanduser())
    else:
        default_str = str(Path.home() / "Documents" / "Voice Memos")

    console.print("[bold]Select output folder for markdown files[/bold]")
    console.print("[dim](Audio/ subfolder will be created automatically)[/dim]")

    folder_str = typer.prompt("Output folder", default=default_str).strip()
    return Path(folder_str).expanduser()


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


def list_ollama_models_cli(host: str) -> tuple[list[str], str | None]:
    """List locally available Ollama models via CLI (fallback)."""
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


def prompt_ollama_model(saved_model: str, host: str, allow_skip: bool = False) -> str | None:
    """Show a numbered list of local Ollama models and let the user pick one.

    Args:
        saved_model: Previously configured model name (highlighted in list).
        host: Ollama server URL.
        allow_skip: If True, show a "Skip LLM" option (returns None).

    Returns:
        Selected model name, or None if the user chose to skip.
    """
    result = prompt_ollama_models(
        saved_models=[saved_model] if saved_model else [],
        host=host,
        allow_skip=allow_skip,
        max_models=1,
    )
    return result[0] if result else None


def prompt_ollama_models(
    saved_models: list[str],
    host: str,
    allow_skip: bool = False,
    max_models: int = 3,
) -> list[str]:
    """Show a numbered list of local Ollama models for cascade selection.

    Args:
        saved_models: Previously configured model names (highlighted in list).
        host: Ollama server URL.
        allow_skip: If True, show a "Skip LLM" option (returns empty list).
        max_models: Maximum number of models to select (1-3).

    Returns:
        List of selected model names, or empty list if skipped.
    """
    # Try API first, fall back to CLI
    models, error_message = list_models(host)
    if error_message:
        models, error_message = list_ollama_models_cli(host)

    if not models:
        if error_message:
            console.print(f"[yellow]Could not list Ollama models:[/yellow] {error_message}")
        else:
            console.print("[yellow]No Ollama models installed.[/yellow]")
        if allow_skip:
            return []
        # Fall back to manual entry
        default = saved_models[0] if saved_models else "llama3.2:3b"
        model = typer.prompt("Enter Ollama model name", default=default).strip()
        return [model] if model else []

    console.print("\n[bold]Available Ollama models:[/bold]")
    if allow_skip:
        console.print("  0. [dim]Skip LLM processing[/dim]")
    for i, model in enumerate(models, 1):
        marker = ""
        if model in saved_models:
            idx = saved_models.index(model) + 1
            marker = f" [green](stage {idx})[/green]"
        console.print(f"  {i}. {model}{marker}")

    if max_models > 1:
        console.print(
            f"\n[dim]Select up to {max_models} models for cascade processing.\n"
            "Enter numbers separated by commas (e.g., '1,2,3') or 'done' to finish.[/dim]"
        )

    # For single model selection, use simple prompt
    if max_models == 1:
        default_num = "1"
        if saved_models and saved_models[0] in models:
            default_num = str(models.index(saved_models[0]) + 1)

        while True:
            choice = typer.prompt("\nSelect model", default=default_num).strip()
            try:
                idx = int(choice)
                if allow_skip and idx == 0:
                    return []
                if 1 <= idx <= len(models):
                    return [models[idx - 1]]
                console.print(f"[red]Enter a number between {0 if allow_skip else 1} and {len(models)}[/red]")
            except ValueError:
                if choice in models:
                    return [choice]
                console.print("[red]Invalid selection. Enter a number or model name.[/red]")

    # Multi-model cascade selection
    selected: list[str] = []
    default_selection = ",".join(
        str(models.index(m) + 1) for m in saved_models if m in models
    ) or "1"

    while True:
        prompt_text = f"\nSelect models (1-{max_models})"
        if selected:
            prompt_text = f"\nSelected: {', '.join(selected)}. Add more or 'done'"

        choice = typer.prompt(prompt_text, default=default_selection if not selected else "done").strip().lower()

        if choice == "done" or choice == "":
            if selected:
                return selected
            if allow_skip:
                return []
            console.print("[red]Please select at least one model.[/red]")
            continue

        if allow_skip and choice == "0":
            return []

        # Parse comma-separated numbers
        try:
            indices = [int(x.strip()) for x in choice.split(",")]
            new_models = []
            for idx in indices:
                if 1 <= idx <= len(models):
                    model = models[idx - 1]
                    if model not in selected and model not in new_models:
                        new_models.append(model)
                else:
                    console.print(f"[yellow]Skipping invalid index: {idx}[/yellow]")

            selected.extend(new_models)
            if len(selected) >= max_models:
                return selected[:max_models]

            if new_models:
                console.print(f"[green]Added: {', '.join(new_models)}[/green]")
                if len(selected) < max_models:
                    console.print(f"[dim]({max_models - len(selected)} more slots available)[/dim]")
        except ValueError:
            # Try as model name
            if choice in models and choice not in selected:
                selected.append(choice)
                console.print(f"[green]Added: {choice}[/green]")
                if len(selected) >= max_models:
                    return selected
            else:
                console.print("[red]Invalid selection. Enter numbers separated by commas.[/red]")


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
        bool | None,
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
    existing_config: VMEAConfig | None = None
    if config_path.exists():
        try:
            existing_config = load_config(config_path)
        except Exception:
            existing_config = None
        if not typer.confirm("Config already exists. Overwrite?"):
            raise typer.Exit(0)

    output_folder = choose_folder("Select the folder where Markdown notes should be saved")

    audio_output_folder: Path | None = None
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

    source_override: Path | None = source_path
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
    ollama_models: list[str] = existing_config.ollama_models if existing_config else []
    ollama_host = existing_config.ollama_host if existing_config else "http://localhost:11434"
    if llm_cleanup_enabled:
        ollama_host = typer.prompt("Ollama host", default=ollama_host).strip()

        # Ask about cascade mode
        use_cascade = typer.confirm(
            "Configure cascade mode (multiple models for progressive refinement)?",
            default=len(ollama_models) > 1,
        )
        if use_cascade:
            saved_models = ollama_models if ollama_models else [ollama_model]
            ollama_models = prompt_ollama_models(
                saved_models=saved_models,
                host=ollama_host,
                allow_skip=False,
                max_models=3,
            )
            ollama_model = ollama_models[0] if ollama_models else ollama_model
        else:
            picked = prompt_ollama_models(
                saved_models=[ollama_model],
                host=ollama_host,
                allow_skip=False,
                max_models=1,
            )
            ollama_model = picked[0] if picked else ollama_model
            ollama_models = []  # Clear cascade config

    # Create config
    config = VMEAConfig(
        output_folder=output_folder,
        audio_output_folder=audio_output_folder,
        audio_export_mode="copy",
        audio_fallback_to_source_link=False,
        source_path_override=source_override,
        llm_cleanup_enabled=llm_cleanup_enabled,
        ollama_model=ollama_model,
        ollama_models=ollama_models,
        ollama_host=ollama_host,
        preserve_raw_transcript=True,
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
        if ollama_models and len(ollama_models) > 1:
            console.print(f"[green]✓[/green] Cascade mode: {' → '.join(ollama_models)}")
        else:
            console.print(f"[green]✓[/green] Ollama model: {ollama_model}")
    console.print("\n[bold]Next steps:[/bold]")
    console.print("  vmea list     – List discovered voice memos")
    console.print("  vmea export   – Export all memos")
    console.print("  vmea doctor   – Check system health")


def export_memo(
    memo_pair: Any,
    config: VMEAConfig,
    output_folder: Path,
    state: StateStore,
    conflict_mode: str,
    llm_enabled: bool,
    selected_models: list[str],
    use_cascade: bool,
    dry_run: bool = False,
    force: bool = False,
) -> str:
    """Export a single memo. Returns 'created', 'skipped', or 'failed'.

    This is the core export pipeline extracted from the export command
    so it can be called directly by watch mode and retry-failed.
    """
    try:
        # Compute hash for change detection
        source_hash = compute_source_hash(memo_pair.audio_path, memo_pair.composition_path)
        source_mtime = datetime.fromtimestamp(
            memo_pair.audio_path.stat().st_mtime, tz=UTC
        ).replace(tzinfo=None)

        # Check if we should export
        do_export, reason = should_export(
            memo_pair.memo_id, source_hash, state, conflict_mode, source_mtime
        )

        if not do_export and not force:
            console.print(f"  [dim]skip[/dim]  {memo_pair.memo_id} ({reason})")
            return "skipped"

        # Parse metadata
        metadata = parse_memo(
            memo_pair.audio_path,
            memo_pair.composition_path,
            memo_pair.memo_id,
            config.transcript_source_priority,
        )

        # Whisper transcription if no native transcript and transcribe_missing is enabled
        if not metadata.transcript and config.transcribe_missing:
            try:
                from vmea.transcribe import transcribe_if_needed

                console.print(f"  [dim]transcribing[/dim] {memo_pair.memo_id}...")
                transcript_text, transcript_source = transcribe_if_needed(
                    audio_path=memo_pair.audio_path,
                    existing_transcript=metadata.transcript,
                    model=config.whisper_model,
                    language=config.whisper_language,
                )
                if transcript_text:
                    metadata.transcript = transcript_text
                    metadata.transcript_source = transcript_source
                    console.print(f"  [green]✓[/green] Transcribed with Whisper ({transcript_source})")
            except ImportError:
                console.print(
                    f"  [yellow]warn[/yellow] {memo_pair.memo_id}: "
                    "Whisper not installed. Install with: pip install 'vmea[transcribe]'"
                )
            except Exception as exc:
                console.print(
                    f"  [yellow]warn[/yellow] {memo_pair.memo_id}: "
                    f"Whisper transcription failed ({exc})"
                )

        # LLM processing: cleanup transcript, generate key takeaways, domains, and filename title
        key_takeaways: list[str] | None = None
        llm_model = ""
        domains = ""
        sub_domains = ""
        llm_title = ""
        if metadata.transcript and llm_enabled and selected_models:
            try:
                # Use first model for auxiliary tasks, cascade for main cleanup
                primary_model = selected_models[0]
                llm_model = " \u2192 ".join(selected_models) if use_cascade else primary_model

                # Generate filename title first (needed for write_note)
                llm_title = generate_filename_title(
                    transcript=metadata.transcript,
                    model=primary_model,
                    host=config.ollama_host,
                    timeout=config.ollama_timeout,
                )

                # Clean up transcript (cascade or single model)
                if use_cascade:
                    console.print(f"  [dim]cascade cleanup[/dim] {memo_pair.memo_id[:12]}...")
                    cascade_result = cascade_cleanup_transcript(
                        transcript=metadata.transcript,
                        models=selected_models,
                        host=config.ollama_host,
                        timeout=config.ollama_timeout,
                        instructions_path=config.cleanup_instructions_path,
                        search_dir=output_folder,
                        fail_on_missing_instruction=config.fail_on_missing_instruction_file,
                    )
                    metadata.revised_transcript = cascade_result.revised_transcript
                else:
                    cleanup_result = cleanup_transcript(
                        transcript=metadata.transcript,
                        model=primary_model,
                        host=config.ollama_host,
                        timeout=config.ollama_timeout,
                        instructions_path=config.cleanup_instructions_path,
                        search_dir=output_folder,
                        fail_on_missing_instruction=config.fail_on_missing_instruction_file,
                    )
                    metadata.revised_transcript = cleanup_result.revised_transcript

                # Generate key takeaways (using primary model)
                key_takeaways = generate_key_takeaways(
                    transcript=metadata.transcript,
                    model=primary_model,
                    host=config.ollama_host,
                    timeout=config.ollama_timeout,
                )

                # Generate domain categorization (using primary model)
                domain_result = generate_domains(
                    transcript=metadata.transcript,
                    model=primary_model,
                    host=config.ollama_host,
                    timeout=config.ollama_timeout,
                )
                domains = domain_result.domain
                sub_domains = domain_result.sub_domain
            except Exception as exc:
                console.print(
                    f"  [yellow]warn[/yellow] {memo_pair.memo_id}: "
                    f"LLM processing failed ({exc})"
                )

        # Write note and optionally copy audio
        note_path, audio_path = write_note(
            metadata=metadata,
            output_folder=output_folder,
            audio_source=memo_pair.audio_path,
            key_takeaways=key_takeaways,
            llm_model=llm_model,
            domains=domains,
            sub_domains=sub_domains,
            date_format=config.filename_date_format,
            dry_run=dry_run,
            audio_export_mode=config.audio_export_mode,
            llm_title=llm_title,
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

        console.print(f"  [green]create[/green] {note_path.name}")
        return "created"

    except Exception as e:
        console.print(f"  [red]fail[/red]  {memo_pair.memo_id}: {e}")
        return "failed"


def _prepare_llm(
    config: VMEAConfig,
    interactive: bool = True,
) -> tuple[bool, list[str], bool]:
    """Prepare Ollama for LLM processing.

    Returns:
        Tuple of (llm_enabled, selected_models, use_cascade).
    """
    llm_enabled = config.llm_cleanup_enabled
    saved_models = config.ollama_models if config.ollama_models else [config.ollama_model]
    selected_models: list[str] = []
    use_cascade = False

    if not llm_enabled:
        return llm_enabled, selected_models, use_cascade

    console.print("[dim]Starting Ollama...[/dim]")
    terminal_mode = config.ollama_startup_mode == "terminal_managed"

    # Start Ollama server if not running
    if not is_ollama_running(config.ollama_host):
        success, err = start_ollama(
            host=config.ollama_host,
            terminal_mode=terminal_mode,
        )
        if not success:
            console.print(f"[red]✗[/red] Could not start Ollama: {err}")
            if interactive and not typer.confirm("Continue without LLM cleanup?", default=False):
                raise typer.Exit(1)
            return False, [], False

    console.print("[green]✓[/green] Ollama is running")

    if not interactive:
        # Non-interactive: use configured models directly
        selected_models = saved_models
        use_cascade = len(selected_models) > 1
        # Preload first model
        success, err = preload_model(selected_models[0], config.ollama_host)
        if not success:
            console.print(f"[yellow]⚠[/yellow] Could not preload model: {err}")
        return llm_enabled, selected_models, use_cascade

    # Interactive: ask if user wants cascade mode
    if typer.confirm("Use cascade mode (multiple models for progressive refinement)?", default=len(saved_models) > 1):
        picked = prompt_ollama_models(
            saved_models=saved_models,
            host=config.ollama_host,
            allow_skip=True,
            max_models=3,
        )
        if not picked:
            console.print("[dim]Skipping LLM processing.[/dim]")
            return False, [], False
        selected_models = picked
        use_cascade = len(selected_models) > 1
        console.print(f"[dim]Preloading {selected_models[0]}...[/dim]")
        success, err = preload_model(selected_models[0], config.ollama_host)
        if not success:
            console.print(f"[yellow]⚠[/yellow] Could not preload model: {err}")
        if use_cascade:
            console.print(f"[green]✓[/green] Cascade mode: {' → '.join(selected_models)}")
        else:
            console.print(f"[green]✓[/green] Ready with model: {selected_models[0]}")
    else:
        # Single model selection
        picked = prompt_ollama_models(
            saved_models=saved_models[:1],
            host=config.ollama_host,
            allow_skip=True,
            max_models=1,
        )
        if not picked:
            console.print("[dim]Skipping LLM processing.[/dim]")
            return False, [], False
        selected_models = picked
        console.print(f"[dim]Preloading {selected_models[0]}...[/dim]")
        success, err = preload_model(selected_models[0], config.ollama_host)
        if not success:
            console.print(f"[yellow]⚠[/yellow] Could not preload model: {err}")
            if not typer.confirm("Continue without LLM cleanup?", default=False):
                raise typer.Exit(1)
            return False, [], False
        console.print(f"[green]✓[/green] Ready with model: {selected_models[0]}")

    return llm_enabled, selected_models, use_cascade


@app.command()
def export(
    memo_id: Annotated[
        str | None,
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
        typer.Option("--use-config-paths", help="Use config paths without interactive prompts"),
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

    # Use config paths directly in non-interactive mode, otherwise prompt
    if use_config_paths:
        output_folder = config.output_folder.expanduser()
    else:
        output_folder = prompt_output_folder(config.output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    # State tracking
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

    console.print(f"\n[bold blue]VMEA Export[/bold blue] – {len(memos)} memo(s) found\n")

    if dry_run:
        console.print("[dim](dry run mode – no files will be written)[/dim]\n")

    # Prepare Ollama
    interactive = not use_config_paths
    llm_enabled, selected_models, use_cascade = _prepare_llm(config, interactive=interactive)

    # Process each memo
    stats = {"created": 0, "skipped": 0, "failed": 0}
    conflict_mode = "overwrite" if force else config.conflict_resolution

    for memo_pair in memos:
        result = export_memo(
            memo_pair=memo_pair,
            config=config,
            output_folder=output_folder,
            state=state,
            conflict_mode=conflict_mode,
            llm_enabled=llm_enabled,
            selected_models=selected_models,
            use_cascade=use_cascade,
            dry_run=dry_run,
            force=force,
        )
        stats[result] = stats.get(result, 0) + 1

    # Summary
    console.print(f"\n[bold]Done:[/bold] {stats.get('created', 0)} created, {stats.get('skipped', 0)} skipped, {stats.get('failed', 0)} failed")


@app.command()
def watch() -> None:
    """Watch for new voice memos and export automatically."""
    import time

    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    config = get_config_or_exit()
    source_path = find_source_path(config.source_path_override)

    if not source_path:
        console.print("[red]✗[/red] Voice Memos folder not found.")
        raise typer.Exit(1)

    console.print("[bold blue]VMEA Watch[/bold blue]")
    console.print(f"Watching: {source_path}")
    console.print("Press Ctrl+C to stop\n")

    # Prepare LLM once (non-interactive)
    llm_enabled, selected_models, use_cascade = _prepare_llm(config, interactive=False)
    output_folder = config.output_folder.expanduser()
    output_folder.mkdir(parents=True, exist_ok=True)
    state_path = output_folder / config.state_file

    class MemoHandler(FileSystemEventHandler):
        def __init__(self) -> None:
            self.pending: dict[str, float] = {}
            self.debounce_seconds = config.watch_debounce_seconds

        def on_created(self, event: Any) -> None:
            if event.is_directory or not event.src_path.endswith('.m4a'):
                return
            self.pending[event.src_path] = time.time()
            console.print(f"  [dim]detected[/dim] {Path(event.src_path).name}")

        def on_modified(self, event: Any) -> None:
            if event.is_directory or not event.src_path.endswith('.m4a'):
                return
            self.pending[event.src_path] = time.time()

        def process_pending(self) -> None:
            now = time.time()
            ready = [p for p, t in self.pending.items() if now - t > self.debounce_seconds]
            for path in ready:
                del self.pending[path]
                audio_path = Path(path)
                memo_id = audio_path.stem
                console.print(f"  [green]export[/green] {memo_id}")
                # Find the memo pair for this file
                memo_pairs = [
                    m for m in discover_memos(source_path)
                    if m.memo_id == memo_id
                ]
                if not memo_pairs:
                    console.print(f"  [red]not found[/red] {memo_id}")
                    return
                state = StateStore(path=state_path)
                result = export_memo(
                    memo_pair=memo_pairs[0],
                    config=config,
                    output_folder=output_folder,
                    state=state,
                    conflict_mode=config.conflict_resolution,
                    llm_enabled=llm_enabled,
                    selected_models=selected_models,
                    use_cascade=use_cascade,
                )
                if result == "failed":
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
        console.print("[red]✗[/red] Config not found. Run [bold]vmea init[/bold]")
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

    # Remove failed records from state
    failed_ids = []
    for record in failed:
        console.print(f"  Retrying: {record.memo_id}")
        state.remove(record.memo_id)
        failed_ids.append(record.memo_id)

    # Find source and re-export failed memos directly
    source_path = find_source_path(config.source_path_override)
    if not source_path:
        console.print("[red]\u2717[/red] Voice Memos folder not found.")
        raise typer.Exit(1)

    # Prepare LLM (non-interactive)
    llm_enabled, selected_models, use_cascade = _prepare_llm(config, interactive=False)

    memos = [m for m in discover_memos(source_path) if m.memo_id in failed_ids]
    stats = {"created": 0, "skipped": 0, "failed": 0}
    for memo_pair in memos:
        result = export_memo(
            memo_pair=memo_pair,
            config=config,
            output_folder=output_folder,
            state=state,
            conflict_mode=config.conflict_resolution,
            llm_enabled=llm_enabled,
            selected_models=selected_models,
            use_cascade=use_cascade,
        )
        stats[result] = stats.get(result, 0) + 1

    console.print(f"\n[bold]Retry done:[/bold] {stats.get('created', 0)} created, {stats.get('failed', 0)} failed")


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
    state: StateStore | None = None
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
        status = "[green]✓[/green]" if state and memo_pair.memo_id in state else "[dim]–[/dim]"

        table.add_row(memo_pair.memo_id[:12] + "...", title, duration, date_str, status)

    console.print(table)


@app.command()
def config() -> None:
    """Show current configuration."""
    config_path = get_config_path()

    if not config_path.exists():
        console.print("[red]No config found.[/red] Run [bold]vmea init[/bold] first.")
        raise typer.Exit(1)

    console.print("[bold blue]VMEA Configuration[/bold blue]")
    console.print(f"[dim]Path: {config_path}[/dim]\n")

    cfg = load_config()
    console.print("[bold]Output:[/bold]")
    console.print(f"  folder: {cfg.output_folder}")
    console.print(f"  audio_folder: {cfg.audio_output_folder or cfg.output_folder}")
    console.print(f"  audio_export_mode: {cfg.audio_export_mode}")
    console.print(f"  audio_fallback_to_source_link: {cfg.audio_fallback_to_source_link}")
    console.print("\n[bold]Source:[/bold]")
    if cfg.source_path_override:
        console.print(f"  path: {cfg.source_path_override} (override)")
    else:
        source = find_source_path()
        console.print(f"  path: {source or 'not found'} (auto-detected)")
    console.print("\n[bold]Reconciliation:[/bold]")
    console.print(f"  conflict_resolution: {cfg.conflict_resolution}")
    console.print(f"  state_file: {cfg.state_file}")
    console.print("\n[bold]LLM Cleanup:[/bold]")
    console.print(f"  enabled: {cfg.llm_cleanup_enabled}")
    if cfg.llm_cleanup_enabled:
        console.print(f"  model: {cfg.ollama_model}")
        console.print(f"  host: {cfg.ollama_host}")


# Ollama subcommand group
ollama_app = typer.Typer(help="Manage Ollama for transcript cleanup")
app.add_typer(ollama_app, name="ollama")


@ollama_app.command("status")
def ollama_status() -> None:
    """Check Ollama server status and available models."""
    config = get_config_or_exit() if get_config_path().exists() else None
    host = config.ollama_host if config else "http://localhost:11434"

    console.print("[bold blue]Ollama Status[/bold blue]\n")

    if is_ollama_running(host):
        console.print(f"[green]✓[/green] Server running at {host}")
        models, err = list_models(host)
        if err:
            console.print(f"[yellow]⚠[/yellow] Could not list models: {err}")
        elif models:
            console.print("\n[bold]Available models:[/bold]")
            for model in models:
                marker = " [dim](configured)[/dim]" if config and model == config.ollama_model else ""
                console.print(f"  - {model}{marker}")
        else:
            console.print("[yellow]⚠[/yellow] No models installed")
            console.print("  Run: ollama pull llama3.2:3b")
    else:
        console.print(f"[red]✗[/red] Server not running at {host}")
        console.print("\n[bold]To start:[/bold]")
        console.print("  vmea ollama start")
        console.print("  # or manually: ollama serve")


@ollama_app.command("start")
def ollama_start(
    terminal: Annotated[
        bool,
        typer.Option("--terminal", "-t", help="Open in Terminal.app"),
    ] = False,
) -> None:
    """Start the Ollama server."""
    config = get_config_or_exit() if get_config_path().exists() else None
    host = config.ollama_host if config else "http://localhost:11434"

    if is_ollama_running(host):
        console.print(f"[green]✓[/green] Ollama is already running at {host}")
        return

    console.print(f"Starting Ollama at {host}...")
    success, err = start_ollama(host, terminal_mode=terminal)

    if success:
        console.print("[green]✓[/green] Ollama started")
    else:
        console.print(f"[red]✗[/red] Failed to start: {err}")
        raise typer.Exit(1)


@ollama_app.command("models")
def ollama_models_cmd() -> None:
    """List available Ollama models."""
    config = get_config_or_exit() if get_config_path().exists() else None
    host = config.ollama_host if config else "http://localhost:11434"

    if not is_ollama_running(host):
        console.print(f"[red]✗[/red] Ollama not running at {host}")
        console.print("  Run: vmea ollama start")
        raise typer.Exit(1)

    models, err = list_models(host)
    if err:
        console.print(f"[red]✗[/red] {err}")
        raise typer.Exit(1)

    if not models:
        console.print("[yellow]No models installed.[/yellow]")
        console.print("\n[bold]Suggested models:[/bold]")
        console.print("  ollama pull llama3.2:3b   # Fast, good for cleanup")
        console.print("  ollama pull mistral:7b    # Higher quality")
        return

    table = Table(title="Available Ollama Models")
    table.add_column("Model", style="cyan")
    table.add_column("Status", justify="center")

    configured_model = config.ollama_model if config else None
    for model in models:
        status = "[green]configured[/green]" if model == configured_model else ""
        table.add_row(model, status)

    console.print(table)


@ollama_app.command("select")
def ollama_select() -> None:
    """Interactively select and configure an Ollama model."""
    config = get_config_or_exit()
    host = config.ollama_host

    # Start Ollama if needed
    if not is_ollama_running(host):
        console.print("Starting Ollama...")
        success, err = start_ollama(host)
        if not success:
            console.print(f"[red]✗[/red] {err}")
            raise typer.Exit(1)

    # List and select model
    models, err = list_models(host)
    if err:
        console.print(f"[red]✗[/red] {err}")
        raise typer.Exit(1)

    if not models:
        console.print("[yellow]No models installed.[/yellow]")
        if typer.confirm("Pull the recommended model (llama3.2:3b)?", default=True):
            console.print("Pulling llama3.2:3b (this may take a few minutes)...")
            success, err = pull_model("llama3.2:3b", host)
            if success:
                console.print("[green]✓[/green] Model pulled successfully")
                models = ["llama3.2:3b"]
            else:
                console.print(f"[red]✗[/red] {err}")
                raise typer.Exit(1)
        else:
            raise typer.Exit(0)

    console.print("\n[bold]Available models:[/bold]")
    for i, model in enumerate(models, 1):
        current = " [dim](current)[/dim]" if model == config.ollama_model else ""
        console.print(f"  {i}. {model}{current}")

    selected = typer.prompt(
        "\nSelect model (number or name)",
        default=config.ollama_model,
    ).strip()

    # Handle numeric selection
    try:
        idx = int(selected) - 1
        if 0 <= idx < len(models):
            selected = models[idx]
    except ValueError:
        pass

    if selected not in models:
        console.print(f"[red]✗[/red] Model '{selected}' not found")
        raise typer.Exit(1)

    # Preload the model
    console.print(f"\nLoading {selected}...")
    success, err = preload_model(selected, host)
    if not success:
        console.print(f"[yellow]⚠[/yellow] Could not preload: {err}")

    # Update config if changed
    if selected != config.ollama_model:
        config_path = get_config_path()
        content = config_path.read_text()
        # Simple replacement for ollama_model line
        import re
        new_content = re.sub(
            r'^ollama_model\s*=\s*"[^"]*"',
            f'ollama_model = "{selected}"',
            content,
            flags=re.MULTILINE,
        )
        config_path.write_text(new_content)
        console.print(f"[green]✓[/green] Config updated: ollama_model = {selected}")
    else:
        console.print(f"[green]✓[/green] Model ready: {selected}")


@ollama_app.command("pull")
def ollama_pull_cmd(
    model: Annotated[
        str,
        typer.Argument(help="Model to pull (e.g., llama3.2:3b)"),
    ],
) -> None:
    """Pull a model from the Ollama registry."""
    config = get_config_or_exit() if get_config_path().exists() else None
    host = config.ollama_host if config else "http://localhost:11434"

    console.print(f"Pulling {model}...")
    success, err = pull_model(model, host)

    if success:
        console.print(f"[green]✓[/green] Model {model} pulled successfully")
    else:
        console.print(f"[red]✗[/red] {err}")
        raise typer.Exit(1)


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
