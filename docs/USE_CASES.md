# Use Cases & LLM Processing

How VMEA handles transcription sources, what the LLM pipeline does, and common workflows.

---

## Transcription Sources

VMEA can extract transcripts from three sources, tried in priority order:

| Source | Format | Availability | Priority |
|--------|--------|-------------|----------|
| `tsrp` | JSON atom embedded in `.m4a` | iOS 18+ / macOS 15+ | 1 (highest) |
| `plist` | `manifest.plist` in `.composition` folder | iOS 17+ | 2 |
| `whisper` | Generated locally via OpenAI Whisper | Any memo | 3 (fallback) |

The `transcript_source_priority` config controls which native sources are tried:

- **`both`** (default) -- try `tsrp` first, then `plist`
- **`tsrp`** -- only use the embedded atom
- **`plist`** -- only use the plist file

If no native transcript is found and `transcribe_missing = true`, VMEA runs Whisper locally to generate one.

### How each source works

**tsrp atom** -- iOS 18+ embeds a JSON transcript directly inside the `.m4a` file as a custom MP4 atom. VMEA reads the raw bytes, locates the `tsrp` marker, and parses the JSON to extract text from `attributedString.runs`.

**manifest.plist** -- iOS 17+ stores metadata (title, dates, duration, transcript) in a binary plist inside a `.composition` folder alongside each `.m4a`. VMEA uses Python's `plistlib` to parse it and extracts transcript text from various nested structures.

**Whisper** -- When neither native source is available, VMEA uses OpenAI's Whisper speech-to-text model to transcribe the audio locally. Install with `pip install -e ".[transcribe]"`.

---

## LLM Processing Pipeline

When `llm_cleanup_enabled = true` and a transcript is available, VMEA sends it through four LLM tasks via Ollama:

### 1. Filename Title Generation

Creates a short, filename-safe slug (2-5 words, lowercase, hyphenated).

**Input:** Raw transcript  
**Output:** e.g., `project-kickoff-meeting`  
**Used in:** `YYYY-MM-DD-XX-<title>.md`

### 2. Transcript Cleanup

Cleans up the raw transcript for readability. In single-model mode, one pass is made. In cascade mode, up to three models process the text sequentially.

**What cleanup does:**
- Fix punctuation and capitalization
- Improve paragraph breaks
- Correct obvious transcription errors
- Apply consistent formatting
- Add Obsidian backlinks to key terms (customizable)

**What cleanup does NOT do:**
- Summarize or shorten content
- Add information not present in the original
- Interpret or editorialize
- Change the speaker's meaning

### 3. Key Takeaways

Extracts exactly 5 key points from the transcript.

**Output format:**
```
1. First key point from the memo.
2. Second key point from the memo.
3. Third key point from the memo.
4. Fourth key point from the memo.
5. Fifth key point from the memo.
```

### 4. Domain Categorization

Classifies the memo into a domain and sub-domain for YAML frontmatter.

**Output example:**
```yaml
domains: Technology
sub-domains: Software Development
```

---

## Cascade Mode

Cascade mode runs the transcript cleanup through multiple models sequentially. Each model refines the previous model's output.

```toml
ollama_models = ["llama3.2:3b", "llama3.1:8b", "mistral:7b"]
```

| Stage | Role | System Prompt |
|-------|------|---------------|
| 1 | Initial cleanup | Uses the configured instruction file as-is |
| 2 | Revision | Adds emphasis on clarity, flow, and paragraph structure |
| 3 | Polish | Adds emphasis on professional quality and consistency |

The first model in the list is also used for the auxiliary tasks (title, takeaways, domains).

**Tips:**
- Use faster/smaller models first for bulk cleanup
- Use larger models for the final polish
- 2 models is often sufficient; 3 for maximum quality
- The same model can appear more than once for iterative refinement

---

## Customizing LLM Behavior

The system prompt sent to Ollama during cleanup is fully customizable:

```bash
# Copy the default instructions
cp src/vmea/prompts/cleanup_instructions.md ~/.config/vmea/

# Point your config at the custom file
# In ~/.config/vmea/config.toml:
cleanup_instructions_path = "~/.config/vmea/cleanup_instructions.md"
```

See [Customizing LLM Instructions](CUSTOMIZING_LLM_INSTRUCTIONS.md) for a detailed guide.

---

## Common Workflows

### Basic: Export all memos once

```bash
vmea init       # Configure paths and model
vmea export     # Process all memos
```

### With Whisper for older memos

```bash
pip install -e ".[transcribe]"
# Set transcribe_missing = true in config
vmea export
```

### Continuous processing

```bash
# Foreground watcher
vmea watch

# Or install as a background service
vmea daemon install
```

### Re-process with a different model

```bash
# Delete state to force re-export
rm ~/path/to/output/.vmea-state.jsonl

# Update model in config, then:
vmea export
```

### Dry run to preview

```bash
vmea export --dry-run
```

### Single memo export

```bash
vmea list                          # Find the memo ID
vmea export --memo-id <id>         # Export just that one
vmea export --memo-id <id> --force # Force re-export
```
