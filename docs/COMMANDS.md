# Commands Reference

All available `vmea` CLI commands and their options.

## Core Commands

### `vmea init`

First-run setup wizard. Interactively configures output folder, audio folder, source detection, and LLM settings.

```bash
vmea init
```

Creates `~/.config/vmea/config.toml` with your choices.

### `vmea export`

Export voice memos to markdown.

```bash
vmea export                          # Export all memos
vmea export --memo-id <id>           # Export a single memo
vmea export --dry-run                # Preview without writing files
vmea export --force                  # Re-export even if unchanged
vmea export --use-config-paths       # Use config paths without interactive prompts
```

| Flag | Description |
|------|-------------|
| `--memo-id <id>` | Export only the specified memo |
| `--dry-run` | Show what would be exported without writing files |
| `--force` | Re-export memos even if unchanged since last export |
| `--use-config-paths` | Skip interactive folder prompts; use paths from config |

### `vmea list`

List all discovered voice memos and their status.

```bash
vmea list
```

Shows memo ID, title, date, duration, transcript availability, and export status.

### `vmea doctor`

Run system health checks.

```bash
vmea doctor
```

Checks:
- Config file exists and is valid
- Voice Memos folder is accessible
- Output folder exists
- Python version is compatible
- Ollama is running (if LLM enabled)
- Selected model is available

### `vmea config`

Display current configuration.

```bash
vmea config
```

## Watch & Background

### `vmea watch`

Start a foreground filesystem watcher that auto-exports new memos as they appear.

```bash
vmea watch
# Press Ctrl+C to stop
```

Uses `watchdog` to monitor the Voice Memos source folder. New or modified `.m4a` files are automatically exported after a configurable debounce delay (`watch_debounce_seconds`).

### `vmea retry-failed`

Retry memos that previously failed to export.

```bash
vmea retry-failed
```

Finds memos with `error` entries in the state file, clears those records, and re-exports them.

### `vmea daemon install`

Install a macOS launchd service for background processing.

```bash
vmea daemon install
```

Creates a `com.vmea.export` plist in `~/Library/LaunchAgents/`.

### `vmea daemon uninstall`

Remove the launchd service.

```bash
vmea daemon uninstall
```

### `vmea daemon status`

Check whether the daemon is loaded and running.

```bash
vmea daemon status
```

## Ollama (LLM) Commands

### `vmea ollama status`

Check if Ollama is installed and running.

```bash
vmea ollama status
```

### `vmea ollama start`

Start the Ollama server.

```bash
vmea ollama start
```

### `vmea ollama models`

List locally available Ollama models.

```bash
vmea ollama models
```

### `vmea ollama select`

Interactively select and configure an Ollama model.

```bash
vmea ollama select
```

Supports both single-model and cascade (multi-model) selection.

### `vmea ollama pull`

Pull a model from the Ollama registry.

```bash
vmea ollama pull llama3.2:3b
vmea ollama pull mistral:7b
```

## Global Options

| Option | Description |
|--------|-------------|
| `--version`, `-v` | Print version and exit |
| `--help` | Show help for any command |

```bash
vmea --version
vmea export --help
vmea ollama --help
```
