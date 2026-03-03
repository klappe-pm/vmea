"""VMEA Ollama – Lifecycle management for local Ollama server."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from urllib import error, request


@dataclass
class OllamaStatus:
    """Status of the Ollama server."""

    running: bool
    host: str
    models: list[str]
    error: str | None = None


def is_ollama_installed() -> bool:
    """Check if the Ollama CLI is installed."""
    return shutil.which("ollama") is not None


def is_ollama_running(host: str = "http://localhost:11434") -> bool:
    """Check if the Ollama server is responding.

    Args:
        host: Ollama server URL.

    Returns:
        True if server is running and responding.
    """
    try:
        endpoint = host.rstrip("/") + "/api/tags"
        req = request.Request(endpoint, method="GET")
        with request.urlopen(req, timeout=5):
            return True
    except Exception:
        return False


def start_ollama(
    host: str = "http://localhost:11434",
    wait_seconds: int = 10,
    terminal_mode: bool = False,
) -> tuple[bool, str | None]:
    """Start the Ollama server if not already running.

    Args:
        host: Ollama server URL (for environment variable).
        wait_seconds: Maximum seconds to wait for server to start.
        terminal_mode: If True, opens Terminal.app with ollama serve.

    Returns:
        Tuple of (success, error_message).
    """
    if not is_ollama_installed():
        return False, "Ollama CLI is not installed. Install from https://ollama.com"

    if is_ollama_running(host):
        return True, None

    env = os.environ.copy()
    env["OLLAMA_HOST"] = host

    try:
        if terminal_mode:
            # Open Terminal.app and run ollama serve
            script = f'''
            tell application "Terminal"
                activate
                do script "OLLAMA_HOST={host} ollama serve"
            end tell
            '''
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
        else:
            # Start in background
            subprocess.Popen(
                ["ollama", "serve"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

        # Wait for server to become ready
        for _ in range(wait_seconds * 2):
            time.sleep(0.5)
            if is_ollama_running(host):
                return True, None

        return False, f"Ollama did not start within {wait_seconds} seconds"

    except subprocess.CalledProcessError as exc:
        return False, f"Failed to start Ollama: {exc}"
    except Exception as exc:
        return False, f"Unexpected error starting Ollama: {exc}"


def list_models(host: str = "http://localhost:11434") -> tuple[list[str], str | None]:
    """List locally available Ollama models.

    Args:
        host: Ollama server URL.

    Returns:
        Tuple of (model_names, error_message).
    """
    if not is_ollama_running(host):
        return [], "Ollama server is not running"

    try:
        endpoint = host.rstrip("/") + "/api/tags"
        req = request.Request(endpoint, method="GET")
        with request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            models = [m["name"] for m in data.get("models", [])]
            return models, None
    except error.URLError as exc:
        return [], f"Failed to list models: {exc.reason}"
    except json.JSONDecodeError:
        return [], "Invalid response from Ollama server"
    except Exception as exc:
        return [], f"Error listing models: {exc}"


def preload_model(
    model: str,
    host: str = "http://localhost:11434",
    timeout: int = 120,
) -> tuple[bool, str | None]:
    """Preload a model into memory for faster inference.

    This sends a minimal prompt to warm up the model.

    Args:
        model: Model name to preload.
        host: Ollama server URL.
        timeout: Request timeout in seconds.

    Returns:
        Tuple of (success, error_message).
    """
    if not is_ollama_running(host):
        return False, "Ollama server is not running"

    payload = {
        "model": model,
        "prompt": "Hello",
        "stream": False,
    }
    body = json.dumps(payload).encode("utf-8")
    endpoint = host.rstrip("/") + "/api/generate"

    try:
        req = request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
            if data.get("response"):
                return True, None
            return False, "Model did not respond"
    except error.URLError as exc:
        return False, f"Failed to preload model: {exc.reason}"
    except Exception as exc:
        return False, f"Error preloading model: {exc}"


def pull_model(
    model: str,
    host: str = "http://localhost:11434",
) -> tuple[bool, str | None]:
    """Pull a model from the Ollama registry.

    Args:
        model: Model name to pull.
        host: Ollama server URL.

    Returns:
        Tuple of (success, error_message).
    """
    if not is_ollama_installed():
        return False, "Ollama CLI is not installed"

    env = os.environ.copy()
    env["OLLAMA_HOST"] = host

    try:
        result = subprocess.run(
            ["ollama", "pull", model],
            env=env,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout for large models
        )
        if result.returncode == 0:
            return True, None
        return False, result.stderr.strip() or "Failed to pull model"
    except subprocess.TimeoutExpired:
        return False, "Model pull timed out"
    except Exception as exc:
        return False, f"Error pulling model: {exc}"


def ensure_ready(
    model: str,
    host: str = "http://localhost:11434",
    start_if_needed: bool = True,
    preload: bool = True,
    terminal_mode: bool = False,
) -> OllamaStatus:
    """Ensure Ollama is running and the model is ready.

    This is the main entry point for the Ollama workflow:
    1. Start Ollama if not running
    2. Check if model is available
    3. Preload model into memory

    Args:
        model: Model name to use.
        host: Ollama server URL.
        start_if_needed: If True, start Ollama if not running.
        preload: If True, preload the model after startup.
        terminal_mode: If True, start Ollama in Terminal.app.

    Returns:
        OllamaStatus with current state.
    """
    # Check installation
    if not is_ollama_installed():
        return OllamaStatus(
            running=False,
            host=host,
            models=[],
            error="Ollama CLI is not installed. Install from https://ollama.com",
        )

    # Start if needed
    if not is_ollama_running(host):
        if start_if_needed:
            success, err = start_ollama(host, terminal_mode=terminal_mode)
            if not success:
                return OllamaStatus(
                    running=False,
                    host=host,
                    models=[],
                    error=err,
                )
        else:
            return OllamaStatus(
                running=False,
                host=host,
                models=[],
                error="Ollama server is not running",
            )

    # List models
    models, err = list_models(host)
    if err:
        return OllamaStatus(
            running=True,
            host=host,
            models=[],
            error=err,
        )

    # Check if requested model is available
    if model not in models:
        return OllamaStatus(
            running=True,
            host=host,
            models=models,
            error=f"Model '{model}' not found. Available: {', '.join(models) or 'none'}",
        )

    # Preload model
    if preload:
        success, err = preload_model(model, host)
        if not success:
            return OllamaStatus(
                running=True,
                host=host,
                models=models,
                error=f"Failed to preload model: {err}",
            )

    return OllamaStatus(
        running=True,
        host=host,
        models=models,
    )
