# Architecture Diagrams

Mermaid.js diagrams showing how VMEA's modules and data structures fit together. Each file includes a summary and a renderable Mermaid code block.

## Color Legend

| Color | Meaning |
|-------|--------|
| 🟦 Blue (`#3b82f6`) | Input / Source data |
| 🟨 Amber (`#f59e0b`) | Whisper transcription |
| 🟪 Purple (`#8b5cf6`) | LLM / Ollama processing |
| 🟩 Green (`#10b981`) | Output / Write operations |
| ⬜ Slate (`#64748b`) | State / Storage / Config |

## Diagram Files

| Diagram | What it shows |
|---------|--------------|
| [Export Sequence Diagram](export-sequence-diagram.md) | End-to-end runtime sequence of `vmea export`, including `export_memo()` |
| [Data Flow Pipeline Diagram](data-flow-pipeline-diagram.md) | How data flows from source files through parsing, transcription, LLM, and output |
| [Export Decision Flowchart](export-decision-flowchart.md) | Branching logic: state checks, Whisper fallback, single vs. cascade LLM, audio modes |
| [Core Data Model Class Diagram](core-data-model-class-diagram.md) | Key data structures (`MemoMetadata`, `StateStore`, `VMEAConfig`, StrEnum configs) |
| [Transcript Source Priority Diagram](transcript-source-priority-diagram.md) | Transcript source precedence (`tsrp` > `plist` > Whisper) |

## Related Documentation

- [Configuration](../CONFIGURATION.md) -- all config options
- [Use Cases & LLM Processing](../USE_CASES.md) -- how the LLM pipeline works
- [Development](../DEVELOPMENT.md) -- project structure and architecture overview
