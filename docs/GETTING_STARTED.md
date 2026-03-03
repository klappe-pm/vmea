# Getting Started with VMEA

This guide walks you through setting up and using VMEA (Voice Memo Export Automation) to export your Apple Voice Memos to organized markdown notes.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Initial Setup](#initial-setup)
4. [Your First Export](#your-first-export)
5. [Understanding the Output](#understanding-the-output)
6. [Configuring LLM Processing](#configuring-llm-processing)
7. [Cascade Mode](#cascade-mode)
8. [Watch Mode](#watch-mode)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before installing VMEA, ensure you have:

### Required

- **macOS 13+ (Ventura or later)**
- **Python 3.11 or higher**
  ```bash
  python3 --version  # Should show 3.11+
  ```
- **Voice Memos app** with at least one recording
- **Full Disk Access** permission for Terminal/your IDE

### Optional (for enhanced features)

- **Ollama** – Local LLM for transcript cleanup and enhancement
- **FFmpeg** – Required for Whisper transcription

### Granting Full Disk Access

VMEA needs to read Voice Memos from a protected system folder. To grant access:

1. Open **System Settings** → **Privacy & Security** → **Full Disk Access**
2. Click the **+** button
3. Add **Terminal** (or your terminal app: iTerm, Warp, VS Code, etc.)
4. Restart your terminal

---

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/klappe-pm/Apple-Voice-Memo-Export-to-Markdown.git
cd Apple-Voice-Memo-Export-to-Markdown
```

### Step 2: Create a Virtual Environment (Recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install VMEA

```bash
# Basic installation
pip install -e .

# With Whisper transcription support (for older memos)
pip install -e ".[transcribe]"

# With all features
pip install -e ".[transcribe,llm,dev]"
```

### Step 4: Verify Installation

```bash
vmea --version
vmea doctor
```

---

## Initial Setup

### Step 1: Run the Setup Wizard

```bash
vmea init
```

This interactive wizard will:

1. **Select output folder** – Where markdown notes will be saved
2. **Select audio folder** – Where audio files will be copied (optional)
3. **Detect Voice Memos** – Automatically find your Voice Memos folder
4. **Configure LLM** – Set up Ollama for transcript enhancement (optional)

### Step 2: Install Ollama (Optional but Recommended)

Ollama enables AI-powered features like transcript cleanup, title generation, and categorization.

```bash
# Install Ollama (macOS)
brew install ollama

# Or download from https://ollama.com

# Start Ollama
ollama serve

# Pull a model (in another terminal)
ollama pull llama3.2:3b
```

### Step 3: Verify Setup

```bash
vmea doctor
```

You should see green checkmarks for:
- ✓ Config found
- ✓ Voice Memos folder
- ✓ Output folder
- ✓ Python version

---

## Your First Export

### Basic Export

```bash
vmea export
```

You'll be prompted to:
1. Confirm or change the output folder
2. Choose whether to use cascade mode (multiple LLM models)
3. Select an Ollama model (if LLM is enabled)

### Preview Mode (Dry Run)

See what would be exported without making changes:

```bash
vmea export --dry-run
```

### Export a Single Memo

List available memos first:

```bash
vmea list
```

Then export a specific one:

```bash
vmea export --memo-id <id>
```

### Force Re-export

Re-export memos even if they haven't changed:

```bash
vmea export --force
```

---

## Understanding the Output

### File Naming Convention

```
YYYY-MM-DD-XX-descriptive-title.md
│    │  │  │   └── LLM-generated title slug
│    │  │  └────── Daily sequence (00, 01, 02...)
│    │  └───────── Day
│    └──────────── Month
└───────────────── Year
```

**Examples:**
- `2024-03-15-00-project-kickoff-meeting.md`
- `2024-03-15-01-afternoon-standup.md`

### Note Structure

Each exported note contains:

```yaml
---
domains: Technology
sub-domains: Software Development
llm-model: llama3.2:3b
date-created: 2024-03-15
date-revised: 2024-03-15
aliases:
tags:
---

# 2024-03-15-00-project-kickoff-meeting

## Voice Memo
![[Audio/2024-03-15-00-project-kickoff-meeting.m4a]]

## Key Takeaways
1. First key point...
2. Second key point...
...

### Revised Transcript
Cleaned up transcript with proper formatting...

### Original Transcript
Raw transcript from iOS/Whisper...
```

### Audio Files

Depending on your `audio_export_mode` setting:

| Mode | Result |
|------|--------|
| `copy` | Audio copied to `output_folder/Audio/` |
| `symlink` | Symlink created to original file |
| `app-link` | Clickable link to open Voice Memos app |

---

## Configuring LLM Processing

### Configuration File

Edit `~/.config/vmea/config.toml`:

```toml
# LLM cleanup settings
llm_cleanup_enabled = true
ollama_model = "llama3.2:3b"
ollama_models = []  # Empty = single model mode
ollama_host = "http://localhost:11434"
ollama_timeout = 120

# Custom instructions file (optional)
cleanup_instructions_path = ""
```

### Available Models

| Model | Speed | Quality | Best For |
|-------|-------|---------|----------|
| `llama3.2:1b` | ⚡⚡⚡⚡ | ★★★☆☆ | Quick processing |
| `llama3.2:3b` | ⚡⚡⚡ | ★★★★☆ | Balanced (default) |
| `llama3.1:8b` | ⚡⚡ | ★★★★★ | Higher quality |
| `mistral:7b` | ⚡⚡ | ★★★★★ | Alternative |

### Selecting Models Interactively

```bash
vmea ollama select
```

---

## Cascade Mode

Cascade mode runs your transcript through multiple LLM models sequentially for progressive refinement.

### How It Works

1. **Model 1 (Transcribe)**: Initial cleanup – fixes punctuation, removes filler words
2. **Model 2 (Revise)**: Enhancement – improves clarity, flow, and structure
3. **Model 3 (Polish)**: Final pass – ensures professional quality and consistency

### Enabling Cascade Mode

**During export:**
```bash
vmea export
# When prompted: "Use cascade mode?" → Yes
# Select 2-3 models
```

**In configuration:**
```toml
ollama_models = ["llama3.2:3b", "llama3.1:8b", "mistral:7b"]
```

### Cascade Mode Tips

- Use **faster models first** for initial cleanup
- Use **higher quality models** for final polish
- 2 models is often sufficient; 3 models for maximum quality
- Same model can be used multiple times for iterative refinement

---

## Watch Mode

Automatically export new Voice Memos as they're recorded.

### Foreground Watcher

```bash
vmea watch
# Press Ctrl+C to stop
```

### Background Daemon (launchd)

```bash
# Install as background service
vmea daemon install

# Check status
vmea daemon status

# Remove
vmea daemon uninstall
```

---

## Customizing LLM Instructions

VMEA uses a customizable instruction file for LLM processing. See [Customizing LLM Instructions](CUSTOMIZING_LLM_INSTRUCTIONS.md) for details.

Quick start:
```bash
# Copy default instructions to your config folder
cp src/vmea/prompts/cleanup_instructions.md ~/.config/vmea/

# Edit to your needs
nano ~/.config/vmea/cleanup_instructions.md

# Update config to use custom file
# In ~/.config/vmea/config.toml:
# cleanup_instructions_path = "~/.config/vmea/cleanup_instructions.md"
```

---

## Troubleshooting

### "Voice Memos folder not found"

1. **Open Voice Memos app** to trigger iCloud sync
2. **Grant Full Disk Access** (see [Prerequisites](#prerequisites))
3. Run `vmea doctor` to see which paths are checked

### "No transcript available"

For older memos without native transcription:
```bash
pip install -e ".[transcribe]"
```
Then set `transcribe_missing = true` in config.

### "Ollama not running"

```bash
# Start Ollama
vmea ollama start

# Or manually
ollama serve
```

### "Model not found"

```bash
# List available models
vmea ollama models

# Pull a model
vmea ollama pull llama3.2:3b
```

### Resetting State

If you need to re-export everything:

```bash
# Delete the state file
rm ~/path/to/output/.vmea-state.jsonl

# Re-export
vmea export
```

---

## Next Steps

- [Customizing LLM Instructions](CUSTOMIZING_LLM_INSTRUCTIONS.md) – Tailor transcript cleanup to your needs
- [Command Reference](../README.md#commands-reference) – Full list of commands
- [Configuration Options](../README.md#configuration) – All config settings

---

## Getting Help

- **Check system health:** `vmea doctor`
- **View current config:** `vmea config`
- **GitHub Issues:** [Report a bug](https://github.com/klappe-pm/Apple-Voice-Memo-Export-to-Markdown/issues)
