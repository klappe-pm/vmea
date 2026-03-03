# Data Flow Pipeline Diagram
## Summary
This diagram explains how memo data flows through VMEA: source files are parsed by `parser.py`, transcripts are resolved (native `tsrp`/`plist` or Whisper fallback), optional LLM enrichment is applied via `cleanup.py`, and final markdown/audio outputs are written by `writer.py` and tracked in `state.py`.

```mermaid
%%{init: {'theme': 'base'}}%%
flowchart TB
    subgraph Input["📥 Input Sources (discovery.py)"]
        VM[("Voice Memos<br/>~/Library/Group Containers/")]
        M4A["🎵 .m4a audio files"]
        COMP["📋 .composition/manifest.plist"]
        VM --> M4A
        VM --> COMP
    end

    subgraph Parse["📖 Parsing (parser.py)"]
        PARSER["parse_memo()<br/>Extract MemoMetadata"]
        TSRP["extract_tsrp_atom()"]
        PLIST["extract_transcript_from_plist()"]
        META["MemoMetadata"]
        M4A --> PARSER
        COMP --> PARSER
        M4A --> TSRP
        COMP --> PLIST
        TSRP --> META
        PLIST --> META
        PARSER --> META
    end

    subgraph Transcribe["🎤 Transcription (transcribe.py)"]
        NATIVE{"Has native<br/>transcript?"}
        WHISPER["transcribe_if_needed()<br/>Whisper Speech-to-Text"]
        TRANS["Transcript Text"]
        META --> NATIVE
        NATIVE -->|No| WHISPER
        NATIVE -->|Yes| TRANS
        WHISPER --> TRANS
    end

    subgraph LLM["🤖 LLM Enhancement (cleanup.py)"]
        TITLE["generate_filename_title()"]
        CLEANUP["cleanup_transcript() /<br/>cascade_cleanup_transcript()"]
        TAKEAWAY["generate_key_takeaways()"]
        DOMAIN["generate_domains()"]
        TRANS --> TITLE
        TRANS --> CLEANUP
        TRANS --> TAKEAWAY
        TRANS --> DOMAIN
    end

    subgraph Output["📤 Output (writer.py + state.py)"]
        WRITE["write_note()"]
        MD["📝 Markdown Note<br/>YYYY-MM-DD-XX-title.md"]
        AUDIO["🔊 Audio File<br/>(copy/symlink/app-link)"]
        STATE[("StateStore<br/>.vmea-state.jsonl")]
        TITLE --> WRITE
        CLEANUP --> WRITE
        TAKEAWAY --> WRITE
        DOMAIN --> WRITE
        WRITE --> MD
        WRITE --> AUDIO
        MD --> STATE
    end

    style Input fill:#dbeafe,stroke:#3b82f6,stroke-width:2px
    style Parse fill:#dbeafe,stroke:#3b82f6,stroke-width:2px
    style Transcribe fill:#fef3c7,stroke:#f59e0b,stroke-width:2px
    style LLM fill:#ede9fe,stroke:#8b5cf6,stroke-width:2px
    style Output fill:#d1fae5,stroke:#10b981,stroke-width:2px
    style WHISPER fill:#f59e0b,color:#fff
    style TITLE fill:#8b5cf6,color:#fff
    style CLEANUP fill:#8b5cf6,color:#fff
    style TAKEAWAY fill:#8b5cf6,color:#fff
    style DOMAIN fill:#8b5cf6,color:#fff
    style STATE fill:#64748b,color:#fff
```
