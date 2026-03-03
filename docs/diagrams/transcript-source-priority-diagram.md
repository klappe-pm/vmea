# Transcript Source Priority Diagram
## Summary
This diagram shows transcript source precedence controlled by `transcript_source_priority` in `VMEAConfig`. When set to `"both"` (default), VMEA prefers the `tsrp` atom (iOS 18+), then `manifest.plist` (iOS 17+), and falls back to local Whisper generation only when `transcribe_missing = true` and no native source is available.

```mermaid
%%{init: {'theme': 'base'}}%%
flowchart LR
    CONFIG["VMEAConfig<br/>transcript_source_priority"]

    subgraph Native["Native iOS Transcription"]
        TSRP["extract_tsrp_atom()<br/>tsrp atom in .m4a<br/>(iOS 18+ / macOS 15+)"]
        PLIST["extract_transcript_from_plist()<br/>manifest.plist<br/>(iOS 17+)"]
    end
    
    subgraph Generated["Generated Locally"]
        WHISPER["transcribe_if_needed()<br/>OpenAI Whisper<br/>(any memo, requires transcribe_missing=true)"]
    end

    CONFIG -->|"both / tsrp"| TSRP
    CONFIG -->|"both / plist"| PLIST
    
    TSRP -->|"Priority 1"| TRANSCRIPT
    PLIST -->|"Priority 2"| TRANSCRIPT
    WHISPER -->|"Fallback"| TRANSCRIPT
    TRANSCRIPT["📝 Final Transcript"]
    
    style CONFIG fill:#f1f5f9,stroke:#64748b,stroke-width:2px
    style Native fill:#d1fae5,stroke:#10b981,stroke-width:2px
    style Generated fill:#fef3c7,stroke:#f59e0b,stroke-width:2px
    style TSRP fill:#10b981,color:#fff
    style PLIST fill:#10b981,color:#fff
    style WHISPER fill:#f59e0b,color:#fff
    style TRANSCRIPT fill:#3b82f6,color:#fff
```
