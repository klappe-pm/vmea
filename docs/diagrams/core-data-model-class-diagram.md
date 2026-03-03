# Core Data Model Class Diagram
## Summary
This class diagram describes the primary VMEA data structures and their relationships, including memo metadata, export state records, configuration, and LLM/transcription result models.

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
