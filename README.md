# Apple Voice Memo Export to Markdown

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![macOS](https://img.shields.io/badge/macOS-13%2B-brightgreen.svg)](https://www.apple.com/macos/)

Export Apple Voice Memos to markdown notes with AI-powered transcription and organization.

## Summary
Automatically exports Apple Voice Memos to well-organized markdown files with transcripts, AI-generated titles, key takeaways, and domain categorization.

### How this project works
1. **Discovers** Voice Memos from iCloud sync folder
2. **Extracts** native iOS transcripts (preserved as "Original Transcript")
3. **Transcribes** audio with Whisper (preserved as "Whisper Transcript")
4. **Enhances** content using local LLM cascade (Ollama) – cleans transcripts, generates titles, summaries & key takeaways
5. **Writes** markdown notes with three transcript tiers, summary, YAML frontmatter: `YYYY-MM-DD-XX-title.md`
6. **Tracks** state to enable incremental updates without duplicates



## Features
- 🎙️ **Automatic Export** – Convert Voice Memos to markdown with YAML frontmatter
- 🤖 **Whisper Transcription** – Generate transcripts for older memos without native transcription
- ✨ **LLM Enhancement** – Clean up transcripts, generate titles, key takeaways, summaries, and categorization
- 🔄 **Cascade Mode** – Run multiple LLM models sequentially for progressive refinement
- 📊 **Three-Tier Transcripts** – Cascade (LLM), Whisper, and Original (iOS) transcripts preserved separately
- 📝 **Customizable Instructions** – Edit LLM prompts without modifying code
- 📁 **Smart Naming** – Auto-generated filenames: `YYYY-MM-DD-XX-descriptive-title.md`
- 🔗 **Flexible Audio** – Copy files, symlink, or link directly to Voice Memos app
- 👀 **Watch Mode** – Automatically export new memos as they're recorded
- 🔄 **Idempotent** – Re-run safely without creating duplicates

## Documentation
- 📖 **[Getting Started Guide](docs/GETTING_STARTED.md)** – Complete setup walkthrough
- ⚙️ **[Customizing LLM Instructions](docs/CUSTOMIZING_LLM_INSTRUCTIONS.md)** – Tailor transcript cleanup

## Installation
```bash
# Install
git clone https://github.com/klappe-pm/Apple-Voice-Memo-Export-to-Markdown.git
cd Apple-Voice-Memo-Export-to-Markdown
pip install -e .

## Optional Dependencies
```bash
# For Whisper transcription (older memos without native transcripts)
pip install -e ".[transcribe]"

# Export all memos
vmea export

# Check system health
vmea doctor
```

## Requirements
- **macOS 13+** (Ventura or later)
- **Python 3.11+**
- **Full Disk Access** permission (System Settings > Privacy & Security)
- **Ollama** (optional, for LLM features)

## Quick Start
```bash
# 1. Initialize configuration
vmea init
# 2. Export all memos
vmea export
# 3. Check system health
vmea doctor
```

## Output Format
### Filename Convention
```
2024-03-15-00-project-kickoff-meeting.md
```

**Examples:**
- `2024-03-15-00-project-kickoff-meeting.md`
- `2024-03-15-01-afternoon-standup.md`
- `2024-03-15-02-client-call-notes.md`

## Core Commands Reference
| Command | Description |
|---------|-------------|
| `vmea init` | First-run setup with folder picker |
| `vmea export` | Export all memos |
| `vmea export --memo-id <id>` | Export single memo |
| `vmea export --dry-run` | Preview without writing files |
| `vmea export --force` | Re-export even if unchanged |
| `vmea list` | List discovered memos |
| `vmea doctor` | System health check |
| `vmea config` | Show current configuration |

## Watch & Daemon Command Reference
| Command | Description |
|---------|-------------|
| `vmea watch` | Foreground filesystem watcher |
| `vmea daemon install` | Install launchd background service |
| `vmea daemon uninstall` | Remove launchd service |
| `vmea daemon status` | Check daemon status |
| `vmea retry-failed` | Retry previously failed exports |

### Ollama (LLM) Commnd Reference
| Command | Description |
|---------|-------------|
| `vmea ollama status` | Check Ollama server status |
| `vmea ollama start` | Start Ollama server |
| `vmea ollama models` | List available models |
| `vmea ollama select` | Interactively select a model |
| `vmea ollama pull <model>` | Pull a model from registry |

## Configuration
Config file: `~/.config/vmea/config.toml`

### Configuration Options
```toml
# Output settings
output_folder = "~/Documents/Voice Memos"
audio_export_mode = "copy"  # "copy", "symlink", or "app-link"

# Whisper transcription (for memos without native transcripts)
transcribe_missing = true
whisper_model = "base"  # tiny, base, small, medium, large

# LLM cleanup via Ollama
llm_cleanup_enabled = true
ollama_model = "llama3.2:3b"              # Single model (default)
ollama_models = []                         # Cascade mode: ["model1", "model2", "model3"]
ollama_host = "http://localhost:11434"
cleanup_instructions_path = ""             # Custom instructions file (optional)
```

### Cascade Mode
Run multiple models sequentially for progressive refinement:

```toml
# Example cascade configuration
ollama_models = ["llama3.2:3b", "llama3.1:8b", "mistral:7b"]
```

| Stage | Purpose |
|-------|--------|
| Model 1 | Initial cleanup – punctuation, filler words |
| Model 2 | Revision – clarity, flow, structure |
| Model 3 | Polish – professional quality, consistency |

See [Cascade Mode documentation](docs/GETTING_STARTED.md#cascade-mode) for details.

### Audio Export Modes
| Mode | Behavior |
|------|----------|
| `copy` | Copies .m4a to `output_folder/Audio/` |
| `symlink` | Creates symlink to original file |
| `app-link` | Creates clickable link to open Voice Memos app |

### Whisper Models
| Model | Size | Speed | Quality |
|-------|------|-------|--------|
| `tiny` | 39 MB | ⚡⚡⚡⚡ | ★★☆☆☆ |
| `base` | 74 MB | ⚡⚡⚡ | ★★★☆☆ |
| `small` | 244 MB | ⚡⚡ | ★★★★☆ |
| `medium` | 769 MB | ⚡ | ★★★★★ |
| `large` | 1.5 GB | 🐢 | ★★★★★ |

## Transcription Sources
VMEA extracts transcripts from multiple sources:

### Priority
`tsrp` → `plist` → `whisper` (fallback)

| Source | Description | Availability |
|--------|-------------|-------------|
| `tsrp` | Embedded in .m4a file | iOS 18+ / macOS 15+ |
| `plist` | manifest.plist in .composition folder | iOS 17+ |
| `whisper` | Generated locally via OpenAI Whisper | Any memo (fallback) |

## LLM Processing
When `llm_cleanup_enabled = true`, Ollama performs:

1. **Filename Title Generation** – Creates descriptive slug for filename
2. **Transcript Cleanup** – Fixes punctuation, paragraphs, artifacts (cascade mode)
3. **Key Takeaways** – Extracts 5 main points
4. **Domain Categorization** – Assigns domain and sub-domain
5. **Summary Generation** – Creates a 2-4 sentence summary placed under the note title

### What LLM cleanup does:
- ✅ Fix punctuation and capitalization
- ✅ Improve paragraph breaks
- ✅ Correct obvious transcription errors
- ✅ Apply consistent formatting
- ✅ Add Obsidian backlinks to key terms (customizable)

### What LLM cleanup does NOT do:
- ❌ Summarize or shorten content
- ❌ Add information not present
- ❌ Interpret or editorialize
- ❌ Change the speaker's meaning

### Customizing LLM Behavior
Edit the instruction file to customize how transcripts are processed:

```bash
# Copy default instructions
cp src/vmea/prompts/cleanup_instructions.md ~/.config/vmea/

# Edit and set path in config.toml
cleanup_instructions_path = "~/.config/vmea/cleanup_instructions.md"
```

See [Customizing LLM Instructions](docs/CUSTOMIZING_LLM_INSTRUCTIONS.md) for details.

## Development
```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,transcribe,llm]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=vmea

# Type checking
mypy src/vmea

# Linting
ruff check src/vmea
```

## Project Structure
```
src/vmea/
├── __init__.py       # Package version
├── __main__.py       # Entry point
├── cli.py            # Typer CLI commands
├── config.py         # Pydantic config models
├── discovery.py      # Find Voice Memos folder
├── parser.py         # Extract metadata & transcripts
├── transcribe.py     # Whisper integration
├── cleanup.py        # Ollama LLM processing (single & cascade)
├── writer.py         # Generate markdown notes
├── state.py          # JSONL state tracking
├── ollama.py         # Ollama server management
└── prompts/          # LLM instruction templates
    └── cleanup_instructions.md  # Default cleanup instructions

docs/
├── GETTING_STARTED.md           # Complete setup guide
└── CUSTOMIZING_LLM_INSTRUCTIONS.md  # LLM customization guide
```

## Troubleshooting

### "Voice Memos folder not found"
1. Open Voice Memos app to trigger iCloud sync
2. Grant Full Disk Access in System Settings → Privacy & Security
3. Run `vmea doctor` to see which paths are checked

### "Whisper not installed"
```bash
pip install -e ".[transcribe]"
```

### "Ollama not running"
```bash
vmea ollama start
# or manually: ollama serve
```

## Architecture Diagrams
All diagrams have been moved into dedicated files under `docs/diagrams/`.

- [Architecture Diagrams Index](docs/diagrams/README.md)
- [Export Sequence Diagram](docs/diagrams/export-sequence-diagram.md)
- [Data Flow Pipeline Diagram](docs/diagrams/data-flow-pipeline-diagram.md)
- [Export Decision Flowchart](docs/diagrams/export-decision-flowchart.md)
- [Core Data Model Class Diagram](docs/diagrams/core-data-model-class-diagram.md)
- [Transcript Source Priority Diagram](docs/diagrams/transcript-source-priority-diagram.md)
