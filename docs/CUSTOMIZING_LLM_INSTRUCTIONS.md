# Customizing LLM Instructions

VMEA uses a customizable instruction file to guide how the LLM processes your transcripts. This guide explains how to customize these instructions for your specific needs.

## Overview

The LLM instruction file tells Ollama exactly how to clean up, format, and enhance your voice memo transcripts. By customizing this file, you can:

- Change formatting rules (dates, times, numbers)
- Add domain-specific terminology handling
- Enable/disable specific cleanup behaviors
- Add custom output formatting (like Obsidian backlinks)
- Adjust the level of editorial intervention

## Default Instructions Location

VMEA includes a default instruction file at:
```
src/vmea/prompts/cleanup_instructions.md
```

## Setting Up Custom Instructions

### Step 1: Copy the Default File

```bash
# Create config directory if needed
mkdir -p ~/.config/vmea

# Copy default instructions
cp src/vmea/prompts/cleanup_instructions.md ~/.config/vmea/cleanup_instructions.md
```

### Step 2: Update Configuration

Edit `~/.config/vmea/config.toml`:

```toml
cleanup_instructions_path = "~/.config/vmea/cleanup_instructions.md"
```

### Step 3: Customize

Edit your custom file:

```bash
nano ~/.config/vmea/cleanup_instructions.md
# or
code ~/.config/vmea/cleanup_instructions.md
```

---

## Instruction File Structure

The default instruction file has several sections:

### 1. Role Definition

```markdown
You are a transcript editor. Your task is to clean up and improve a raw voice memo transcript.
```

This sets the LLM's persona and primary task.

### 2. Core Requirements

```markdown
You MUST make improvements to the transcript.
Do not return the original text unchanged.
```

These are non-negotiable behaviors.

### 3. Formatting Rules

```markdown
### Punctuation & Grammar
- Fix punctuation errors and add proper sentence endings
- Fix capitalization at sentence beginnings and for proper nouns
...
```

Specific instructions for how to handle text.

### 4. Output Requirements

```markdown
## Output Requirements
Return ONLY the cleaned transcript text. No explanations, no preamble...
```

How the output should be formatted.

---

## Customization Examples

### Example 1: Obsidian Integration

Add backlinks and wiki-style formatting:

```markdown
### Quality
- Add double brackets to key terms, eg; [[Key Term]]
- Connections between concepts being automatically generated, using backlinks
- Define key terms identified during transcription

### Obsidian Formatting
- Use `[[wikilinks]]` for important concepts
- Format tags as #tag-name
- Use callouts for important notes: `> [!note]`
```

### Example 2: Date/Time Formatting

Customize how dates and times appear:

```markdown
### Consistency
- Format numbers, dates, and times consistently
  - Date format: `yyyy-MM-dd`; eg. `2025-01-01`
  - Time format: `HH:MM`; eg. 23:00 -- use 24-hour time
```

Or for US-style formatting:
```markdown
### Consistency
- Format dates as: Month Day, Year (e.g., March 15, 2024)
- Format times in 12-hour format with AM/PM
```

### Example 3: Technical/Medical Transcripts

For specialized vocabulary:

```markdown
### Domain-Specific Rules
- Preserve medical terminology exactly as spoken
- Expand common medical abbreviations on first use: "BP (blood pressure)"
- Format drug names in Title Case
- Keep dosage information verbatim
```

### Example 4: Meeting Notes Style

```markdown
### Structure
- Format as meeting notes with clear sections
- Extract and list action items with assignees
- Summarize decisions made
- Use bullet points for discussion topics
```

### Example 5: Minimal Intervention

For transcripts that should stay close to the original:

```markdown
### Editing Approach
- Make ONLY essential corrections:
  - Fix obvious typos
  - Add basic punctuation
- Do NOT:
  - Reorganize content
  - Add paragraph breaks
  - Remove filler words
  - Change phrasing
```

---

## Cascade Mode Instructions

When using [cascade mode](GETTING_STARTED.md#cascade-mode), each model receives slightly modified instructions:

### Model 1 (Initial Cleanup)
Receives your custom instructions as-is.

### Model 2 (Revision)
Receives enhanced instructions focused on:
- Improving clarity and flow
- Fixing remaining errors
- Better paragraph structure

### Model 3 (Polish)
Receives instructions focused on:
- Professional quality
- Final consistency checks
- Maximum readability

You don't need to create separate files for each stage—VMEA handles this automatically.

---

## Fallback Search Order

VMEA looks for instruction files in this order:

1. **Explicit path** – `cleanup_instructions_path` in config.toml
2. **Output folder** – `cleanup_instructions.md` in your export folder
3. **Output folder** – `CLAUDE.md` in your export folder
4. **Output folder** – `GEMINI.md` in your export folder
5. **Output folder** – `README.md` in your export folder
6. **Built-in default** – Bundled with VMEA

This means you can also place a `cleanup_instructions.md` file in your output folder for project-specific instructions.

---

## Tips for Effective Instructions

### Be Specific

❌ "Fix the transcript"
✅ "Fix punctuation by adding periods at sentence ends and commas for natural pauses"

### Use Examples

```markdown
- Clean up false starts and self-corrections
  Example: "I went to the—I drove to the store" → "I drove to the store"
```

### State What NOT to Do

```markdown
You must NOT:
- Summarize or shorten the content
- Add information that wasn't spoken
- Change the speaker's meaning or intent
```

### Test Incrementally

1. Make one change at a time
2. Export a test memo
3. Review the results
4. Adjust as needed

---

## Troubleshooting

### Instructions Not Being Applied

1. Check the path in config:
   ```bash
   vmea config | grep cleanup_instructions
   ```

2. Verify the file exists:
   ```bash
   ls -la ~/.config/vmea/cleanup_instructions.md
   ```

3. Check file permissions:
   ```bash
   chmod 644 ~/.config/vmea/cleanup_instructions.md
   ```

### LLM Ignoring Instructions

- Instructions may be too complex—simplify
- Try using bullet points instead of paragraphs
- Add "IMPORTANT:" prefix to critical rules
- Test with a different model

### Output Has Unexpected Formatting

- Check for conflicting instructions
- Ensure "Return ONLY the cleaned transcript" is present
- Remove any markdown code block instructions if you don't want them

---

## Full Example: Custom Instructions

Here's a complete custom instruction file for journaling:

```markdown
# Transcript Cleanup Instructions

You are a transcript editor preparing voice journal entries.

## Core Task
Clean up the transcript while preserving the personal, reflective tone.

## Formatting Rules

### Punctuation
- Add proper sentence endings
- Use em-dashes (—) for pauses and asides
- Keep ellipses (...) for trailing thoughts

### Structure
- Add paragraph breaks for topic changes
- Keep single-paragraph entries for short thoughts
- Don't impose artificial structure

### Content Preservation
- Keep first-person perspective
- Preserve emotional expressions
- Keep informal language and colloquialisms
- Remove only excessive filler words

### Dates & Times
- Format dates as "Month Day, Year"
- Keep time references natural ("this morning", "around 3pm")

### Do NOT
- Add analysis or interpretation
- Change "I feel" statements
- Remove personal observations
- Add content not in the original

## Output
Return only the cleaned journal entry text.
```

---

## Related Documentation

- [Getting Started Guide](GETTING_STARTED.md)
- [Cascade Mode](GETTING_STARTED.md#cascade-mode)
- [Configuration Reference](../README.md#configuration)
