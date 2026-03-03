# Development

Guide for contributing to VMEA, running tests, and understanding the project structure.

---

## Setup

```bash
# Clone
git clone https://github.com/klappe-pm/Apple-Voice-Memo-Export-to-Markdown.git
cd Apple-Voice-Memo-Export-to-Markdown

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install with all extras
pip install -e ".[dev,transcribe,llm]"
```

## Running Tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov=vmea

# Single test file
pytest tests/test_parser.py -v
```

## Linting & Type Checking

```bash
# Lint
ruff check src/vmea

# Auto-fix lint issues
ruff check --fix src/vmea

# Type check
mypy src/vmea
```

## CI

The GitHub Actions workflow (`.github/workflows/pylint.yml`) runs on Python 3.11, 3.12, and 3.13:

1. Installs the project with all extras
2. Runs `ruff check src/vmea`
3. Runs `pytest --cov=vmea`

---

## Project Structure

```
src/vmea/
├── __init__.py          # Package version
├── __main__.py          # python -m vmea entry point
├── cli.py               # Typer CLI commands and orchestration
├── config.py            # VMEAConfig Pydantic model, load/save/migrate
├── discovery.py         # Locate Voice Memos on disk (MemoPair)
├── parser.py            # Extract MemoMetadata from .m4a + .composition
├── transcribe.py        # Whisper speech-to-text integration
├── cleanup.py           # Ollama LLM cleanup, cascade, takeaways, domains
├── writer.py            # Generate and write Markdown notes
├── state.py             # JSONL state store (StateStore, MemoState)
├── ollama.py            # Ollama server lifecycle management
└── prompts/
    ├── __init__.py
    └── cleanup_instructions.md   # Default LLM system prompt

tests/
├── conftest.py          # Shared fixtures (temp dirs, mock memo structures)
├── test_cli.py          # CLI unit tests
├── test_cleanup.py      # LLM cleanup tests
├── test_config.py       # Config load/save tests
├── test_discovery.py    # Memo discovery tests
├── test_parser.py       # Parser and transcript extraction tests
├── test_state.py        # State store and hash tests
└── test_writer.py       # Markdown writer tests

docs/
├── GETTING_STARTED.md              # Full setup walkthrough
├── COMMANDS.md                     # CLI commands reference
├── CONFIGURATION.md                # All config options
├── USE_CASES.md                    # Transcription, LLM pipeline, workflows
├── TROUBLESHOOTING.md              # Common errors and fixes
├── CUSTOMIZING_LLM_INSTRUCTIONS.md # LLM prompt customization
├── DEVELOPMENT.md                  # This file
└── diagrams/                       # Mermaid.js architecture diagrams
    ├── README.md
    ├── export-sequence-diagram.md
    ├── data-flow-pipeline-diagram.md
    ├── export-decision-flowchart.md
    ├── core-data-model-class-diagram.md
    └── transcript-source-priority-diagram.md
```

---

## Architecture Overview

The export pipeline flows left to right:

```
Discovery -> State Check -> Parser -> [Whisper] -> [LLM Cleanup] -> Writer -> State Record
```

| Module | Responsibility |
|--------|---------------|
| `discovery.py` | Finds `.m4a` + `.composition` pairs, yields `MemoPair` objects |
| `state.py` | Checks if a memo needs exporting based on content hash and conflict policy |
| `parser.py` | Extracts `MemoMetadata` (title, dates, duration, transcript) from files |
| `transcribe.py` | Runs Whisper on memos without native transcripts |
| `cleanup.py` | Sends transcripts to Ollama for cleanup, titles, takeaways, domains |
| `writer.py` | Assembles Markdown with YAML frontmatter and writes to disk |
| `ollama.py` | Manages Ollama server lifecycle (start, check, preload) |
| `cli.py` | Wires everything together as Typer commands |
| `config.py` | Loads/saves `VMEAConfig` from TOML |

### Key Data Types

| Type | Module | Purpose |
|------|--------|---------|
| `MemoPair` | `discovery.py` | Audio path + composition path + memo ID |
| `MemoMetadata` | `parser.py` | All parsed data for one memo |
| `MemoState` | `state.py` | Export record (hash, paths, timestamp) |
| `StateStore` | `state.py` | JSONL-backed collection of `MemoState` records |
| `VMEAConfig` | `config.py` | All application settings (Pydantic model) |
| `CleanupResult` | `cleanup.py` | Single-pass LLM cleanup output |
| `CascadeCleanupResult` | `cleanup.py` | Multi-model cascade output |
| `DomainResult` | `cleanup.py` | Domain + sub-domain classification |

See [Architecture Diagrams](diagrams/README.md) for visual representations.

---

## Adding a New Command

1. Define the function in `cli.py` with the `@app.command()` decorator.
2. Use `get_config_or_exit()` to load config.
3. Follow the pattern of existing commands (e.g., `doctor`, `list_memos`).
4. Add tests in `tests/test_cli.py`.
5. Document in `docs/COMMANDS.md`.

## Adding a New Config Option

1. Add the field to `VMEAConfig` in `config.py`.
2. Update `render_config_content()` in `cli.py` if it should appear in generated configs.
3. Update `config.example.toml`.
4. Document in `docs/CONFIGURATION.md`.
5. Add tests in `tests/test_config.py`.
