# Troubleshooting

Common issues and how to resolve them.

---

## "Voice Memos folder not found"

VMEA looks for Voice Memos in Apple's iCloud sync folder under `~/Library/Group Containers/`. If it can't find the folder:

1. **Open the Voice Memos app** on your Mac to trigger iCloud sync.
2. **Grant Full Disk Access** to your terminal app:
   - System Settings > Privacy & Security > Full Disk Access
   - Add Terminal (or iTerm, Warp, VS Code, etc.)
   - Restart the terminal after granting access.
3. Run `vmea doctor` to see exactly which paths are being checked.
4. If the folder is in a non-standard location, set `source_path_override` in your config:
   ```toml
   source_path_override = "/path/to/your/Voice Memos"
   ```

---

## "No transcript available"

Some older Voice Memos don't have a native iOS transcript. You have two options:

**Option A: Enable Whisper transcription**

```bash
pip install -e ".[transcribe]"
```

Then ensure your config has:

```toml
transcribe_missing = true
whisper_model = "base"   # or "small", "medium", "large" for better quality
```

**Option B: Export without transcripts**

Memos without transcripts are still exported; the transcript sections will show placeholder text.

---

## "Whisper not installed"

```bash
pip install -e ".[transcribe]"
```

Whisper also requires **FFmpeg**:

```bash
brew install ffmpeg
```

---

## "Ollama not running"

VMEA needs Ollama for LLM features. Start it with:

```bash
vmea ollama start
# or manually:
ollama serve
```

If Ollama isn't installed:

```bash
brew install ollama
# or download from https://ollama.com
```

After starting, pull a model:

```bash
ollama pull llama3.2:3b
```

---

## "Model not found"

The configured model may not be downloaded yet.

```bash
# List locally available models
vmea ollama models

# Pull the model you need
vmea ollama pull llama3.2:3b
```

Then update your config if needed:

```toml
ollama_model = "llama3.2:3b"
```

---

## LLM returns empty or poor results

- **Increase timeout** if the model is timing out:
  ```toml
  ollama_timeout = 300
  ```
- **Try a larger model** for better quality:
  ```toml
  ollama_model = "llama3.1:8b"
  ```
- **Use cascade mode** for progressive refinement:
  ```toml
  ollama_models = ["llama3.2:3b", "llama3.1:8b"]
  ```
- **Customize instructions** -- see [Customizing LLM Instructions](CUSTOMIZING_LLM_INSTRUCTIONS.md).

---

## Duplicate or missing exports

VMEA tracks state in a JSONL file inside your output folder (`.vmea-state.jsonl`).

### Reset all state (full re-export)

```bash
rm ~/path/to/output/.vmea-state.jsonl
vmea export
```

### Re-export a single memo

```bash
vmea export --memo-id <id> --force
```

### Retry failed exports

```bash
vmea retry-failed
```

---

## Watch mode not detecting new memos

- Make sure `vmea watch` is running in a terminal (or the daemon is installed).
- New memos may take a few seconds to appear due to the debounce delay (`watch_debounce_seconds`, default 5).
- Check that Full Disk Access is granted for the process running VMEA.

---

## Config file issues

### View current config

```bash
vmea config
```

### Re-run setup

```bash
vmea init
```

This will prompt you to overwrite the existing config.

### Legacy enum values

If you see errors about invalid enum values (e.g., `TranscriptSource.BOTH`), VMEA automatically migrates these on load. If problems persist, delete `~/.config/vmea/config.toml` and re-run `vmea init`.

---

## Getting Help

- **System diagnostics:** `vmea doctor`
- **View current config:** `vmea config`
- **GitHub Issues:** [Report a bug](https://github.com/klappe-pm/Apple-Voice-Memo-Export-to-Markdown/issues)
