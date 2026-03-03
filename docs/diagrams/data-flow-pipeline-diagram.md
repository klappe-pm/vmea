# Data Flow Pipeline Diagram
## Summary
This diagram explains how memo data flows through VMEA: source files are parsed, transcripts are resolved (native or Whisper), optional LLM enrichment is applied, and final markdown/audio outputs are written and tracked in state.

```mermaid
%%{init: {'theme': 'base'}}%%
flowchart TB
    subgraph Input["📥 Input Sources"]
        VM[("Voice Memos<br/>~/Library/Group Containers/")]
        M4A["🎵 .m4a audio files"]
        COMP["📋 .composition metadata"]
        VM --> M4A
        VM --> COMP
    end

    subgraph Parse["📖 Parsing"]
        PARSER["Parser Module<br/>Extract metadata"]
        META["MemoMetadata"]
        M4A --> PARSER
        COMP --> PARSER
        PARSER --> META
    end

    subgraph Transcribe["🎤 Transcription"]
        NATIVE{"Has native<br/>transcript?"}
        WHISPER["Whisper<br/>Speech-to-Text"]
        TRANS["Transcript Text"]
        META --> NATIVE
        NATIVE -->|No| WHISPER
        NATIVE -->|Yes| TRANS
        WHISPER --> TRANS
    end

    subgraph LLM["🤖 LLM Enhancement"]
        TITLE["Generate Title"]
        CLEANUP["Cleanup Transcript"]
        TAKEAWAY["Key Takeaways"]
        DOMAIN["Domain Classification"]
        TRANS --> TITLE
        TRANS --> CLEANUP
        TRANS --> TAKEAWAY
        TRANS --> DOMAIN
    end

    subgraph Output["📤 Output"]
        WRITE["Writer Module"]
        MD["📝 Markdown Note"]
        AUDIO["🔊 Audio File"]
        STATE[("State Store")]
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
