# Export Sequence Diagram
## Summary
This diagram shows the end-to-end runtime sequence of `vmea export`, including memo discovery, state checks, transcript extraction/transcription, LLM enrichment, note writing, and state recording. The `export_memo()` function encapsulates the per-memo pipeline and is called directly by `export`, `watch`, and `retry-failed`.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#3b82f6', 'secondaryColor': '#f59e0b', 'tertiaryColor': '#8b5cf6'}}}%%
sequenceDiagram
    participant User
    participant CLI as CLI (export)
    participant Discovery
    participant ExportMemo as export_memo()
    participant Parser
    participant Whisper
    participant Ollama as Ollama (cleanup.py)
    participant Writer
    participant State as StateStore

    rect rgb(59, 130, 246, 0.1)
        Note over User,State: Initialization
        User->>CLI: vmea export [--dry-run] [--force] [--memo-id]
        CLI->>Discovery: find_source_path()
        Discovery-->>CLI: Voice Memos folder
        CLI->>Discovery: discover_memos()
        Discovery-->>CLI: List of MemoPairs
        CLI->>CLI: _prepare_llm(config)
        CLI-->>CLI: (llm_enabled, models, use_cascade)
    end
    
    loop For each MemoPair
        CLI->>ExportMemo: export_memo(memo_pair, config, ...)

        rect rgb(100, 116, 139, 0.1)
            Note over ExportMemo,State: State Check
            ExportMemo->>State: compute_source_hash(audio, composition)
            ExportMemo->>State: should_export(memo_id, hash)
            State-->>ExportMemo: (yes/no, reason)
        end
        
        alt Should export (or --force)
            rect rgb(59, 130, 246, 0.1)
                Note over ExportMemo,Parser: Parse
                ExportMemo->>Parser: parse_memo(audio, composition, memo_id, priority)
                Parser-->>ExportMemo: MemoMetadata
            end
            
            alt No transcript & transcribe_missing=true
                rect rgb(245, 158, 11, 0.1)
                    Note over ExportMemo,Whisper: Transcription
                    ExportMemo->>Whisper: transcribe_if_needed()
                    Whisper-->>ExportMemo: transcript text + source
                end
            end
            
            alt LLM enabled & has transcript
                rect rgb(139, 92, 246, 0.1)
                    Note over ExportMemo,Ollama: LLM Enhancement
                    ExportMemo->>Ollama: generate_filename_title()
                    Ollama-->>ExportMemo: "project-kickoff"
                    ExportMemo->>Ollama: cleanup_transcript() or cascade_cleanup_transcript()
                    Ollama-->>ExportMemo: revised transcript
                    ExportMemo->>Ollama: generate_key_takeaways()
                    Ollama-->>ExportMemo: 5 takeaways
                    ExportMemo->>Ollama: generate_domains()
                    Ollama-->>ExportMemo: DomainResult(domain, sub_domain)
                end
            end
            
            rect rgb(16, 185, 129, 0.1)
                Note over ExportMemo,State: Output
                ExportMemo->>Writer: write_note()
                Writer-->>ExportMemo: (note_path, audio_path)
                ExportMemo->>State: record_export()
            end
        end

        ExportMemo-->>CLI: "created" | "skipped" | "failed"
    end
    
    CLI-->>User: Summary (created/skipped/failed)
```
