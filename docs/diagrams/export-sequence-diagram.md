# Export Sequence Diagram
## Summary
This diagram shows the end-to-end runtime sequence of `vmea export`, including memo discovery, state checks, transcript extraction/transcription, LLM enrichment, note writing, and state recording.

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
