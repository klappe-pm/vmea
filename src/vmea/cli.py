"""VMEA CLI – Command-line interface for Voice Memo Export Automation."""

from typing import Annotated, Optional

import typer
from rich.console import Console

from vmea import __version__

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
    console.print("[bold blue]VMEA Setup[/bold blue]")
    console.print("TODO: Implement first-run setup with folder picker")
    raise typer.Exit(1)


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
) -> None:
    """Export voice memos to Markdown notes."""
    console.print("[bold blue]VMEA Export[/bold blue]")
    if memo_id:
        console.print(f"TODO: Export memo {memo_id}")
    else:
        console.print("TODO: Export all memos")
    if dry_run:
        console.print("[dim](dry run mode)[/dim]")
    raise typer.Exit(1)


@app.command()
def watch() -> None:
    """Watch for new voice memos and export automatically."""
    console.print("[bold blue]VMEA Watch[/bold blue]")
    console.print("TODO: Implement filesystem watcher")
    raise typer.Exit(1)


@app.command()
def doctor() -> None:
    """Check system health and configuration."""
    console.print("[bold blue]VMEA Doctor[/bold blue]")
    console.print("TODO: Implement health checks")
    raise typer.Exit(1)


@app.command("retry-failed")
def retry_failed() -> None:
    """Retry previously failed exports."""
    console.print("[bold blue]VMEA Retry Failed[/bold blue]")
    console.print("TODO: Implement retry logic")
    raise typer.Exit(1)


@app.command("list")
def list_memos() -> None:
    """List discovered voice memos."""
    console.print("[bold blue]VMEA List[/bold blue]")
    console.print("TODO: Implement memo listing")
    raise typer.Exit(1)


@app.command()
def config() -> None:
    """Show current configuration."""
    console.print("[bold blue]VMEA Config[/bold blue]")
    console.print("TODO: Show config")
    raise typer.Exit(1)


# Daemon subcommand group
daemon_app = typer.Typer(help="Manage background daemon")
app.add_typer(daemon_app, name="daemon")


@daemon_app.command("install")
def daemon_install() -> None:
    """Install launchd daemon for background processing."""
    console.print("[bold blue]VMEA Daemon Install[/bold blue]")
    console.print("TODO: Install launchd plist")
    raise typer.Exit(1)


@daemon_app.command("uninstall")
def daemon_uninstall() -> None:
    """Remove launchd daemon."""
    console.print("[bold blue]VMEA Daemon Uninstall[/bold blue]")
    console.print("TODO: Remove launchd plist")
    raise typer.Exit(1)


@daemon_app.command("status")
def daemon_status() -> None:
    """Check daemon status."""
    console.print("[bold blue]VMEA Daemon Status[/bold blue]")
    console.print("TODO: Check launchd status")
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
