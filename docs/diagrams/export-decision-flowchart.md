# Export Decision Flowchart
## Summary
This flowchart shows the branching logic used during export, including skip/re-export decisions, transcript availability checks, Whisper fallback, optional LLM steps, audio export mode handling, and state updates.

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
