"""VMEA Transcribe – Whisper-based speech-to-text for Voice Memos."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Available Whisper models (smallest to largest)
WHISPER_MODELS = [
    "tiny",
    "tiny.en",
    "base",
    "base.en",
    "small",
    "small.en",
    "medium",
    "medium.en",
    "large",
    "large-v2",
    "large-v3",
]

DEFAULT_MODEL = "base"


@dataclass
class TranscriptionResult:
    """Result of audio transcription."""

    text: str
    model: str
    language: str | None = None
    duration_seconds: float | None = None


def is_whisper_available() -> bool:
    """Check if the openai-whisper package is installed.

    Returns:
        True if whisper is importable.
    """
    try:
        import whisper  # type: ignore[import-untyped]  # noqa: F401

        return True
    except ImportError:
        return False


def get_available_models() -> list[str]:
    """Get list of available Whisper models.

    Returns:
        List of model names that can be used.
    """
    return WHISPER_MODELS.copy()


def transcribe_audio(
    audio_path: Path,
    model: str = DEFAULT_MODEL,
    language: str | None = None,
    verbose: bool = False,
) -> TranscriptionResult:
    """Transcribe an audio file using Whisper.

    Args:
        audio_path: Path to the audio file (.m4a, .mp3, .wav, etc.).
        model: Whisper model name (tiny, base, small, medium, large).
        language: Optional language code (e.g., "en"). Auto-detected if None.
        verbose: If True, show progress during transcription.

    Returns:
        TranscriptionResult with transcribed text.

    Raises:
        ImportError: If openai-whisper is not installed.
        FileNotFoundError: If audio file doesn't exist.
        RuntimeError: If transcription fails.
    """
    if not is_whisper_available():
        raise ImportError(
            "openai-whisper is not installed. "
            "Install with: pip install 'vmea[transcribe]' or pip install openai-whisper"
        )

    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    import whisper

    try:
        # Load the model (downloads if not cached)
        logger.info(f"Loading Whisper model: {model}")
        whisper_model = whisper.load_model(model)

        # Transcribe the audio
        logger.info(f"Transcribing: {audio_path.name}")
        options: dict[str, str | bool] = {"verbose": verbose}
        if language:
            options["language"] = language

        result = whisper_model.transcribe(str(audio_path), **options)

        text = result.get("text", "").strip()
        detected_language = result.get("language")

        if not text:
            raise RuntimeError("Whisper returned empty transcription")

        return TranscriptionResult(
            text=text,
            model=model,
            language=detected_language,
        )

    except Exception as e:
        if "CUDA" in str(e) or "torch" in str(e):
            # Provide helpful error for GPU/PyTorch issues
            raise RuntimeError(
                f"Whisper transcription failed (possible GPU/PyTorch issue): {e}"
            ) from e
        raise RuntimeError(f"Whisper transcription failed: {e}") from e


def transcribe_if_needed(
    audio_path: Path,
    existing_transcript: str | None,
    model: str = DEFAULT_MODEL,
    language: str | None = None,
) -> tuple[str | None, str]:
    """Transcribe audio only if no existing transcript is available.

    Args:
        audio_path: Path to the audio file.
        existing_transcript: Existing transcript text, or None.
        model: Whisper model to use if transcription needed.
        language: Optional language code.

    Returns:
        Tuple of (transcript_text, source) where source is "whisper" if
        transcription was performed, or "existing" if transcript was already present.
        Returns (None, "none") if transcription fails or no transcript available.
    """
    # If transcript already exists, return it
    if existing_transcript and existing_transcript.strip():
        return existing_transcript, "existing"

    # Check if Whisper is available
    if not is_whisper_available():
        logger.warning(
            "No transcript available and Whisper is not installed. "
            "Install with: pip install 'vmea[transcribe]'"
        )
        return None, "none"

    # Transcribe with Whisper
    try:
        result = transcribe_audio(audio_path, model=model, language=language)
        return result.text, "whisper"
    except Exception as e:
        logger.error(f"Whisper transcription failed: {e}")
        return None, "none"
