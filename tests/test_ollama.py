"""Tests for VMEA Ollama lifecycle management module."""

import json

import pytest

from vmea.ollama import (
    ensure_ready,
    is_ollama_installed,
    is_ollama_running,
    list_models,
    preload_model,
    start_ollama,
)


class FakeResponse:
    """Minimal urllib response stub."""

    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_is_ollama_installed_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vmea.ollama.shutil.which", lambda _x: "/usr/local/bin/ollama")
    assert is_ollama_installed() is True


def test_is_ollama_installed_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vmea.ollama.shutil.which", lambda _x: None)
    assert is_ollama_installed() is False


def test_is_ollama_running_true(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(_req, _timeout):  # type: ignore[no-untyped-def]
        return FakeResponse({"models": []})

    monkeypatch.setattr("vmea.ollama.request.urlopen", fake_urlopen)
    assert is_ollama_running() is True


def test_is_ollama_running_false_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(_req, _timeout):  # type: ignore[no-untyped-def]
        raise ConnectionRefusedError("Connection refused")

    monkeypatch.setattr("vmea.ollama.request.urlopen", fake_urlopen)
    assert is_ollama_running() is False


def test_list_models_returns_model_names(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(_req, _timeout):  # type: ignore[no-untyped-def]
        return FakeResponse({
            "models": [
                {"name": "llama3.2:3b", "size": 2000000000},
                {"name": "mistral:7b", "size": 4000000000},
            ]
        })

    monkeypatch.setattr("vmea.ollama.request.urlopen", fake_urlopen)
    monkeypatch.setattr("vmea.ollama.is_ollama_running", lambda _h: True)

    models, err = list_models()
    assert err is None
    assert models == ["llama3.2:3b", "mistral:7b"]


def test_list_models_returns_error_when_not_running(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vmea.ollama.is_ollama_running", lambda _h: False)

    models, err = list_models()
    assert models == []
    assert err == "Ollama server is not running"


def test_preload_model_success(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(req, _timeout):  # type: ignore[no-untyped-def]
        payload = json.loads(req.data.decode("utf-8"))
        assert payload["model"] == "llama3.2:3b"
        assert payload["prompt"] == "Hello"
        return FakeResponse({"response": "Hi there!"})

    monkeypatch.setattr("vmea.ollama.request.urlopen", fake_urlopen)
    monkeypatch.setattr("vmea.ollama.is_ollama_running", lambda _h: True)

    success, err = preload_model("llama3.2:3b")
    assert success is True
    assert err is None


def test_preload_model_fails_when_not_running(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vmea.ollama.is_ollama_running", lambda _h: False)

    success, err = preload_model("llama3.2:3b")
    assert success is False
    assert err == "Ollama server is not running"


def test_start_ollama_already_running(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vmea.ollama.is_ollama_installed", lambda: True)
    monkeypatch.setattr("vmea.ollama.is_ollama_running", lambda _h: True)

    success, err = start_ollama()
    assert success is True
    assert err is None


def test_start_ollama_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vmea.ollama.is_ollama_installed", lambda: False)

    success, err = start_ollama()
    assert success is False
    assert "not installed" in err


def test_ensure_ready_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vmea.ollama.is_ollama_installed", lambda: True)
    monkeypatch.setattr("vmea.ollama.is_ollama_running", lambda _h: True)
    monkeypatch.setattr("vmea.ollama.list_models", lambda _h: (["llama3.2:3b"], None))
    monkeypatch.setattr("vmea.ollama.preload_model", lambda _m, _h: (True, None))

    status = ensure_ready("llama3.2:3b")
    assert status.running is True
    assert status.error is None
    assert "llama3.2:3b" in status.models


def test_ensure_ready_model_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vmea.ollama.is_ollama_installed", lambda: True)
    monkeypatch.setattr("vmea.ollama.is_ollama_running", lambda _h: True)
    monkeypatch.setattr("vmea.ollama.list_models", lambda _h: (["mistral:7b"], None))

    status = ensure_ready("llama3.2:3b")
    assert status.running is True
    assert "not found" in status.error
    assert "mistral:7b" in status.error


def test_ensure_ready_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vmea.ollama.is_ollama_installed", lambda: False)

    status = ensure_ready("llama3.2:3b")
    assert status.running is False
    assert "not installed" in status.error
