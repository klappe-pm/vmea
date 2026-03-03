"""Tests for VMEA cleanup module."""

import json
from pathlib import Path

import pytest

from vmea.cleanup import CleanupResult, cleanup_transcript, resolve_instruction_file


class FakeResponse:
    """Minimal urllib response stub."""

    def __init__(self, payload: dict[str, str]) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_resolve_instruction_file_uses_default_when_path_missing(tmp_path: Path) -> None:
    # Use tmp_path as search_dir to avoid picking up project's README.md
    content, source = resolve_instruction_file(None, search_dir=tmp_path)
    assert "You are a transcript editor" in content
    assert source == "default"


def test_resolve_instruction_file_uses_explicit_path(tmp_path: Path) -> None:
    instruction_file = tmp_path / "custom.md"
    instruction_file.write_text("Custom instructions here")
    content, source = resolve_instruction_file(instruction_file)
    assert content == "Custom instructions here"
    assert source == str(instruction_file)


def test_resolve_instruction_file_fallback_chain(tmp_path: Path) -> None:
    # Create CLAUDE.md in search dir
    claude_file = tmp_path / "CLAUDE.md"
    claude_file.write_text("Instructions from CLAUDE.md")
    content, source = resolve_instruction_file(None, search_dir=tmp_path)
    assert content == "Instructions from CLAUDE.md"
    assert source == str(claude_file)


def test_cleanup_transcript_returns_cleanup_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_urlopen(req, timeout):  # type: ignore[no-untyped-def]
        assert req.full_url == "http://localhost:11434/api/generate"
        assert timeout == 120
        payload = json.loads(req.data.decode("utf-8"))
        assert payload["model"] == "llama3.2:3b"
        assert payload["prompt"] == "raw transcript"
        return FakeResponse({"response": "revised transcript"})

    monkeypatch.setattr("vmea.cleanup.request.urlopen", fake_urlopen)
    monkeypatch.setattr("vmea.cleanup.is_ollama_running", lambda h: True)

    # Use tmp_path to avoid picking up project's README.md
    result = cleanup_transcript("raw transcript", "llama3.2:3b", search_dir=tmp_path)
    assert isinstance(result, CleanupResult)
    assert result.revised_transcript == "revised transcript"
    assert result.model == "llama3.2:3b"
    assert result.instruction_source == "default"


def test_cleanup_transcript_raises_on_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "vmea.cleanup.request.urlopen",
        lambda req, timeout: FakeResponse({"response": "   "}),
    )
    monkeypatch.setattr("vmea.cleanup.is_ollama_running", lambda h: True)

    with pytest.raises(RuntimeError, match="empty transcript"):
        cleanup_transcript("raw transcript", "llama3.2:3b")


def test_cleanup_transcript_raises_when_ollama_not_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("vmea.cleanup.is_ollama_running", lambda h: False)

    with pytest.raises(RuntimeError, match="not running"):
        cleanup_transcript("raw transcript", "llama3.2:3b")
