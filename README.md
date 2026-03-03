# Apple Voice Memo Export to Markdown

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![macOS](https://img.shields.io/badge/macOS-13%2B-brightgreen.svg)](https://www.apple.com/macos/)

Export Apple Voice Memos to markdown notes with AI-powered transcription and organization.

## Features

- 🎙️ **Automatic Export** – Convert Voice Memos to markdown with YAML frontmatter
- 🤖 **Whisper Transcription** – Generate transcripts for older memos without native transcription
- ✨ **LLM Enhancement** – Clean up transcripts, generate titles, key takeaways, and categorization
- 📁 **Smart Naming** – Auto-generated filenames: `YYYY-MM-DD-XX-descriptive-title.md`
- 🔗 **Flexible Audio** – Copy files, symlink, or link directly to Voice Memos app
- 👀 **Watch Mode** – Automatically export new memos as they're recorded
- 🔄 **Idempotent** – Re-run safely without creating duplicates

## Architecture Overview

### Export Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Discovery
    participant Parser
    participant Whisper
    participant Ollama
    participant Writer
    participant State

    User->>CLI: vmea export
    CLI->>Discovery: find_source_path()
    Discovery-->>CLI: Voice Memos folder
    CLI->>Discovery: discover_memos()
    Discovery-->>CLI: List of MemoPairs
    
    loop For each memo
        CLI->>State: should_export(memo_id)
        State-->>CLI: (yes/no, reason)
        
        alt Should export
            CLI->>Parser: parse_memo(audio, composition)
            Parser-->>CLI: MemoMetadata
            
            alt No transcript & transcribe_missing=true
                CLI->>Whisper: transcribe_audio()
                Whisper-->>CLI: transcript text
            end
            
            alt LLM enabled & has transcript
                CLI->>Ollama: generate_filename_title()
                Ollama-->>CLI: "project-kickoff"
                CLI->>Ollama: cleanup_transcript()
                Ollama-->>CLI: revised transcript
                CLI->>Ollama: generate_key_takeaways()
                Ollama-->>CLI: 5 takeaways
                CLI->>Ollama: generate_domains()
                Ollama-->>CLI: domain, sub-domain
            end
            
            CLI->>Writer: write_note()
            Writer-->>CLI: (note_path, audio_path)
            CLI->>State: record_export()
        end
    end
    
    CLI-->>User: Summary (created/skipped/failed)
```

### Data Flow

```mermaid
flowchart TB
    subgraph Input["📥 Input Sources"]
        VM[("Voice Memos<br/>~/Library/Group Containers/")]
        M4A["🎵 .m4a files"]
        COMP["📋 .composition folders"]
        VM --> M4A
        VM --> COMP
    end

    subgraph Processing["⚙️ Processing Pipeline"]
        PARSE["Parser<br/>Extract metadata & transcript"]
        WHISPER["Whisper<br/>Generate missing transcripts"]
        LLM["Ollama LLM<br/>Enhance & categorize"]
        
        M4A --> PARSE
        COMP --> PARSE
        PARSE -->|No transcript| WHISPER
        WHISPER --> LLM
        PARSE -->|Has transcript| LLM
    end

    subgraph Output["📤 Output"]
        MD["📝 Markdown Note<br/>2024-03-15-00-meeting-notes.md"]
        AUDIO["🔊 Audio File<br/>Audio/2024-03-15-00-meeting-notes.m4a"]
        STATE[("State Store<br/>.vmea-state.jsonl")]
        
        LLM --> MD
        LLM --> AUDIO
        MD --> STATE
    end

    style Input fill:#e1f5fe
    style Processing fill:#fff3e0
    style Output fill:#e8f5e9
```

### Class Diagram

```mermaid
classDiagram
    class MemoMetadata {
        +str memo_id
        +str title
        +datetime created
        +datetime modified
        +float duration_seconds
        +str transcript
        +str revised_transcript
        +str transcript_source
        +str custom_label
        +bool is_favorited
    }

    class MemoPair {
        +Path audio_path
        +Path composition_path
        +str memo_id
        +has_composition() bool
    }

    class MemoState {
        +str memo_id
        +str source_hash
        +str note_path
        +str audio_path
        +str exported_at
        +str transcript_source
    }

    class StateStore {
        +Path path
        -dict _records
        +get(memo_id) MemoState
        +set(record) void
        +remove(memo_id) bool
        +all() Iterator
    }

    class VMEAConfig {
        +Path output_folder
        +str audio_export_mode
        +bool llm_cleanup_enabled
        +str ollama_model
        +str whisper_model
        +bool transcribe_missing
    }

    class TranscriptionResult {
        +str text
        +str model
        +str language
    }

    class CleanupResult {
        +str revised_transcript
        +str instruction_source
        +str model
    }

    class DomainResult {
        +str domain
        +str sub_domain
    }

    MemoPair --> MemoMetadata : parsed into
    MemoMetadata --> MemoState : exported as
    StateStore --> MemoState : manages
    VMEAConfig --> StateStore : configures
```

### Decision Logic

```mermaid
flowchart TD
    START([Start Export]) --> DISCOVER[Discover Memos]
    DISCOVER --> LOOP{More memos?}
    
    LOOP -->|Yes| CHECK[Check State]
    CHECK --> SHOULD{Should export?}
    
    SHOULD -->|No: unchanged| SKIP[Skip memo]
    SKIP --> LOOP
    
    SHOULD -->|Yes| PARSE[Parse Metadata]
    PARSE --> HAS_TRANS{Has transcript?}
    
    HAS_TRANS -->|No| WHISPER_CHECK{Whisper enabled?}
    WHISPER_CHECK -->|Yes| TRANSCRIBE[Transcribe with Whisper]
    WHISPER_CHECK -->|No| LLM_CHECK
    TRANSCRIBE --> LLM_CHECK
    
    HAS_TRANS -->|Yes| LLM_CHECK{LLM enabled?}
    
    LLM_CHECK -->|Yes| GEN_TITLE[Generate Filename Title]
    GEN_TITLE --> CLEANUP[Cleanup Transcript]
    CLEANUP --> TAKEAWAYS[Generate Key Takeaways]
    TAKEAWAYS --> DOMAINS[Generate Domains]
    DOMAINS --> WRITE
    
    LLM_CHECK -->|No| WRITE[Write Note]
    
    WRITE --> AUDIO_MODE{Audio mode?}
    AUDIO_MODE -->|copy| COPY[Copy Audio File]
    AUDIO_MODE -->|app-link| LINK[Create App Link]
    AUDIO_MODE -->|symlink| SYM[Create Symlink]
    
    COPY --> RECORD
    LINK --> RECORD
    SYM --> RECORD
    
    RECORD[Record to State] --> LOOP
    
    LOOP -->|No| DONE([Done])

    style START fill:#4caf50,color:#fff
    style DONE fill:#4caf50,color:#fff
    style TRANSCRIBE fill:#ff9800,color:#fff
    style GEN_TITLE fill:#2196f3,color:#fff
    style CLEANUP fill:#2196f3,color:#fff
    style TAKEAWAYS fill:#2196f3,color:#fff
    style DOMAINS fill:#2196f3,color:#fff
```

## Installation

```bash
git clone https://github.com/klappe-pm/Apple-Voice-Memo-Export-to-Markdown.git
cd Apple-Voice-Memo-Export-to-Markdown
pip install -e .
```

### Optional Dependencies

```bash
# For Whisper transcription (older memos without native transcripts)
pip install -e ".[transcribe]"

# For LLM features (requires Ollama installed separately)
pip install -e ".[llm]"

# For development
pip install -e ".[dev]"
```

### Requirements

- **macOS 13+** (Ventura or later)
- **Python 3.11+**
- **Full Disk Access** permission (System Settings → Privacy & Security)
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
YYYY-MM-DD-XX-descriptive-title.md
│    │  │  │   └── LLM-generated title slug
│    │  │  └────── Daily sequence (00, 01, 02...)
│    │  └───────── Day
│    └──────────── Month
└───────────────── Year
```

**Examples:**
- `2024-03-15-00-project-kickoff-meeting.md`
- `2024-03-15-01-afternoon-standup.md`
- `2024-03-15-02-client-call-notes.md`

### Note Structure

```yaml
---
domains: Technology
sub-domains: Software Development
llm-model: llama3.2:3b
date-created: 2024-03-15
date-revised: 2024-03-15
aliases:
tags:
---

# 2024-03-15-00-project-kickoff-meeting

## Voice Memo
![[Audio/2024-03-15-00-project-kickoff-meeting.m4a]]

## Key Takeaways
1. First key point from the memo.
2. Second key point from the memo.
3. Third key point from the memo.
4. Fourth key point from the memo.
5. Fifth key point from the memo.

### Revised Transcript
```markdown
Cleaned up transcript text...
```

### Original Transcript
```markdown
Raw transcript from iOS/Whisper...
```
```

## Commands Reference

### Core Commands

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

### Watch & Daemon

| Command | Description |
|---------|-------------|
| `vmea watch` | Foreground filesystem watcher |
| `vmea daemon install` | Install launchd background service |
| `vmea daemon uninstall` | Remove launchd service |
| `vmea daemon status` | Check daemon status |
| `vmea retry-failed` | Retry previously failed exports |

### Ollama (LLM)

| Command | Description |
|---------|-------------|
| `vmea ollama status` | Check Ollama server status |
| `vmea ollama start` | Start Ollama server |
| `vmea ollama models` | List available models |
| `vmea ollama select` | Interactively select a model |
| `vmea ollama pull <model>` | Pull a model from registry |

## Configuration

Config file: `~/.config/vmea/config.toml`

### Key Options

```toml
# Output settings
output_folder = "~/Documents/Voice Memos"
audio_export_mode = "copy"  # "copy", "symlink", or "app-link"

# Whisper transcription (for memos without native transcripts)
transcribe_missing = true
whisper_model = "base"  # tiny, base, small, medium, large

# LLM cleanup via Ollama
llm_cleanup_enabled = true
ollama_model = "llama3.2:3b"
ollama_host = "http://localhost:11434"
```

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

```mermaid
flowchart LR
    subgraph Native["Native iOS Transcription"]
        TSRP["tsrp atom<br/>(iOS 18+)"] 
        PLIST["manifest.plist<br/>(composition folder)"]
    end
    
    subgraph Generated["Generated"]
        WHISPER["Whisper<br/>(local AI)"]
    end
    
    TSRP --> TRANSCRIPT[Final Transcript]
    PLIST --> TRANSCRIPT
    WHISPER --> TRANSCRIPT
    
    style TSRP fill:#4caf50,color:#fff
    style PLIST fill:#4caf50,color:#fff  
    style WHISPER fill:#ff9800,color:#fff
```

**Priority:** `tsrp` → `plist` → `whisper` (fallback)

## LLM Processing

When `llm_cleanup_enabled = true`, Ollama performs:

1. **Filename Title Generation** – Creates descriptive slug for filename
2. **Transcript Cleanup** – Fixes punctuation, paragraphs, artifacts
3. **Key Takeaways** – Extracts 5 main points
4. **Domain Categorization** – Assigns domain and sub-domain

### What LLM cleanup does:
- ✅ Fix punctuation and capitalization
- ✅ Improve paragraph breaks
- ✅ Correct obvious transcription errors
- ✅ Apply consistent formatting

### What LLM cleanup does NOT do:
- ❌ Summarize or shorten content
- ❌ Add information not present
- ❌ Interpret or editorialize
- ❌ Change the speaker's meaning

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
├── cleanup.py        # Ollama LLM processing
├── writer.py         # Generate markdown notes
├── state.py          # JSONL state tracking
└── ollama.py         # Ollama server management
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

## License

MIT – see [LICENSE](LICENSE)
