"""VMEA Parser – Extract metadata and transcripts from Voice Memos."""

import plistlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from mutagen.mp4 import MP4


@dataclass
class MemoMetadata:
    """Parsed metadata from a Voice Memo."""

    memo_id: str
    title: str | None = None
    created: datetime | None = None
    modified: datetime | None = None
    duration_seconds: float | None = None
    transcript: str | None = None
    revised_transcript: str | None = None
    transcript_source: str | None = None  # "plist", "tsrp", or "native"
    custom_label: str | None = None
    is_favorited: bool = False
    raw_plist: dict[str, Any] = field(default_factory=dict)
    # Cleanup provenance fields
    transcript_cleanup: str = ""  # "" or "cleaned"
    transcript_cleanup_model: str = ""  # model name or ""
    transcript_instruction_source: str = ""  # file path or ""


def parse_manifest_plist(composition_path: Path) -> dict[str, Any] | None:
    """Parse manifest.plist from a .composition folder.

    Args:
        composition_path: Path to .composition folder.

    Returns:
        Parsed plist dict, or None if not found/invalid.
    """
    manifest_path = composition_path / "manifest.plist"
    if not manifest_path.exists():
        return None

    try:
        with open(manifest_path, "rb") as f:
            return cast(dict[str, Any], plistlib.load(f))
    except (plistlib.InvalidFileException, OSError):
        return None


def extract_transcript_from_plist(plist_data: dict[str, Any]) -> str | None:
    """Extract transcript text from parsed plist data.

    Args:
        plist_data: Parsed manifest.plist dict.

    Returns:
        Transcript string, or None if not present.
    """
    def normalize(text: str) -> str | None:
        cleaned = text.strip()
        return cleaned or None

    def from_runs(value: Any) -> str | None:
        if isinstance(value, dict):
            value = value.get("runs")
        if not isinstance(value, list):
            return None

        parts = [item for item in value if isinstance(item, str)]
        if not parts:
            return None
        return normalize("".join(parts))

    def from_segments(value: Any) -> str | None:
        if not isinstance(value, list):
            return None

        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
                continue
            if not isinstance(item, dict):
                continue

            for key in ("text", "string", "content", "utterance", "displayText"):
                segment_text = item.get(key)
                if isinstance(segment_text, str) and segment_text.strip():
                    parts.append(segment_text.strip())
                    break

        if not parts:
            return None
        return normalize(" ".join(parts))

    def extract(value: Any) -> str | None:
        if isinstance(value, str):
            return normalize(value)

        candidate = from_runs(value)
        if candidate:
            return candidate

        if isinstance(value, dict):
            for key in ("text", "string", "content"):
                nested_text = value.get(key)
                if isinstance(nested_text, str):
                    candidate = normalize(nested_text)
                    if candidate:
                        return candidate

            for key in ("attributedString", "attributedText"):
                if key in value:
                    candidate = from_runs(value[key])
                    if candidate:
                        return candidate

            for key in ("segments", "utterances", "phrases"):
                if key in value:
                    candidate = from_segments(value[key])
                    if candidate:
                        return candidate

            for key, nested in value.items():
                lowered = key.lower()
                if any(token in lowered for token in ("transcript", "speech", "dictation", "caption")):
                    candidate = extract(nested)
                    if candidate:
                        return candidate
            return None

        if isinstance(value, list):
            candidate = from_segments(value)
            if candidate:
                return candidate
            for item in value:
                candidate = extract(item)
                if candidate:
                    return candidate

        return None

    return extract(plist_data)


def extract_tsrp_atom(audio_path: Path) -> str | None:
    """Extract transcript from tsrp atom embedded in .m4a file.

    iOS 18+ / macOS 15+ embeds transcripts as JSON in a custom atom.
    The JSON format is:
    {"locale":{...}, "attributedString":{"runs":["word",0," word",1,...]}}

    Args:
        audio_path: Path to .m4a file.

    Returns:
        Transcript string, or None if not present.
    """
    import json
    import struct

    try:
        with open(audio_path, "rb") as f:
            data = f.read()

        # Search for 'tsrp' atom marker
        tsrp_pos = data.find(b"tsrp")
        if tsrp_pos < 4:
            return None

        # Get atom size from 4 bytes before the marker
        atom_size = struct.unpack(">I", data[tsrp_pos - 4 : tsrp_pos])[0]
        if atom_size < 8:
            return None

        # Extract JSON content (skip the 4-byte atom type)
        json_start = tsrp_pos + 4
        json_end = tsrp_pos - 4 + atom_size
        json_bytes = data[json_start:json_end]

        # Parse JSON
        tsrp_data = json.loads(json_bytes.decode("utf-8"))

        # Extract transcript from attributedString.runs
        # Format varies:
        #   {"attributedString": {"runs": ["word", 0, " word", 1, ...]}}
        #   {"attributedString": ["word", 0, " word", 1, ...]}
        attributed_string = tsrp_data.get("attributedString", {})

        # Handle both dict and list formats
        if isinstance(attributed_string, dict):
            runs = attributed_string.get("runs", [])
        elif isinstance(attributed_string, list):
            runs = attributed_string
        else:
            return None

        if not runs:
            return None

        # Concatenate only the string elements (skip numeric indices)
        transcript_parts = [item for item in runs if isinstance(item, str)]
        transcript = "".join(transcript_parts).strip()

        return transcript if transcript else None

    except (OSError, json.JSONDecodeError, struct.error, UnicodeDecodeError, KeyError, AttributeError):
        return None


# Regex pattern for Voice Memo filename: "YYYYMMDD HHMMSS-UUID"
_FILENAME_DATE_PATTERN = re.compile(
    r"^(\d{4})(\d{2})(\d{2})\s+(\d{2})(\d{2})(\d{2})-[A-F0-9]+$",
    re.IGNORECASE,
)


def parse_date_from_filename(memo_id: str) -> datetime | None:
    """Parse recording date from Voice Memo filename.

    Voice Memos use format: "YYYYMMDD HHMMSS-UUID"
    Example: "20250809 202743-D74EE5C0" -> Aug 9, 2025 at 8:27:43 PM

    Args:
        memo_id: The memo identifier (filename stem).

    Returns:
        Parsed datetime, or None if format doesn't match.
    """
    match = _FILENAME_DATE_PATTERN.match(memo_id)
    if not match:
        return None

    try:
        year, month, day, hour, minute, second = map(int, match.groups())
        return datetime(year, month, day, hour, minute, second)
    except ValueError:
        return None


def extract_duration_from_m4a(audio_path: Path) -> float | None:
    """Extract duration from M4A file using mutagen.

    Args:
        audio_path: Path to .m4a file.

    Returns:
        Duration in seconds, or None if extraction fails.
    """
    try:
        audio = MP4(audio_path)  # type: ignore[no-untyped-call]
        if audio.info and audio.info.length:
            return audio.info.length
    except (OSError, Exception) as exc:
        # mutagen can raise various exceptions for corrupt/unreadable files
        _ = exc  # explicitly acknowledge the error
    return None


def generate_title_from_date(dt: datetime) -> str:
    """Generate a human-readable title from a datetime.

    Includes seconds to avoid filename collisions between memos
    recorded in the same minute.

    Args:
        dt: Recording datetime.

    Returns:
        Formatted title like "Voice Memo - Aug 9, 2025 8:27:43 PM"
    """
    # Use platform-safe formatting (no %-d which is Linux-only)
    day = dt.day
    hour = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"Voice Memo - {dt.strftime('%b')} {day}, {dt.year} {hour}:{dt.strftime('%M:%S')} {ampm}"


def parse_memo(
    audio_path: Path,
    composition_path: Path | None,
    memo_id: str,
    transcript_priority: str = "both",
) -> MemoMetadata:
    """Parse all available metadata from a Voice Memo.

    Args:
        audio_path: Path to .m4a file.
        composition_path: Path to .composition folder (may be None).
        memo_id: Unique identifier for the memo.
        transcript_priority: "plist", "tsrp", or "both".

    Returns:
        MemoMetadata with all extracted information.
    """
    metadata = MemoMetadata(memo_id=memo_id)

    # Parse plist if available
    plist_data: dict[str, Any] | None = None
    if composition_path:
        plist_data = parse_manifest_plist(composition_path)
        if plist_data:
            metadata.raw_plist = plist_data
            metadata.title = plist_data.get("title") or plist_data.get("customLabel")
            metadata.custom_label = plist_data.get("customLabel")
            metadata.is_favorited = plist_data.get("isFavorited", False)

            # Parse dates
            if created := plist_data.get("creationDate"):
                metadata.created = created if isinstance(created, datetime) else None
            if modified := plist_data.get("modificationDate"):
                metadata.modified = modified if isinstance(modified, datetime) else None

            metadata.duration_seconds = plist_data.get("duration")

    # Extract transcript based on priority
    transcript: str | None = None
    source: str | None = None

    if transcript_priority in ("tsrp", "both"):
        transcript = extract_tsrp_atom(audio_path)
        if transcript:
            source = "tsrp"

    if not transcript and transcript_priority in ("plist", "both") and plist_data:
        transcript = extract_transcript_from_plist(plist_data)
        if transcript:
            source = "plist"

    metadata.transcript = transcript
    metadata.transcript_source = source

    # Fallback 1: Parse date from filename (most reliable for synced files)
    # Filename format: "YYYYMMDD HHMMSS-UUID" contains original recording time
    if not metadata.created:
        metadata.created = parse_date_from_filename(memo_id)

    # Fallback 2: Get dates from file system (least reliable for synced files)
    if not metadata.created:
        try:
            stat = audio_path.stat()
            metadata.created = datetime.fromtimestamp(
                stat.st_birthtime, tz=UTC  # type: ignore[attr-defined]
            ).replace(tzinfo=None)
        except (OSError, AttributeError):
            pass

    if not metadata.modified:
        try:
            stat = audio_path.stat()
            metadata.modified = datetime.fromtimestamp(
                stat.st_mtime, tz=UTC
            ).replace(tzinfo=None)
        except OSError:
            pass

    # Fallback: Extract duration from M4A file if not in plist
    if metadata.duration_seconds is None:
        metadata.duration_seconds = extract_duration_from_m4a(audio_path)

    # Fallback: Generate title from recording date if no plist title
    if not metadata.title and metadata.created:
        metadata.title = generate_title_from_date(metadata.created)

    return metadata
