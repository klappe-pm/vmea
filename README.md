# VMEA – Voice Memo Export Automation

A lightweight, zero-telemetry macOS CLI tool that exports Apple Voice Memos to Obsidian/Logseq-compatible Markdown notes with rich YAML frontmatter.

## Features

- **Automatic Discovery** – Finds Voice Memos in standard macOS locations (Group Containers + Application Support)
- **Rich Metadata Extraction** – Parses `.composition/manifest.plist` and embedded `tsrp` atoms for transcripts, duration, recording date
- **Obsidian/Logseq Ready** – Generates Markdown with YAML frontmatter including tags, aliases, dates, transcript
- **Reconciliation-as-Source-of-Truth** – Idempotent exports with create/update/skip logic based on content hashes
- **Audio Preservation** – Copies `.m4a` files alongside notes with date-created metadata preserved
- **Optional LLM Cleanup** – Local Ollama integration for transcript post-processing (no internet required)
- **Background Daemon** – `launchd` integration with filesystem watching + periodic reconciliation
- **Zero Telemetry** – Fully offline, no tracking, MIT licensed

## Installation

```bash
# Clone and install
git clone https://github.com/YOUR_USERNAME/vmea.git
cd vmea
pip install -e .

# Or with pipx
pipx install git+https://github.com/YOUR_USERNAME/vmea.git
```

### Requirements

- macOS 14.0+ (Sonoma/Sequoia/Tahoe)
- Python 3.11+
- Full Disk Access permission (for Voice Memos folder)

## Quick Start

```bash
# First run – select output folder
vmea init

# Export all memos
vmea export

# Check system health
vmea doctor

# Watch for new memos (foreground)
vmea watch

# Install as background daemon
vmea daemon install
```

## Example Output

### Markdown Note (`2024-03-15-meeting-notes.md`)

```markdown
---
memo_id: "abc123def456"
title: "Meeting Notes"
domain: voice-memo
created: 2024-03-15T10:30:00-07:00
modified: 2024-03-15T10:35:22-07:00
duration_seconds: 322
has_transcript: true
transcript_source: native
audio_file: "2024-03-15-meeting-notes.m4a"
tags:
  - voice-memo
  - transcript
aliases:
  - "Meeting Notes (Voice Memo)"
---

# Meeting Notes

## Transcript

[Native transcript content here...]

## Metadata

- **Recorded**: March 15, 2024 at 10:30 AM
- **Duration**: 5:22
- **Audio**: [[2024-03-15-meeting-notes.m4a]]
```

## Configuration

VMEA uses a TOML config file at `~/.config/vmea/config.toml`:

```toml
# Output folder for notes and audio
output_folder = "~/Documents/Obsidian/Voice Memos"

# Default domain tag
default_domain = "voice-memo"

# LLM cleanup (optional)
llm_cleanup_enabled = false
ollama_model = "llama3.2:3b"
ollama_host = "http://localhost:11434"

# Background processing
watch_enabled = true
reconcile_interval_minutes = 60
```

See `config.example.toml` for all options.

## Commands

| Command | Description |
|---------|-------------|
| `vmea init` | First-run setup with folder picker |
| `vmea export` | Full export/reconciliation pass |
| `vmea export --memo-id <id>` | Export single memo |
| `vmea watch` | Foreground filesystem watcher |
| `vmea daemon install` | Install launchd daemon |
| `vmea daemon uninstall` | Remove launchd daemon |
| `vmea doctor` | System health check |
| `vmea retry-failed` | Retry previously failed exports |
| `vmea list` | List discovered memos |
| `vmea config` | Show current configuration |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Voice Memos Source                       │
│  ~/Library/Group Containers/group.com.apple.VoiceMemos...   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Discovery Layer                         │
│  • Path resolution (Group Containers / App Support)          │
│  • Pair matching (.m4a + .composition)                       │
│  • File stability detection                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Parsing Layer                           │
│  • manifest.plist parsing                                    │
│  • tsrp atom extraction (iOS 18+)                            │
│  • Metadata normalization                                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Reconciliation Layer                      │
│  • State store (JSONL)                                       │
│  • Content hashing                                           │
│  • Create / Update / Skip decisions                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Output Layer                            │
│  • Markdown + YAML frontmatter generation                    │
│  • Audio file copy with metadata                             │
│  • Optional LLM transcript cleanup                           │
└─────────────────────────────────────────────────────────────┘
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/vmea

# Linting
ruff check src/ tests/
ruff format src/ tests/
```

## License

MIT – see [LICENSE](LICENSE)

## Contributing

Contributions welcome! Please read the architecture docs and ensure tests pass before submitting PRs.

---

Built with 🎙️ by voice memo enthusiasts
