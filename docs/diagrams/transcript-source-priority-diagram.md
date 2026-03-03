# Transcript Source Priority Diagram
## Summary
This diagram shows transcript source precedence: VMEA prefers native transcript data (`tsrp`, then `manifest.plist`) and falls back to local Whisper generation only when native sources are unavailable.

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
