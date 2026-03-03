# Export Decision Flowchart
## Summary
This flowchart shows the branching logic inside `export_memo()`, including state-based skip/re-export decisions, transcript availability checks, Whisper fallback, optional LLM steps (single or cascade), audio export mode handling, and state recording.

```mermaid
%%{init: {'theme': 'base'}}%%
flowchart TD
    START(["🚀 vmea export"]) --> PREPARE["_prepare_llm(config)"]
    PREPARE --> DISCOVER["discover_memos()"]
    DISCOVER --> LOOP{"More memos?"}
    
    LOOP -->|Yes| HASH["compute_source_hash()<br/>(chunked file hashing)"]
    HASH --> CHECK["should_export()"]
    CHECK --> SHOULD{"Should export?"}
    
    SHOULD -->|"No: unchanged"| SKIP["⏭️ Skip memo"]
    SHOULD -->|"No: skip_existing"| SKIP
    SKIP --> LOOP
    
    SHOULD -->|"Yes: new/changed/force"| PARSE["parse_memo()"]
    PARSE --> HAS_TRANS{"Has transcript?"}
    
    HAS_TRANS -->|No| WHISPER_CHECK{"transcribe_missing?"}
    WHISPER_CHECK -->|Yes| TRANSCRIBE["🎤 transcribe_if_needed()"]
    WHISPER_CHECK -->|No| LLM_CHECK
    TRANSCRIBE --> LLM_CHECK
    
    HAS_TRANS -->|Yes| LLM_CHECK{"LLM enabled?"}
    
    LLM_CHECK -->|Yes| GEN_TITLE["🏷️ generate_filename_title()"]
    GEN_TITLE --> CASCADE{"Cascade mode?"}
    CASCADE -->|Yes| CASCADE_CLEANUP["✨ cascade_cleanup_transcript()"]
    CASCADE -->|No| SINGLE_CLEANUP["✨ cleanup_transcript()"]
    CASCADE_CLEANUP --> TAKEAWAYS
    SINGLE_CLEANUP --> TAKEAWAYS
    TAKEAWAYS["📝 generate_key_takeaways()"] --> DOMAINS["🗂️ generate_domains()"]
    DOMAINS --> WRITE
    
    LLM_CHECK -->|No| WRITE["💾 write_note()"]
    
    WRITE --> AUDIO_MODE{"audio_export_mode?"}
    AUDIO_MODE -->|copy| COPY["📁 Copy Audio"]
    AUDIO_MODE -->|app-link| LINK["🔗 file:// Link"]
    AUDIO_MODE -->|symlink| SYM["↗️ Symlink"]
    
    COPY --> RECORD
    LINK --> RECORD
    SYM --> RECORD
    
    RECORD["📊 record_export()"] --> LOOP
    
    LOOP -->|No| DONE(["✅ Summary"])

    style START fill:#10b981,color:#fff,stroke:#059669
    style DONE fill:#10b981,color:#fff,stroke:#059669
    style TRANSCRIBE fill:#f59e0b,color:#fff,stroke:#d97706
    style GEN_TITLE fill:#8b5cf6,color:#fff,stroke:#7c3aed
    style CASCADE_CLEANUP fill:#8b5cf6,color:#fff,stroke:#7c3aed
    style SINGLE_CLEANUP fill:#8b5cf6,color:#fff,stroke:#7c3aed
    style TAKEAWAYS fill:#8b5cf6,color:#fff,stroke:#7c3aed
    style DOMAINS fill:#8b5cf6,color:#fff,stroke:#7c3aed
    style WRITE fill:#10b981,color:#fff,stroke:#059669
    style RECORD fill:#64748b,color:#fff,stroke:#475569
    style SKIP fill:#94a3b8,color:#fff
    style HASH fill:#64748b,color:#fff,stroke:#475569
```
