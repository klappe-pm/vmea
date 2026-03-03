# Configuration

VMEA stores its configuration in a TOML file at `~/.config/vmea/config.toml`. Run `vmea init` to create it interactively, or edit it directly.

## All Options

```toml
# ─── Output ────────────────────────────────────────────────────
output_folder = "~/Documents/Voice Memos"       # Where markdown notes are written
audio_output_folder = ""                         # Separate audio folder (empty = same as output_folder)
audio_export_mode = "app-link"                   # "copy", "symlink", "source-link", or "app-link"
audio_fallback_to_source_link = false            # Fall back to source-link if primary mode fails

# ─── Metadata ──────────────────────────────────────────────────
default_domain = ""                              # Pre-fill domain in frontmatter
filename_date_format = "%Y-%m-%d"                # strftime format for dates in filenames

# ─── Source detection ──────────────────────────────────────────
source_path_override = ""                        # Manual path to Voice Memos folder (empty = auto-detect)

# ─── Transcript ────────────────────────────────────────────────
include_native_transcript = true                 # Include iOS native transcript in output
transcript_source_priority = "both"              # "plist", "tsrp", or "both"

# ─── LLM cleanup (Ollama) ─────────────────────────────────────
llm_cleanup_enabled = true                       # Enable LLM-powered transcript enhancement
ollama_model = "llama3.2:3b"                     # Single model (used when ollama_models is empty)
ollama_models = []                               # Cascade mode: ["model1", "model2", "model3"]
ollama_host = "http://localhost:11434"            # Ollama server URL
ollama_timeout = 120                             # Seconds per LLM request
cleanup_instructions_path = ""                   # Custom instruction file (empty = built-in default)
fail_on_missing_instruction_file = false          # Error if instruction file is missing
preserve_raw_transcript = true                   # Keep the original transcript alongside the revised one
ollama_startup_mode = "terminal_managed"         # "terminal_managed" or "background"

# ─── Whisper transcription ─────────────────────────────────────
whisper_model = "base"                           # tiny, base, small, medium, large
whisper_language = ""                            # ISO language code (empty = auto-detect)
transcribe_missing = true                        # Transcribe memos that lack a native transcript

# ─── Reconciliation & state ────────────────────────────────────
conflict_resolution = "update"                   # "skip", "update", or "overwrite"
state_file = ".vmea-state.jsonl"                 # State file name (stored inside output_folder)

# ─── Watch mode ────────────────────────────────────────────────
watch_debounce_seconds = 5                       # Seconds to wait after a file event before exporting

# ─── Advanced ──────────────────────────────────────────────────
dry_run = false                                  # Preview mode (no files written)
```

## Audio Export Modes

| Mode | Behavior |
|------|----------|
| `copy` | Copies the `.m4a` file into `output_folder/Audio/` |
| `symlink` | Creates a symbolic link pointing to the original file |
| `source-link` | Stores the original file path for reference |
| `app-link` | Generates a clickable `file://` link that opens Voice Memos app (default, no file copy) |

## Cascade Mode

Cascade mode runs your transcript through multiple LLM models sequentially. Each model refines the output of the previous one.

```toml
ollama_models = ["llama3.2:3b", "llama3.1:8b", "mistral:7b"]
```

| Stage | Role | Typical Model |
|-------|------|---------------|
| 1 | Initial cleanup -- fix punctuation, remove filler words | Small/fast model |
| 2 | Revision -- improve clarity, flow, paragraph structure | Medium model |
| 3 | Polish -- professional quality, consistency check | Larger model |

When `ollama_models` is non-empty it takes precedence over `ollama_model`. The first model in the list is also used for auxiliary tasks (title generation, key takeaways, domain categorization).

See [Customizing LLM Instructions](CUSTOMIZING_LLM_INSTRUCTIONS.md) for how to change what the LLM does during cleanup.

## Whisper Models

| Model | Size | Speed | Quality |
|-------|------|-------|---------|
| `tiny` | 39 MB | Fastest | Basic |
| `base` | 74 MB | Fast | Good (default) |
| `small` | 244 MB | Moderate | High |
| `medium` | 769 MB | Slow | Very High |
| `large` | 1.5 GB | Slowest | Best |

Install Whisper support with:

```bash
pip install -e ".[transcribe]"
```

## Transcript Source Priority

VMEA can extract transcripts from multiple sources. The `transcript_source_priority` setting controls which sources are tried:

| Value | Behavior |
|-------|----------|
| `both` | Try `tsrp` first, then `plist` (default) |
| `tsrp` | Only use the tsrp atom embedded in the `.m4a` file (iOS 18+/macOS 15+) |
| `plist` | Only use `manifest.plist` from the `.composition` folder (iOS 17+) |

If no native transcript is found and `transcribe_missing = true`, Whisper generates one locally.

## Conflict Resolution

Controls what happens when a memo has already been exported:

| Value | Behavior |
|-------|----------|
| `update` | Re-export only if the source files changed (default) |
| `skip` | Never re-export an already-exported memo |
| `overwrite` | Always re-export, even if unchanged |

## State File

Export state is tracked in a JSONL file (`output_folder/.vmea-state.jsonl`). Each line records:

- Memo ID and source hash
- Paths to the exported note and audio
- Timestamp and transcript source

To force a full re-export, delete this file and run `vmea export`.
