# Apple Voice Memo Export to Markdown

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![macOS](https://img.shields.io/badge/macOS-13%2B-brightgreen.svg)](https://www.apple.com/macos/)

Export Apple Voice Memos to markdown notes with AI-powered transcription and organization.

## Summary

**What it does:** Automatically exports Apple Voice Memos to well-organized markdown files with transcripts, AI-generated titles, key takeaways, and domain categorization.

**How it works:**
1. **Discovers** Voice Memos from iCloud sync folder
2. **Extracts** native iOS transcripts (or generates them with Whisper for older memos)
3. **Enhances** content using local LLM (Ollama) – cleans transcripts, generates titles & summaries
4. **Writes** markdown notes with YAML frontmatter and consistent naming: `YYYY-MM-DD-XX-title.md`
5. **Tracks** state to enable incremental updates without duplicates

**Key technologies:** Python 3.11+, OpenAI Whisper (local), Ollama (local LLM), Typer CLI

## Features

- 🎙️ **Automatic Export** – Convert Voice Memos to markdown with YAML frontmatter
- 🤖 **Whisper Transcription** – Generate transcripts for older memos without native transcription
- ✨ **LLM Enhancement** – Clean up transcripts, generate titles, key takeaways, and categorization
- 🔄 **Cascade Mode** – Run multiple LLM models sequentially for progressive refinement
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

**Priority:** `tsrp` → `plist` → `whisper` (fallback)

| Source | Description | Availability |
|--------|-------------|-------------|
| `tsrp` | Embedded in .m4a file | iOS 18+ / macOS 15+ |
| `plist` | manifest.plist in .composition folder | iOS 17+ |
| `whisper` | Generated locally via OpenAI Whisper | Any memo (fallback) |

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

## License

MIT – see [LICENSE](LICENSE)

---

## Architecture Diagrams

> Visual documentation of system architecture and data flow.

### Color Legend

| Color | Meaning |
|-------|--------|
| 🟦 Blue (`#3b82f6`) | Input / Source data |
| 🟨 Amber (`#f59e0b`) | Whisper transcription |
| 🟪 Purple (`#8b5cf6`) | LLM / Ollama processing |
| 🟩 Green (`#10b981`) | Output / Write operations |
| ⬜ Slate (`#64748b`) | State / Storage |

### Export Sequence Diagram

Shows the complete flow of a `vmea export` command:

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#3b82f6', 'secondaryColor': '#f59e0b', 'tertiaryColor': '#8b5cf6'}}}%%
sequenceDiagram
    participant User
    participant CLI
    participant Discovery
    participant Parser
    participant Whisper
    participant Ollama
    participant Writer
    participant State

    rect rgb(59, 130, 246, 0.1)
        Note over User,State: Initialization
        User->>CLI: vmea export
        CLI->>Discovery: find_source_path()
        Discovery-->>CLI: Voice Memos folder
        CLI->>Discovery: discover_memos()
        Discovery-->>CLI: List of MemoPairs
    end
    
    loop For each memo
        rect rgb(100, 116, 139, 0.1)
            Note over CLI,State: State Check
            CLI->>State: should_export(memo_id)
            State-->>CLI: (yes/no, reason)
        end
        
        alt Should export
            rect rgb(59, 130, 246, 0.1)
                Note over CLI,Parser: Parse
                CLI->>Parser: parse_memo(audio, composition)
                Parser-->>CLI: MemoMetadata
            end
            
            alt No transcript & transcribe_missing=true
                rect rgb(245, 158, 11, 0.1)
                    Note over CLI,Whisper: Transcription
                    CLI->>Whisper: transcribe_audio()
                    Whisper-->>CLI: transcript text
                end
            end
            
            alt LLM enabled & has transcript
                rect rgb(139, 92, 246, 0.1)
                    Note over CLI,Ollama: LLM Enhancement
                    CLI->>Ollama: generate_filename_title()
                    Ollama-->>CLI: "project-kickoff"
                    CLI->>Ollama: cleanup_transcript()
                    Ollama-->>CLI: revised transcript
                    CLI->>Ollama: generate_key_takeaways()
                    Ollama-->>CLI: 5 takeaways
                    CLI->>Ollama: generate_domains()
                    Ollama-->>CLI: domain, sub-domain
                end
            end
            
            rect rgb(16, 185, 129, 0.1)
                Note over CLI,State: Output
                CLI->>Writer: write_note()
                Writer-->>CLI: (note_path, audio_path)
                CLI->>State: record_export()
            end
        end
    end
    
    CLI-->>User: Summary (created/skipped/failed)
```

### Data Flow Diagram

Shows how data moves through the processing pipeline:

```mermaid
%%{init: {'theme': 'base'}}%%
flowchart TB
    subgraph Input["📥 Input Sources"]
        VM[("Voice Memos<br/>~/Library/Group Containers/")]
        M4A["🎵 .m4a audio files"]
        COMP["📋 .composition metadata"]
        VM --> M4A
        VM --> COMP
    end

    subgraph Parse["📖 Parsing"]
        PARSER["Parser Module<br/>Extract metadata"]
        META["MemoMetadata"]
        M4A --> PARSER
        COMP --> PARSER
        PARSER --> META
    end

    subgraph Transcribe["🎤 Transcription"]
        NATIVE{"Has native<br/>transcript?"}
        WHISPER["Whisper<br/>Speech-to-Text"]
        TRANS["Transcript Text"]
        META --> NATIVE
        NATIVE -->|No| WHISPER
        NATIVE -->|Yes| TRANS
        WHISPER --> TRANS
    end

    subgraph LLM["🤖 LLM Enhancement"]
        TITLE["Generate Title"]
        CLEANUP["Cleanup Transcript"]
        TAKEAWAY["Key Takeaways"]
        DOMAIN["Domain Classification"]
        TRANS --> TITLE
        TRANS --> CLEANUP
        TRANS --> TAKEAWAY
        TRANS --> DOMAIN
    end

    subgraph Output["📤 Output"]
        WRITE["Writer Module"]
        MD["📝 Markdown Note"]
        AUDIO["🔊 Audio File"]
        STATE[("State Store")]
        TITLE --> WRITE
        CLEANUP --> WRITE
        TAKEAWAY --> WRITE
        DOMAIN --> WRITE
        WRITE --> MD
        WRITE --> AUDIO
        MD --> STATE
    end

    style Input fill:#dbeafe,stroke:#3b82f6,stroke-width:2px
    style Parse fill:#dbeafe,stroke:#3b82f6,stroke-width:2px
    style Transcribe fill:#fef3c7,stroke:#f59e0b,stroke-width:2px
    style LLM fill:#ede9fe,stroke:#8b5cf6,stroke-width:2px
    style Output fill:#d1fae5,stroke:#10b981,stroke-width:2px
    style WHISPER fill:#f59e0b,color:#fff
    style TITLE fill:#8b5cf6,color:#fff
    style CLEANUP fill:#8b5cf6,color:#fff
    style TAKEAWAY fill:#8b5cf6,color:#fff
    style DOMAIN fill:#8b5cf6,color:#fff
    style STATE fill:#64748b,color:#fff
```

### Decision Flowchart

Shows the branching logic during export:

```mermaid
%%{init: {'theme': 'base'}}%%
flowchart TD
    START(["🚀 Start Export"]) --> DISCOVER["Discover Memos"]
    DISCOVER --> LOOP{"More memos?"}
    
    LOOP -->|Yes| CHECK["Check State"]
    CHECK --> SHOULD{"Should export?"}
    
    SHOULD -->|"No: unchanged"| SKIP["⏭️ Skip memo"]
    SKIP --> LOOP
    
    SHOULD -->|Yes| PARSE["Parse Metadata"]
    PARSE --> HAS_TRANS{"Has transcript?"}
    
    HAS_TRANS -->|No| WHISPER_CHECK{"Whisper enabled?"}
    WHISPER_CHECK -->|Yes| TRANSCRIBE["🎤 Transcribe with Whisper"]
    WHISPER_CHECK -->|No| LLM_CHECK
    TRANSCRIBE --> LLM_CHECK
    
    HAS_TRANS -->|Yes| LLM_CHECK{"LLM enabled?"}
    
    LLM_CHECK -->|Yes| GEN_TITLE["🏷️ Generate Title"]
    GEN_TITLE --> CLEANUP_T["✨ Cleanup Transcript"]
    CLEANUP_T --> TAKEAWAYS["📝 Generate Takeaways"]
    TAKEAWAYS --> DOMAINS["🗂️ Categorize Domain"]
    DOMAINS --> WRITE
    
    LLM_CHECK -->|No| WRITE["💾 Write Note"]
    
    WRITE --> AUDIO_MODE{"Audio mode?"}
    AUDIO_MODE -->|copy| COPY["📁 Copy Audio"]
    AUDIO_MODE -->|app-link| LINK["🔗 Create Link"]
    AUDIO_MODE -->|symlink| SYM["↗️ Symlink"]
    
    COPY --> RECORD
    LINK --> RECORD
    SYM --> RECORD
    
    RECORD["📊 Record State"] --> LOOP
    
    LOOP -->|No| DONE(["✅ Done"])

    style START fill:#10b981,color:#fff,stroke:#059669
    style DONE fill:#10b981,color:#fff,stroke:#059669
    style TRANSCRIBE fill:#f59e0b,color:#fff,stroke:#d97706
    style GEN_TITLE fill:#8b5cf6,color:#fff,stroke:#7c3aed
    style CLEANUP_T fill:#8b5cf6,color:#fff,stroke:#7c3aed
    style TAKEAWAYS fill:#8b5cf6,color:#fff,stroke:#7c3aed
    style DOMAINS fill:#8b5cf6,color:#fff,stroke:#7c3aed
    style WRITE fill:#10b981,color:#fff,stroke:#059669
    style RECORD fill:#64748b,color:#fff,stroke:#475569
    style SKIP fill:#94a3b8,color:#fff
```

### Class Diagram

Shows the main data structures and their relationships:

```mermaid
%%{init: {'theme': 'base'}}%%
classDiagram
    class MemoPair {
        +Path audio_path
        +Path composition_path
        +str memo_id
        +has_composition() bool
    }

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
        +compact() int
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

    style MemoPair fill:#dbeafe,stroke:#3b82f6
    style MemoMetadata fill:#dbeafe,stroke:#3b82f6
    style MemoState fill:#f1f5f9,stroke:#64748b
    style StateStore fill:#f1f5f9,stroke:#64748b
    style VMEAConfig fill:#f1f5f9,stroke:#64748b
    style TranscriptionResult fill:#fef3c7,stroke:#f59e0b
    style CleanupResult fill:#ede9fe,stroke:#8b5cf6
    style DomainResult fill:#ede9fe,stroke:#8b5cf6
```

### Transcription Sources Diagram

Shows the priority of transcript sources:

```mermaid
%%{init: {'theme': 'base'}}%%
flowchart LR
    subgraph Native["Native iOS Transcription"]
        TSRP["tsrp atom<br/>(iOS 18+)"]
        PLIST["manifest.plist<br/>(iOS 17+)"]
    end
    
    subgraph Generated["Generated Locally"]
        WHISPER["OpenAI Whisper<br/>(any memo)"]
    end
    
    TSRP -->|"Priority 1"| TRANSCRIPT
    PLIST -->|"Priority 2"| TRANSCRIPT
    WHISPER -->|"Fallback"| TRANSCRIPT
    TRANSCRIPT["📝 Final Transcript"]
    
    style Native fill:#d1fae5,stroke:#10b981,stroke-width:2px
    style Generated fill:#fef3c7,stroke:#f59e0b,stroke-width:2px
    style TSRP fill:#10b981,color:#fff
    style PLIST fill:#10b981,color:#fff
    style WHISPER fill:#f59e0b,color:#fff
    style TRANSCRIPT fill:#3b82f6,color:#fff
```
