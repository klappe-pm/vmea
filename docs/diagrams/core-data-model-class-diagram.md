# Core Data Model Class Diagram
## Summary
This class diagram describes the primary VMEA data structures and their relationships, including memo metadata, export state records, configuration enums (StrEnum-based), and LLM/transcription result models.

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
        +str|None title
        +datetime|None created
        +datetime|None modified
        +float|None duration_seconds
        +str|None transcript
        +str|None revised_transcript
        +str|None transcript_source
        +str|None custom_label
        +bool is_favorited
        +dict raw_plist
    }

    class MemoState {
        +str memo_id
        +str source_hash
        +str note_path
        +str|None audio_path
        +str exported_at
        +str|None source_modified
        +str|None transcript_source
        +int export_version
        +str|None error
    }

    class StateStore {
        +Path path
        -dict _records
        +get(memo_id) MemoState|None
        +set(record) void
        +remove(memo_id) bool
        +all() Iterator~MemoState~
        +compact() int
        +__len__() int
        +__contains__(memo_id) bool
    }

    class VMEAConfig {
        +Path output_folder
        +Path|None audio_output_folder
        +AudioExportMode audio_export_mode
        +TranscriptSource transcript_source_priority
        +ConflictResolution conflict_resolution
        +bool llm_cleanup_enabled
        +str ollama_model
        +list~str~ ollama_models
        +str whisper_model
        +bool transcribe_missing
        +int watch_debounce_seconds
    }

    class AudioExportMode {
        <<StrEnum>>
        COPY
        SYMLINK
        SOURCE_LINK
        APP_LINK
    }

    class TranscriptSource {
        <<StrEnum>>
        PLIST
        TSRP
        BOTH
    }

    class ConflictResolution {
        <<StrEnum>>
        SKIP
        UPDATE
        OVERWRITE
    }

    class CleanupResult {
        +str revised_transcript
        +str instruction_source
        +str model
    }

    class CascadeCleanupResult {
        +str revised_transcript
        +str instruction_source
        +list~str~ models
        +list~str~ intermediate_results
    }

    class DomainResult {
        +str domain
        +str sub_domain
    }

    MemoPair --> MemoMetadata : parse_memo()
    MemoMetadata --> MemoState : record_export()
    StateStore --> MemoState : manages
    VMEAConfig --> AudioExportMode : uses
    VMEAConfig --> TranscriptSource : uses
    VMEAConfig --> ConflictResolution : uses
    CleanupResult --|> CascadeCleanupResult : cascade extends

    style MemoPair fill:#dbeafe,stroke:#3b82f6
    style MemoMetadata fill:#dbeafe,stroke:#3b82f6
    style MemoState fill:#f1f5f9,stroke:#64748b
    style StateStore fill:#f1f5f9,stroke:#64748b
    style VMEAConfig fill:#f1f5f9,stroke:#64748b
    style AudioExportMode fill:#f1f5f9,stroke:#64748b
    style TranscriptSource fill:#f1f5f9,stroke:#64748b
    style ConflictResolution fill:#f1f5f9,stroke:#64748b
    style CleanupResult fill:#ede9fe,stroke:#8b5cf6
    style CascadeCleanupResult fill:#ede9fe,stroke:#8b5cf6
    style DomainResult fill:#ede9fe,stroke:#8b5cf6
```
