"""Tests for VMEA cleanup module."""

import json

import pytest

from vmea.cleanup import cleanup_transcript, load_cleanup_instructions


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


def test_load_cleanup_instructions_uses_default_when_path_missing() -> None:
    assert "Return only the revised transcript text." in load_cleanup_instructions(None)


def test_cleanup_transcript_returns_ollama_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(req, timeout):  # type: ignore[no-untyped-def]
        assert req.full_url == "http://localhost:11434/api/generate"
        assert timeout == 120
        payload = json.loads(req.data.decode("utf-8"))
        assert payload["model"] == "llama3.2:3b"
        assert payload["prompt"] == "raw transcript"
        return FakeResponse({"response": "revised transcript"})

    monkeypatch.setattr("vmea.cleanup.request.urlopen", fake_urlopen)

    assert cleanup_transcript("raw transcript", "llama3.2:3b") == "revised transcript"


def test_cleanup_transcript_raises_on_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "vmea.cleanup.request.urlopen",
        lambda req, timeout: FakeResponse({"response": "   "}),
    )

    with pytest.raises(RuntimeError, match="empty transcript"):
        cleanup_transcript("raw transcript", "llama3.2:3b")
