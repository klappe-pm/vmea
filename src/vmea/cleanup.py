"""VMEA Cleanup – Local transcript cleanup via Ollama."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional
from urllib import error, request


DEFAULT_CLEANUP_INSTRUCTIONS = """You are revising a raw voice memo transcript.

Return only the revised transcript text.
Preserve the speaker's meaning, order, tone, and first-person perspective.
Fix obvious speech-to-text mistakes, punctuation, capitalization, and paragraph breaks.
Do not summarize. Do not omit details. Do not add facts that are not present.
If a phrase is unclear, keep it close to the original wording instead of guessing.
"""


def load_cleanup_instructions(path: Optional[Path]) -> str:
    """Load cleanup instructions from disk, or use the built-in default."""
    if path and path.exists():
        content = path.read_text(encoding="utf-8").strip()
        if content:
            return content
    return DEFAULT_CLEANUP_INSTRUCTIONS


def cleanup_transcript(
    transcript: str,
    model: str,
    host: str = "http://localhost:11434",
    timeout: int = 120,
    instructions_path: Optional[Path] = None,
) -> str:
    """Send a transcript to Ollama for cleanup and return revised text."""
    instructions = load_cleanup_instructions(instructions_path)
    payload = {
        "model": model,
        "stream": False,
        "system": instructions,
        "prompt": transcript,
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
    except error.URLError as exc:  # pragma: no cover - network failure surface
        raise RuntimeError(f"Failed to reach Ollama at {endpoint}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:  # pragma: no cover - malformed response surface
        raise RuntimeError("Ollama returned invalid JSON") from exc

    revised = str(response_data.get("response", "")).strip()
    if not revised:
        raise RuntimeError("Ollama returned an empty transcript")
    return revised
