"""VMEA Cleanup – Local transcript cleanup via Ollama."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib import error, request

from vmea.ollama import is_ollama_running

# Path to bundled default instructions file
_DEFAULT_INSTRUCTIONS_PATH = Path(__file__).parent / "prompts" / "cleanup_instructions.md"

# Instruction file fallback order (after explicit path)
INSTRUCTION_FILE_FALLBACKS = ["cleanup_instructions.md", "CLAUDE.md", "GEMINI.md", "README.md"]


def _load_default_instructions() -> str:
    """Load default cleanup instructions from bundled file."""
    if _DEFAULT_INSTRUCTIONS_PATH.exists():
        return _DEFAULT_INSTRUCTIONS_PATH.read_text(encoding="utf-8").strip()
    # Fallback if file is missing (shouldn't happen in installed package)
    return """You are a transcript editor. Your task is to clean up and improve a raw voice memo transcript.
You MUST make improvements to the transcript. Do not return the original text unchanged.
Fix punctuation, grammar, and formatting. Remove filler words. Add paragraph breaks.
Return ONLY the cleaned transcript text."""


@dataclass
class CleanupResult:
    """Result of transcript cleanup with provenance."""

    revised_transcript: str
    instruction_source: str  # file path or "default"
    model: str


def resolve_instruction_file(
    explicit_path: Path | None,
    search_dir: Path | None = None,
    fail_on_missing: bool = False,
) -> tuple[str, str]:
    """Resolve instruction file using priority order.

    Priority:
    1. Explicit configured path
    2. CLAUDE.md in search_dir or cwd
    3. GEMINI.md in search_dir or cwd
    4. README.md in search_dir or cwd
    5. Built-in default

    Args:
        explicit_path: Explicitly configured instruction file path.
        search_dir: Directory to search for fallback files. Defaults to cwd.
        fail_on_missing: If True, raise error when no file found.

    Returns:
        Tuple of (instructions_content, source_path_or_"default").

    Raises:
        FileNotFoundError: If fail_on_missing and no file found.
    """
    search_dir = search_dir or Path.cwd()

    # Try explicit path first
    if explicit_path:
        resolved = explicit_path.expanduser()
        if resolved.exists():
            content = resolved.read_text(encoding="utf-8").strip()
            if content:
                return content, str(resolved)
        if fail_on_missing:
            raise FileNotFoundError(f"Instruction file not found: {explicit_path}")

    # Try fallback files
    for filename in INSTRUCTION_FILE_FALLBACKS:
        candidate = search_dir / filename
        if candidate.exists():
            content = candidate.read_text(encoding="utf-8").strip()
            if content:
                return content, str(candidate)

    if fail_on_missing:
        raise FileNotFoundError(
            f"No instruction file found. Searched: {explicit_path}, "
            f"{', '.join(INSTRUCTION_FILE_FALLBACKS)} in {search_dir}"
        )

    return _load_default_instructions(), str(_DEFAULT_INSTRUCTIONS_PATH)


def _call_ollama(
    prompt: str,
    system: str,
    model: str,
    host: str,
    timeout: int,
) -> str:
    """Make a request to Ollama API and return the response text."""
    if not is_ollama_running(host):
        raise RuntimeError(
            f"Ollama server is not running at {host}. "
            "Start with 'vmea ollama start' or 'ollama serve'"
        )

    payload = {
        "model": model,
        "stream": False,
        "system": system,
        "prompt": prompt,
    }
    body = json.dumps(payload).encode("utf-8")
    endpoint = host.rstrip("/") + "/api/generate"
    req = request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=timeout) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except error.URLError as exc:
        raise RuntimeError(f"Failed to reach Ollama at {endpoint}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Ollama returned invalid JSON") from exc

    return str(response_data.get("response", "")).strip()


def cleanup_transcript(
    transcript: str,
    model: str,
    host: str = "http://localhost:11434",
    timeout: int = 120,
    instructions_path: Path | None = None,
    search_dir: Path | None = None,
    fail_on_missing_instruction: bool = False,
) -> CleanupResult:
    """Send a transcript to Ollama for cleanup and return revised text with provenance."""
    instructions, instruction_source = resolve_instruction_file(
        instructions_path,
        search_dir=search_dir,
        fail_on_missing=fail_on_missing_instruction,
    )

    revised = _call_ollama(transcript, instructions, model, host, timeout)
    if not revised:
        raise RuntimeError("Ollama returned an empty transcript")

    return CleanupResult(
        revised_transcript=revised,
        instruction_source=instruction_source,
        model=model,
    )


@dataclass
class CascadeCleanupResult:
    """Result of cascading transcript cleanup across multiple models."""

    revised_transcript: str
    instruction_source: str
    models: list[str]  # Models used in order
    intermediate_results: list[str]  # Each model's output (for debugging/comparison)


# Type alias for progress callback
ProgressCallback = Callable[[int, int, str, str], None]  # (stage, total, model, status)


def cascade_cleanup_transcript(
    transcript: str,
    models: list[str],
    host: str = "http://localhost:11434",
    timeout: int = 120,
    instructions_path: Path | None = None,
    search_dir: Path | None = None,
    fail_on_missing_instruction: bool = False,
    progress_callback: ProgressCallback | None = None,
) -> CascadeCleanupResult:
    """Run transcript through multiple models sequentially for cascading improvement.

    Each model receives the output of the previous model, allowing for
    progressive refinement:
    - Model 1: Initial cleanup/transcription improvement
    - Model 2: Revision and enhancement
    - Model 3: Final polish and consistency check

    Args:
        transcript: Raw transcript text to clean up.
        models: List of Ollama model names to use in sequence (1-3 models).
        host: Ollama server URL.
        timeout: Request timeout per model in seconds.
        instructions_path: Optional path to custom instructions file.
        search_dir: Directory to search for fallback instruction files.
        fail_on_missing_instruction: Raise error if no instruction file found.
        progress_callback: Optional callback(stage, total, model, status) for progress updates.

    Returns:
        CascadeCleanupResult with final transcript and processing details.

    Raises:
        ValueError: If models list is empty.
        RuntimeError: If any model returns empty output.
    """
    if not models:
        raise ValueError("At least one model must be specified for cascade cleanup")

    instructions, instruction_source = resolve_instruction_file(
        instructions_path,
        search_dir=search_dir,
        fail_on_missing=fail_on_missing_instruction,
    )

    current_text = transcript
    intermediate_results: list[str] = []
    total_stages = len(models)
    stage_names = ["cleanup", "revise", "polish"]

    for i, model in enumerate(models):
        stage_name = stage_names[i] if i < len(stage_names) else f"stage-{i+1}"
        
        # Report progress: starting stage
        if progress_callback:
            progress_callback(i + 1, total_stages, model, f"starting {stage_name}")
        
        # Adjust system prompt for later stages to emphasize revision
        if i == 0:
            system_prompt = instructions
        elif i == 1:
            system_prompt = f"""You are revising a transcript that has already been cleaned up.
Review the text and make further improvements:
- Enhance clarity and flow
- Fix any remaining errors
- Improve paragraph structure
- Ensure consistency in formatting

{instructions}

Return ONLY the revised transcript text."""
        else:
            system_prompt = f"""You are doing a final polish on a revised transcript.
Make final refinements:
- Ensure professional quality
- Check for any remaining issues
- Verify formatting consistency
- Make the text as clear and readable as possible

{instructions}

Return ONLY the polished transcript text."""

        revised = _call_ollama(current_text, system_prompt, model, host, timeout)
        if not revised:
            raise RuntimeError(f"Model '{model}' returned an empty transcript at stage {i + 1}")

        intermediate_results.append(revised)
        current_text = revised
        
        # Report progress: completed stage
        if progress_callback:
            progress_callback(i + 1, total_stages, model, f"completed {stage_name}")

    return CascadeCleanupResult(
        revised_transcript=current_text,
        instruction_source=instruction_source,
        models=models,
        intermediate_results=intermediate_results,
    )


KEY_TAKEAWAYS_PROMPT = """You are analyzing a voice memo transcript.

Return exactly 5 key takeaways from this transcript.
Format each takeaway as a single concise sentence.
Number them 1 through 5.
Do not include any other text, just the 5 numbered takeaways.

Example format:
1. First key point from the memo.
2. Second key point from the memo.
3. Third key point from the memo.
4. Fourth key point from the memo.
5. Fifth key point from the memo.
"""


DOMAINS_PROMPT = """You are categorizing a voice memo transcript.

Analyze the transcript and determine the primary knowledge domain and sub-domain.

Return exactly 2 lines:
1. domain: [primary topic area, e.g., "Technology", "Business", "Personal", "Health", "Creative"]
2. sub-domain: [more specific topic, e.g., "Software Development", "Project Management", "Journal Entry"]

Be concise. Use title case. Do not include any other text.

Example output:
domain: Technology
sub-domain: Software Development
"""


def generate_key_takeaways(
    transcript: str,
    model: str,
    host: str = "http://localhost:11434",
    timeout: int = 120,
) -> list[str]:
    """Generate 5 key takeaways from a transcript using Ollama.

    Args:
        transcript: The transcript text to analyze.
        model: Ollama model name.
        host: Ollama server URL.
        timeout: Request timeout in seconds.

    Returns:
        List of 5 key takeaway strings.
    """
    response = _call_ollama(transcript, KEY_TAKEAWAYS_PROMPT, model, host, timeout)

    # Parse the numbered list from response
    takeaways = []
    for line in response.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # Remove leading number and punctuation (e.g., "1. ", "1) ", "1: ")
        if line[0].isdigit():
            # Find where the actual content starts
            for i, char in enumerate(line):
                if char.isalpha():
                    takeaways.append(line[i:].strip())
                    break
        else:
            takeaways.append(line)

    # Ensure we have exactly 5 (pad or truncate)
    while len(takeaways) < 5:
        takeaways.append("No additional takeaway available.")

    return takeaways[:5]


@dataclass
class DomainResult:
    """Result of domain categorization."""

    domain: str
    sub_domain: str


def generate_domains(
    transcript: str,
    model: str,
    host: str = "http://localhost:11434",
    timeout: int = 60,
) -> DomainResult:
    """Generate domain and sub-domain categorization from a transcript.

    Args:
        transcript: The transcript text to analyze.
        model: Ollama model name.
        host: Ollama server URL.
        timeout: Request timeout in seconds.

    Returns:
        DomainResult with domain and sub_domain fields.
    """
    response = _call_ollama(transcript, DOMAINS_PROMPT, model, host, timeout)

    domain = ""
    sub_domain = ""

    for line in response.strip().split("\n"):
        line = line.strip().lower()
        if line.startswith("domain:"):
            domain = line.replace("domain:", "").strip().title()
        elif line.startswith("sub-domain:") or line.startswith("subdomain:"):
            sub_domain = line.replace("sub-domain:", "").replace("subdomain:", "").strip().title()

    return DomainResult(domain=domain, sub_domain=sub_domain)


SUMMARY_PROMPT = """You are summarizing a voice memo transcript.

Write a concise summary (2-4 sentences) that captures the main topic, key points, and any action items or conclusions from this voice memo.

Rules:
- Be concise but informative
- Use complete sentences
- Focus on the most important content
- Do not use bullet points or numbered lists
- Do not include any preamble like "This voice memo is about..."

Return ONLY the summary text, nothing else.
"""


def generate_summary(
    transcript: str,
    model: str,
    host: str = "http://localhost:11434",
    timeout: int = 60,
) -> str:
    """Generate a brief summary of a transcript using LLM.

    Args:
        transcript: The transcript text to summarize.
        model: Ollama model name.
        host: Ollama server URL.
        timeout: Request timeout in seconds.

    Returns:
        A concise summary string.
    """
    response = _call_ollama(transcript, SUMMARY_PROMPT, model, host, timeout)
    return response.strip() if response else ""


FILENAME_TITLE_PROMPT = """You are generating a short filename-safe title for a voice memo.

Analyze the transcript and create a concise, descriptive title (2-5 words).

Rules:
- Use only lowercase letters, numbers, and hyphens
- No spaces, underscores, or special characters
- Maximum 40 characters
- Be descriptive but brief
- Do not include dates or generic words like "memo" or "recording"

Return ONLY the title, nothing else.

Examples:
- "project-kickoff-meeting"
- "weekly-standup-notes"
- "api-design-discussion"
- "birthday-party-planning"
- "code-review-feedback"
"""


def generate_filename_title(
    transcript: str,
    model: str,
    host: str = "http://localhost:11434",
    timeout: int = 60,
) -> str:
    """Generate a filename-safe title from a transcript using LLM.

    Args:
        transcript: The transcript text to analyze.
        model: Ollama model name.
        host: Ollama server URL.
        timeout: Request timeout in seconds.

    Returns:
        A slugified title suitable for use in filenames.
    """
    import re

    response = _call_ollama(transcript, FILENAME_TITLE_PROMPT, model, host, timeout)

    # Clean up the response
    title = response.strip().lower()

    # Remove any quotes that the LLM might have added
    title = title.strip('"\'')

    # Replace any remaining invalid characters with hyphens
    title = re.sub(r"[^a-z0-9-]", "-", title)

    # Collapse multiple hyphens
    title = re.sub(r"-+", "-", title)

    # Remove leading/trailing hyphens
    title = title.strip("-")

    # Truncate to max length
    if len(title) > 40:
        title = title[:40].rsplit("-", 1)[0]  # Cut at word boundary

    # Fallback if empty
    if not title:
        title = "voice-memo"

    return title
