"""VMEA Writer – Generate Markdown notes with YAML frontmatter."""

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from vmea.parser import MemoMetadata


def sanitize_filename(title: str, max_length: int = 100, separator: str = "-") -> str:
    """Convert a title to a safe filename slug.

    Args:
        title: Original title string.
        max_length: Maximum length of the slug.
        separator: Character to use between words.

    Returns:
        Sanitized filename-safe slug.
    """
    # Convert to lowercase and replace spaces
    slug = title.lower().strip()

    # Remove or replace unsafe characters
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", separator, slug)
    slug = re.sub(rf"{separator}+", separator, slug)
    slug = slug.strip(separator)

    # Truncate if needed
    if len(slug) > max_length:
        slug = slug[:max_length].rsplit(separator, 1)[0]

    return slug or "untitled"


def generate_filename(
    metadata: MemoMetadata,
    date_format: str = "%Y-%m-%d",
    separator: str = "-",
    max_length: int = 100,
) -> str:
    """Generate a filename for a memo.

    Format: {date}-{title-slug}.md

    Args:
        metadata: Parsed memo metadata.
        date_format: strftime format for date prefix.
        separator: Slug separator character.
        max_length: Maximum total filename length.

    Returns:
        Generated filename (without path).
    """
    # Date prefix
    date_str = ""
    if metadata.created:
        date_str = metadata.created.strftime(date_format)

    # Title slug
    title = metadata.title or metadata.custom_label or metadata.memo_id
    slug = sanitize_filename(title, max_length=max_length - len(date_str) - 5, separator=separator)

    if date_str:
        return f"{date_str}{separator}{slug}.md"
    return f"{slug}.md"


def format_duration(seconds: Optional[float]) -> str:
    """Format duration in human-readable form.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted string like "5:22" or "1:05:30".
    """
    if seconds is None:
        return "Unknown"

    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def generate_frontmatter(
    metadata: MemoMetadata,
    audio_filename: str,
    domain: str = "voice-memo",
    additional_tags: Optional[list[str]] = None,
) -> str:
    """Generate YAML frontmatter for a memo note.

    Args:
        metadata: Parsed memo metadata.
        audio_filename: Filename of the copied audio file.
        domain: Domain tag.
        additional_tags: Extra tags to include.

    Returns:
        YAML frontmatter string (including --- delimiters).
    """
    tags = [domain]
    if metadata.transcript:
        tags.append("transcript")
    if metadata.is_favorited:
        tags.append("favorited")
    if additional_tags:
        tags.extend(additional_tags)

    # Build frontmatter dict
    lines = ["---"]
    lines.append(f'memo_id: "{metadata.memo_id}"')

    if metadata.title:
        # Escape quotes in title
        safe_title = metadata.title.replace('"', '\\"')
        lines.append(f'title: "{safe_title}"')

    lines.append(f"domain: {domain}")

    if metadata.created:
        lines.append(f"created: {metadata.created.isoformat()}")
    if metadata.modified:
        lines.append(f"modified: {metadata.modified.isoformat()}")
    if metadata.duration_seconds is not None:
        lines.append(f"duration_seconds: {metadata.duration_seconds:.1f}")

    lines.append(f"has_transcript: {str(bool(metadata.transcript)).lower()}")
    if metadata.transcript_source:
        lines.append(f"transcript_source: {metadata.transcript_source}")

    lines.append(f'audio_file: "{audio_filename}"')

    # Tags as YAML list
    lines.append("tags:")
    for tag in tags:
        lines.append(f"  - {tag}")

    # Aliases
    if metadata.title:
        lines.append("aliases:")
        lines.append(f'  - "{metadata.title} (Voice Memo)"')

    lines.append("---")
    return "\n".join(lines)


def generate_note_content(
    metadata: MemoMetadata,
    audio_filename: str,
    domain: str = "voice-memo",
    additional_tags: Optional[list[str]] = None,
) -> str:
    """Generate complete Markdown note content.

    Args:
        metadata: Parsed memo metadata.
        audio_filename: Filename of the copied audio file.
        domain: Domain tag.
        additional_tags: Extra tags to include.

    Returns:
        Complete Markdown content including frontmatter.
    """
    parts = []

    # Frontmatter
    parts.append(generate_frontmatter(metadata, audio_filename, domain, additional_tags))
    parts.append("")  # Blank line after frontmatter

    # Title
    title = metadata.title or metadata.custom_label or "Voice Memo"
    parts.append(f"# {title}")
    parts.append("")

    # Transcript section
    if metadata.transcript:
        parts.append("## Transcript")
        parts.append("")
        parts.append(metadata.transcript)
        parts.append("")

    # Metadata section
    parts.append("## Metadata")
    parts.append("")

    if metadata.created:
        formatted_date = metadata.created.strftime("%B %d, %Y at %I:%M %p")
        parts.append(f"- **Recorded**: {formatted_date}")

    if metadata.duration_seconds is not None:
        parts.append(f"- **Duration**: {format_duration(metadata.duration_seconds)}")

    parts.append(f"- **Audio**: [[{audio_filename}]]")
    parts.append("")

    return "\n".join(parts)


def write_note(
    metadata: MemoMetadata,
    output_folder: Path,
    audio_source: Path,
    domain: str = "voice-memo",
    additional_tags: Optional[list[str]] = None,
    date_format: str = "%Y-%m-%d",
    dry_run: bool = False,
) -> tuple[Path, Path]:
    """Write a Markdown note and copy the audio file.

    Uses atomic writes to prevent partial files.

    Args:
        metadata: Parsed memo metadata.
        output_folder: Destination folder.
        audio_source: Source .m4a file.
        domain: Domain tag.
        additional_tags: Extra tags.
        date_format: Date format for filenames.
        dry_run: If True, don't actually write files.

    Returns:
        Tuple of (note_path, audio_path) for the written files.
    """
    output_folder.mkdir(parents=True, exist_ok=True)

    # Generate filenames
    note_filename = generate_filename(metadata, date_format=date_format)
    audio_filename = note_filename.replace(".md", ".m4a")

    note_path = output_folder / note_filename
    audio_path = output_folder / audio_filename

    if dry_run:
        return note_path, audio_path

    # Generate note content
    content = generate_note_content(metadata, audio_filename, domain, additional_tags)

    # Atomic write for note
    temp_note = note_path.with_suffix(".md.tmp")
    try:
        temp_note.write_text(content, encoding="utf-8")
        temp_note.replace(note_path)
    except Exception:
        temp_note.unlink(missing_ok=True)
        raise

    # Copy audio file (preserve metadata)
    temp_audio = audio_path.with_suffix(".m4a.tmp")
    try:
        shutil.copy2(audio_source, temp_audio)
        temp_audio.replace(audio_path)
    except Exception:
        temp_audio.unlink(missing_ok=True)
        raise

    return note_path, audio_path
