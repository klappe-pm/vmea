"""VMEA Parser – Extract metadata and transcripts from Voice Memos."""

import plistlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


@dataclass
class MemoMetadata:
    """Parsed metadata from a Voice Memo."""

    memo_id: str
    title: Optional[str] = None
    created: Optional[datetime] = None
    modified: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    transcript: Optional[str] = None
    transcript_source: Optional[str] = None  # "plist", "tsrp", or "llm"
    custom_label: Optional[str] = None
    is_favorited: bool = False
    raw_plist: dict[str, Any] = field(default_factory=dict)


def parse_manifest_plist(composition_path: Path) -> Optional[dict[str, Any]]:
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
            return plistlib.load(f)
    except (plistlib.InvalidFileException, OSError):
        return None


def extract_transcript_from_plist(plist_data: dict[str, Any]) -> Optional[str]:
    """Extract transcript text from parsed plist data.

    Args:
        plist_data: Parsed manifest.plist dict.

    Returns:
        Transcript string, or None if not present.
    """
    # TODO: Implement actual extraction logic based on real plist structure
    # The structure varies between macOS versions
    return plist_data.get("transcript")


def extract_tsrp_atom(audio_path: Path) -> Optional[str]:
    """Extract transcript from tsrp atom embedded in .m4a file.

    iOS 18+ / macOS 15+ embeds transcripts as JSON in a custom atom.

    Args:
        audio_path: Path to .m4a file.

    Returns:
        Transcript string, or None if not present.
    """
    # TODO: Implement tsrp atom extraction
    # This requires reading the m4a file and parsing the atom structure
    # to find the custom tsrp atom containing JSON transcript data
    return None


def parse_memo(
    audio_path: Path,
    composition_path: Optional[Path],
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
    plist_data: Optional[dict[str, Any]] = None
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
    transcript: Optional[str] = None
    source: Optional[str] = None

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

    # Fallback: get dates from file system
    if not metadata.created:
        try:
            stat = audio_path.stat()
            metadata.created = datetime.fromtimestamp(stat.st_birthtime)
        except (OSError, AttributeError):
            pass

    if not metadata.modified:
        try:
            stat = audio_path.stat()
            metadata.modified = datetime.fromtimestamp(stat.st_mtime)
        except OSError:
            pass

    return metadata
