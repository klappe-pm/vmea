"""VMEA Writer – Generate Markdown notes for Voice Memos."""

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from vmea.parser import MemoMetadata


def get_next_sequence_number(output_folder: Path, date_str: str) -> int:
    """Get the next available sequence number for a given date.

    Scans existing files in the output folder to find the highest
    sequence number used for the given date, then returns the next one.

    Args:
        output_folder: Folder containing existing notes.
        date_str: Date string in YYYY-MM-DD format.

    Returns:
        Next available sequence number (0-based).
    """
    if not output_folder.exists():
        return 0

    # Pattern: YYYY-MM-DD-XX-* where XX is the sequence number
    pattern = re.compile(rf"^{re.escape(date_str)}-(\d{{2}})-.*\.md$")
    max_seq = -1

    for file in output_folder.glob(f"{date_str}-*.md"):
        match = pattern.match(file.name)
        if match:
            seq = int(match.group(1))
            max_seq = max(max_seq, seq)

    return max_seq + 1


def generate_filename(
    metadata: MemoMetadata,
    llm_title: str = "",
    date_format: str = "%Y-%m-%d",
    sequence_number: int = 0,
) -> str:
    """Generate a filename for a memo.

    Format: {date}-{XX}-{llm-title}.md
    Example: 2025-01-15-00-project-kickoff-meeting.md

    Args:
        metadata: Parsed memo metadata.
        llm_title: LLM-generated title slug (e.g., "project-kickoff-meeting").
        date_format: strftime format for date.
        sequence_number: Daily sequence number (0-based).

    Returns:
        Generated filename (without path).
    """
    if metadata.created:
        date_str = metadata.created.strftime(date_format)
    else:
        date_str = datetime.now().strftime(date_format)

    # Format sequence as 2 digits
    seq_str = f"{sequence_number:02d}"

    # Use provided title or fallback
    title = llm_title if llm_title else "voice-memo"

    return f"{date_str}-{seq_str}-{title}.md"


def format_duration(seconds: Optional[float]) -> str:
    """Format duration in human-readable form."""
    if seconds is None:
        return "Unknown"

    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def generate_note_content(
    metadata: MemoMetadata,
    audio_filename: str,
    note_title: str,
    date_created: str,
    date_revised: str,
    llm_model: str = "",
    domains: str = "",
    sub_domains: str = "",
    key_takeaways: Optional[list[str]] = None,
    audio_source_path: Optional[Path] = None,
    audio_export_mode: str = "copy",
) -> str:
    """Generate Markdown note content with YAML frontmatter.

    Args:
        metadata: Parsed memo metadata.
        audio_filename: Filename of the audio file (for embed link).
        note_title: Title for the note (e.g., "2025-01-01-transcript").
        date_created: Date created in YYYY-MM-DD format.
        date_revised: Date revised in YYYY-MM-DD format.
        llm_model: Name of the LLM model used.
        domains: Domain value from LLM.
        sub_domains: Sub-domain value from LLM.
        key_takeaways: List of 5 key takeaways from LLM.
        audio_source_path: Original audio file path (for app-link mode).
        audio_export_mode: How to reference audio ("copy", "app-link", etc.).

    Returns:
        Complete Markdown content with YAML frontmatter.
    """
    parts = []

    # YAML Frontmatter
    parts.append("---")
    parts.append(f"domains: {domains}")
    parts.append(f"sub-domains: {sub_domains}")
    parts.append(f"llm-model: {llm_model}")
    parts.append(f"date-created: {date_created}")
    parts.append(f"date-revised: {date_revised}")
    parts.append("aliases:")
    parts.append("tags:")
    parts.append("---")
    parts.append("")

    # Title (filename without .md)
    parts.append(f"# {note_title}")

    # Voice Memo section with audio link
    parts.append("## Voice Memo")
    if audio_export_mode == "app-link" and audio_source_path:
        # Create a file:// link to open the memo in Voice Memos app
        file_url = f"file://{quote(str(audio_source_path), safe='/:')}"
        parts.append(f"[🎙️ Open in Voice Memos]({file_url})")
    else:
        parts.append(f"![[{audio_filename}]]")
    parts.append("")

    # Key Takeaways section
    parts.append("## Key Takeaways")
    if key_takeaways and len(key_takeaways) > 0:
        for i, takeaway in enumerate(key_takeaways[:5], 1):
            parts.append(f"{i}. {takeaway}")
    else:
        parts.append("*No key takeaways available*")
    parts.append("")

    # Revised Transcript section (in code block)
    parts.append("### Revised Transcript")
    parts.append("```markdown")
    if metadata.revised_transcript:
        parts.append(metadata.revised_transcript)
    else:
        parts.append("No LLM Transcript")
    parts.append("```")
    parts.append("")

    # Original Transcript section (in code block)
    parts.append("### Original Transcript")
    parts.append("```markdown")
    if metadata.transcript:
        parts.append(metadata.transcript)
    else:
        parts.append("No iOS Transcription Available")
    parts.append("```")
    parts.append("")

    return "\n".join(parts)


def copy_audio_file(audio_source: Path, audio_dest: Path) -> None:
    """Copy an audio file to the destination with atomic write."""
    audio_dest.parent.mkdir(parents=True, exist_ok=True)
    temp_audio = audio_dest.with_suffix(".m4a.tmp")
    try:
        shutil.copy2(audio_source, temp_audio)
        temp_audio.replace(audio_dest)
    except Exception:
        temp_audio.unlink(missing_ok=True)
        raise


def write_note(
    metadata: MemoMetadata,
    output_folder: Path,
    audio_source: Path,
    key_takeaways: Optional[list[str]] = None,
    llm_model: str = "",
    domains: str = "",
    sub_domains: str = "",
    date_format: str = "%Y-%m-%d",
    dry_run: bool = False,
    audio_export_mode: str = "app-link",
    llm_title: str = "",
) -> tuple[Path, Optional[Path]]:
    """Write a Markdown note and optionally copy the audio file.

    Args:
        metadata: Parsed memo metadata.
        output_folder: Destination folder for Markdown notes.
        audio_source: Source .m4a file.
        key_takeaways: List of 5 key takeaways from LLM.
        llm_model: Name of the LLM model used.
        domains: Domain value from LLM.
        sub_domains: Sub-domain value from LLM.
        date_format: Date format for filenames.
        dry_run: If True, don't actually write files.
        audio_export_mode: How to handle audio ("copy", "app-link", etc.).
        llm_title: LLM-generated title for filename (e.g., "project-kickoff").

    Returns:
        Tuple of (note_path, audio_path) for the written files.
        audio_path is None when audio_export_mode is "app-link".
    """
    output_folder.mkdir(parents=True, exist_ok=True)

    # Get the date string for this memo
    if metadata.created:
        date_str = metadata.created.strftime(date_format)
    else:
        date_str = datetime.now().strftime(date_format)

    # Get the next sequence number for this date
    sequence_number = get_next_sequence_number(output_folder, date_str)

    # Generate filename with new format: YYYY-MM-DD-XX-{title}.md
    note_filename = generate_filename(
        metadata,
        llm_title=llm_title,
        date_format=date_format,
        sequence_number=sequence_number,
    )
    note_path = output_folder / note_filename

    # Handle filename collision (shouldn't happen with sequence numbers, but just in case)
    if note_path.exists() and not dry_run:
        # Increment sequence until we find an unused one
        while note_path.exists():
            sequence_number += 1
            note_filename = generate_filename(
                metadata,
                llm_title=llm_title,
                date_format=date_format,
                sequence_number=sequence_number,
            )
            note_path = output_folder / note_filename

    # Audio handling depends on export mode
    audio_path: Optional[Path] = None
    audio_filename = note_filename.replace(".md", ".m4a")

    if audio_export_mode != "app-link":
        # Audio folder is output_folder/Audio/
        audio_folder = output_folder / "Audio"
        audio_folder.mkdir(parents=True, exist_ok=True)
        audio_path = audio_folder / audio_filename

    if dry_run:
        return note_path, audio_path

    # Copy audio file only for copy/symlink modes
    if audio_export_mode == "copy" and audio_path:
        copy_audio_file(audio_source, audio_path)
    elif audio_export_mode == "symlink" and audio_path:
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        if audio_path.exists() or audio_path.is_symlink():
            audio_path.unlink()
        audio_path.symlink_to(audio_source)

    # Date values
    if metadata.created:
        date_created = metadata.created.strftime(date_format)
    else:
        date_created = datetime.now().strftime(date_format)
    date_revised = datetime.now().strftime(date_format)

    # Note title is filename without .md
    note_title = note_filename.removesuffix(".md")

    # Generate and write note content
    temp_note = note_path.with_suffix(".md.tmp")
    try:
        content = generate_note_content(
            metadata=metadata,
            audio_filename=f"Audio/{audio_filename}",
            note_title=note_title,
            date_created=date_created,
            date_revised=date_revised,
            llm_model=llm_model,
            domains=domains,
            sub_domains=sub_domains,
            key_takeaways=key_takeaways,
            audio_source_path=audio_source,
            audio_export_mode=audio_export_mode,
        )
        temp_note.write_text(content, encoding="utf-8")
        temp_note.replace(note_path)
    except Exception:
        temp_note.unlink(missing_ok=True)
        # Clean up audio if note write failed (only if we copied it)
        if audio_path and audio_path.exists():
            audio_path.unlink(missing_ok=True)
        raise

    return note_path, audio_path
