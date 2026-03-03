"""VMEA Writer – Generate Markdown notes with YAML frontmatter."""

import os
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
    audio_reference: str,
    domain: str = "voice-memo",
    additional_tags: Optional[list[str]] = None,
) -> str:
    """Generate YAML frontmatter for a memo note.

    Args:
        metadata: Parsed memo metadata.
        audio_reference: Audio file reference or local file URL.
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

    safe_audio_reference = audio_reference.replace('"', '\\"')
    lines.append(f'audio_file: "{safe_audio_reference}"')

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
    audio_reference: str,
    audio_link: str,
    domain: str = "voice-memo",
    additional_tags: Optional[list[str]] = None,
) -> str:
    """Generate complete Markdown note content.

    Args:
        metadata: Parsed memo metadata.
        audio_reference: Audio file reference or local file URL.
        audio_link: Rendered Markdown link for the audio.
        domain: Domain tag.
        additional_tags: Extra tags to include.

    Returns:
        Complete Markdown content including frontmatter.
    """
    parts = []

    # Frontmatter
    parts.append(generate_frontmatter(metadata, audio_reference, domain, additional_tags))
    parts.append("")  # Blank line after frontmatter

    # Title
    title = metadata.title or metadata.custom_label or "Voice Memo"
    parts.append(f"# {title}")
    parts.append("")

    # Revised transcript first.
    if metadata.transcript:
        parts.append("## Revised Transcript")
        parts.append("")
        parts.append(metadata.revised_transcript or metadata.transcript)
        parts.append("")

    # Metadata section
    parts.append("## Metadata")
    parts.append("")

    if metadata.created:
        formatted_date = metadata.created.strftime("%B %d, %Y at %I:%M %p")
        parts.append(f"- **Recorded**: {formatted_date}")

    if metadata.duration_seconds is not None:
        parts.append(f"- **Duration**: {format_duration(metadata.duration_seconds)}")

    parts.append(f"- **Audio**: {audio_link}")
    parts.append("")

    # Always keep the original transcript at the bottom when we have one.
    if metadata.transcript:
        parts.append("## Original Transcript")
        parts.append("")
        parts.append(metadata.transcript)
        parts.append("")

    return "\n".join(parts)


def render_audio_link(audio_reference: str) -> str:
    """Render the best Markdown link format for an audio reference."""
    if audio_reference.startswith("file://") or "/" in audio_reference:
        return f"[Open Audio](<{audio_reference}>)"
    return f"[[{audio_reference}]]"


def build_audio_reference(note_path: Path, audio_path: Path) -> str:
    """Build a relative reference from the note location to the audio file."""
    if note_path.parent == audio_path.parent:
        return audio_path.name
    relative = os.path.relpath(audio_path, start=note_path.parent)
    return relative.replace(os.sep, "/")


def build_source_file_reference(audio_source: Path) -> str:
    """Build a local file URL for an original source audio file."""
    return audio_source.resolve().as_uri()


def stage_audio_file(
    audio_source: Path,
    audio_path: Path,
    export_mode: str,
) -> None:
    """Export an audio file using the configured mode."""
    audio_path.parent.mkdir(parents=True, exist_ok=True)

    if export_mode == "copy":
        temp_audio = audio_path.with_suffix(".m4a.tmp")
        try:
            shutil.copy2(audio_source, temp_audio)
            temp_audio.replace(audio_path)
        except Exception:
            temp_audio.unlink(missing_ok=True)
            raise
        return

    if export_mode == "symlink":
        temp_audio = audio_path.with_suffix(".m4a.tmp")
        try:
            temp_audio.unlink(missing_ok=True)
            temp_audio.symlink_to(audio_source.resolve())
            temp_audio.replace(audio_path)
        except Exception:
            temp_audio.unlink(missing_ok=True)
            raise
        return

    raise ValueError(f"Unsupported audio export mode: {export_mode}")


def write_note(
    metadata: MemoMetadata,
    output_folder: Path,
    audio_source: Path,
    audio_output_folder: Optional[Path] = None,
    audio_export_mode: str = "copy",
    audio_fallback_to_source_link: bool = True,
    domain: str = "voice-memo",
    additional_tags: Optional[list[str]] = None,
    date_format: str = "%Y-%m-%d",
    dry_run: bool = False,
) -> tuple[Path, Path]:
    """Write a Markdown note and copy the audio file.

    Uses atomic writes to prevent partial files.

    Args:
        metadata: Parsed memo metadata.
        output_folder: Destination folder for Markdown notes.
        audio_source: Source .m4a file.
        audio_output_folder: Destination folder for audio exports. Defaults to output_folder.
        audio_export_mode: "copy", "symlink", or "source-link".
        audio_fallback_to_source_link: If True, link the original file when audio export fails.
        domain: Domain tag.
        additional_tags: Extra tags.
        date_format: Date format for filenames.
        dry_run: If True, don't actually write files.

    Returns:
        Tuple of (note_path, audio_path) for the written files.
    """
    output_folder.mkdir(parents=True, exist_ok=True)
    audio_output_folder = (audio_output_folder or output_folder).expanduser()

    # Generate filenames with collision detection
    note_filename = generate_filename(metadata, date_format=date_format)
    note_path = output_folder / note_filename

    # If file exists and belongs to a different memo, append short ID to disambiguate
    if note_path.exists() and not dry_run:
        existing_content = note_path.read_text(encoding="utf-8")
        if f'memo_id: "{metadata.memo_id}"' not in existing_content:
            short_id = metadata.memo_id.split("-")[-1][:6].lower() if "-" in metadata.memo_id else metadata.memo_id[-6:]
            base = note_filename.removesuffix(".md")
            note_filename = f"{base}-{short_id}.md"
            note_path = output_folder / note_filename

    audio_filename = note_filename.replace(".md", ".m4a")
    exported_audio_path = audio_output_folder / audio_filename

    if audio_export_mode == "source-link":
        audio_path = audio_source.resolve()
        audio_reference = build_source_file_reference(audio_source)
    else:
        audio_path = exported_audio_path
        audio_reference = build_audio_reference(note_path, audio_path)

    if dry_run:
        return note_path, audio_path

    temp_note = note_path.with_suffix(".md.tmp")
    wrote_audio = False

    try:
        if audio_export_mode != "source-link":
            try:
                stage_audio_file(audio_source, exported_audio_path, audio_export_mode)
                wrote_audio = True
            except Exception:
                if not audio_fallback_to_source_link:
                    raise
                audio_path = audio_source.resolve()
                audio_reference = build_source_file_reference(audio_source)

        content = generate_note_content(
            metadata,
            audio_reference,
            render_audio_link(audio_reference),
            domain,
            additional_tags,
        )
        temp_note.write_text(content, encoding="utf-8")
        temp_note.replace(note_path)
    except Exception:
        temp_note.unlink(missing_ok=True)
        if wrote_audio and audio_export_mode != "source-link" and exported_audio_path.exists():
            if exported_audio_path.is_symlink() or exported_audio_path.is_file():
                exported_audio_path.unlink(missing_ok=True)
        raise

    return note_path, audio_path
