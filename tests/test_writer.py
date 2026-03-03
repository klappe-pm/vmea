"""Tests for VMEA writer module."""

from datetime import datetime
from pathlib import Path

import pytest

from vmea.parser import MemoMetadata
from vmea.writer import (
    format_duration,
    generate_filename,
    generate_note_content,
    write_note,
)


class TestFormatDuration:
    """Tests for format_duration function."""

    def test_seconds_only(self) -> None:
        assert format_duration(45) == "0:45"

    def test_minutes_and_seconds(self) -> None:
        assert format_duration(322) == "5:22"

    def test_hours(self) -> None:
        assert format_duration(3661) == "1:01:01"

    def test_none(self) -> None:
        assert format_duration(None) == "Unknown"


class TestGenerateFilename:
    """Tests for generate_filename function."""

    def test_with_llm_title(self) -> None:
        metadata = MemoMetadata(
            memo_id="abc123",
            created=datetime(2024, 3, 15, 10, 30),
        )
        result = generate_filename(metadata, llm_title="project-kickoff", sequence_number=0)
        assert result == "2024-03-15-00-project-kickoff.md"

    def test_with_sequence_number(self) -> None:
        metadata = MemoMetadata(
            memo_id="abc123",
            created=datetime(2024, 3, 15, 10, 30),
        )
        result = generate_filename(metadata, llm_title="meeting-notes", sequence_number=5)
        assert result == "2024-03-15-05-meeting-notes.md"

    def test_without_llm_title_uses_default(self) -> None:
        metadata = MemoMetadata(
            memo_id="abc123",
            created=datetime(2024, 3, 15, 10, 30),
        )
        result = generate_filename(metadata, llm_title="", sequence_number=0)
        assert result == "2024-03-15-00-voice-memo.md"

    def test_without_date_uses_current(self) -> None:
        metadata = MemoMetadata(memo_id="abc123")
        result = generate_filename(metadata, llm_title="test-memo", sequence_number=0)
        # Should use current date, check format: YYYY-MM-DD-XX-title.md
        assert result.endswith("-00-test-memo.md")
        parts = result.split("-")
        assert len(parts) >= 5  # YYYY-MM-DD-XX-title.md


class TestGenerateNoteContent:
    """Tests for generate_note_content function."""

    def test_content_structure_without_transcript(self) -> None:
        metadata = MemoMetadata(
            memo_id="test-123",
            title="Test Recording",
        )

        result = generate_note_content(
            metadata,
            "Audio/test.m4a",
            note_title="2024-03-15-audio",
            date_created="2024-03-15",
            date_revised="2024-03-15",
        )

        # Has YAML frontmatter
        assert result.startswith("---")
        assert "domains:" in result
        assert "sub-domains:" in result
        assert "llm-model:" in result
        assert "date-created: 2024-03-15" in result
        assert "date-revised: 2024-03-15" in result
        assert "aliases:" in result
        assert "tags:" in result
        # Has required sections
        assert "# 2024-03-15-audio" in result
        assert "## Voice Memo" in result
        assert "![[Audio/test.m4a]]" in result
        assert "## Key Takeaways" in result
        assert "### Revised Transcript" in result
        assert "### Original Transcript" in result
        # Transcript sections are in code blocks
        assert "```markdown" in result
        # Default placeholders
        assert "No LLM Transcript" in result
        assert "No iOS Transcription Available" in result

    def test_content_with_transcript(self) -> None:
        metadata = MemoMetadata(
            memo_id="test-123",
            transcript="This is the original transcript.",
        )

        result = generate_note_content(
            metadata,
            "Audio/test.m4a",
            note_title="2024-03-15-transcript",
            date_created="2024-03-15",
            date_revised="2024-03-15",
        )

        assert "### Original Transcript" in result
        assert "This is the original transcript." in result
        # No revised transcript provided
        assert "No LLM Transcript" in result

    def test_content_with_revised_transcript(self) -> None:
        metadata = MemoMetadata(
            memo_id="test-123",
            transcript="Original text.",
            revised_transcript="Cleaned up text.",
        )

        result = generate_note_content(
            metadata,
            "Audio/test.m4a",
            note_title="2024-03-15-transcript",
            date_created="2024-03-15",
            date_revised="2024-03-15",
        )

        assert "### Revised Transcript" in result
        assert "Cleaned up text." in result
        assert "### Original Transcript" in result
        assert "Original text." in result

    def test_content_with_key_takeaways(self) -> None:
        metadata = MemoMetadata(memo_id="test-123")
        takeaways = [
            "First important point.",
            "Second important point.",
            "Third important point.",
            "Fourth important point.",
            "Fifth important point.",
        ]

        result = generate_note_content(
            metadata,
            "Audio/test.m4a",
            note_title="2024-03-15-audio",
            date_created="2024-03-15",
            date_revised="2024-03-15",
            key_takeaways=takeaways,
        )

        assert "## Key Takeaways" in result
        assert "1. First important point." in result
        assert "2. Second important point." in result
        assert "5. Fifth important point." in result

    def test_content_with_llm_metadata(self) -> None:
        metadata = MemoMetadata(
            memo_id="test-123",
            transcript="Test transcript.",
        )

        result = generate_note_content(
            metadata,
            "Audio/test.m4a",
            note_title="2024-03-15-transcript",
            date_created="2024-03-15",
            date_revised="2024-03-15",
            llm_model="llama3.2:3b",
            domains="Technology",
            sub_domains="Software Development",
        )

        assert "llm-model: llama3.2:3b" in result
        assert "domains: Technology" in result
        assert "sub-domains: Software Development" in result


class TestWriteNote:
    """Tests for write_note function."""

    def test_write_note_creates_markdown_with_app_link(self, output_dir: Path, temp_dir: Path) -> None:
        """Default mode (app-link) creates markdown with link, no audio file."""
        metadata = MemoMetadata(
            memo_id="test-123",
            title="Test Recording",
            created=datetime(2024, 3, 15, 10, 30),
            transcript="Hello world",
            transcript_source="plist",
        )
        audio_source = temp_dir / "source.m4a"
        audio_source.write_bytes(b"fake audio")

        note_path, audio_path = write_note(
            metadata, output_dir, audio_source, llm_title="test-recording"
        )

        # Markdown created with new format: YYYY-MM-DD-XX-title.md
        assert note_path.exists()
        assert note_path.name == "2024-03-15-00-test-recording.md"

        # No audio file created in app-link mode (default)
        assert audio_path is None

        # Audio folder should NOT exist
        audio_folder = output_dir / "Audio"
        assert not audio_folder.exists()

        # Content has app link instead of audio embed
        content = note_path.read_text(encoding="utf-8")
        assert content.startswith("---")
        assert "date-created: 2024-03-15" in content
        assert "# 2024-03-15-00-test-recording" in content
        assert "## Voice Memo" in content
        assert "Open in Voice Memos" in content  # App link text
        assert "file://" in content  # File URL
        assert "### Original Transcript" in content
        assert "Hello world" in content

    def test_write_note_copy_mode_creates_audio(self, output_dir: Path, temp_dir: Path) -> None:
        """Copy mode creates audio file in Audio/ subfolder."""
        metadata = MemoMetadata(
            memo_id="test-123",
            title="Test Recording",
            created=datetime(2024, 3, 15, 10, 30),
            transcript="Hello world",
        )
        audio_source = temp_dir / "source.m4a"
        audio_source.write_bytes(b"fake audio")

        note_path, audio_path = write_note(
            metadata, output_dir, audio_source,
            llm_title="test-recording",
            audio_export_mode="copy"
        )

        # Markdown created
        assert note_path.exists()

        # Audio file created in copy mode
        assert audio_path is not None
        assert audio_path.exists()
        assert audio_path.parent.name == "Audio"
        assert audio_path.read_bytes() == b"fake audio"

        # Content has audio embed
        content = note_path.read_text(encoding="utf-8")
        assert "![[Audio/2024-03-15-00-test-recording.m4a]]" in content

    def test_write_note_default_title(self, output_dir: Path, temp_dir: Path) -> None:
        metadata = MemoMetadata(
            memo_id="test-123",
            created=datetime(2024, 3, 15, 10, 30),
        )
        audio_source = temp_dir / "source.m4a"
        audio_source.write_bytes(b"fake audio")

        note_path, audio_path = write_note(metadata, output_dir, audio_source)

        # Filename uses "voice-memo" default when no llm_title provided
        assert note_path.name == "2024-03-15-00-voice-memo.md"
        # No audio file in default app-link mode
        assert audio_path is None

    def test_write_note_increments_sequence(self, output_dir: Path, temp_dir: Path) -> None:
        metadata = MemoMetadata(
            memo_id="test-123",
            created=datetime(2024, 3, 15, 10, 30),
            transcript="Hello",
        )
        audio_source = temp_dir / "source.m4a"
        audio_source.write_bytes(b"fake audio")

        # Create first note
        note_path1, _ = write_note(
            metadata, output_dir, audio_source, llm_title="meeting-notes"
        )
        assert note_path1.name == "2024-03-15-00-meeting-notes.md"

        # Create second note with same date - should get next sequence number
        audio_source2 = temp_dir / "source2.m4a"
        audio_source2.write_bytes(b"fake audio 2")
        note_path2, _ = write_note(
            metadata, output_dir, audio_source2, llm_title="afternoon-call"
        )

        # Should have incremented sequence number
        assert note_path2.name == "2024-03-15-01-afternoon-call.md"

    def test_write_note_copy_mode_creates_audio_subfolder(self, output_dir: Path, temp_dir: Path) -> None:
        """Audio subfolder is only created in copy mode."""
        metadata = MemoMetadata(
            memo_id="test-123",
            created=datetime(2024, 3, 15, 10, 30),
        )
        audio_source = temp_dir / "source.m4a"
        audio_source.write_bytes(b"fake audio")

        note_path, audio_path = write_note(
            metadata, output_dir, audio_source,
            audio_export_mode="copy"
        )

        # Audio subfolder created in copy mode
        audio_folder = output_dir / "Audio"
        assert audio_folder.exists()
        assert audio_folder.is_dir()
        assert audio_path.parent == audio_folder

    def test_write_note_dry_run(self, output_dir: Path, temp_dir: Path) -> None:
        metadata = MemoMetadata(
            memo_id="test-123",
            created=datetime(2024, 3, 15, 10, 30),
        )
        audio_source = temp_dir / "source.m4a"
        audio_source.write_bytes(b"fake audio")

        note_path, audio_path = write_note(metadata, output_dir, audio_source, dry_run=True)

        # Paths returned but files not created
        assert not note_path.exists()
        # audio_path is None in default app-link mode
        assert audio_path is None

    def test_write_note_with_key_takeaways(self, output_dir: Path, temp_dir: Path) -> None:
        metadata = MemoMetadata(
            memo_id="test-123",
            created=datetime(2024, 3, 15, 10, 30),
            transcript="Some transcript",
        )
        audio_source = temp_dir / "source.m4a"
        audio_source.write_bytes(b"fake audio")
        takeaways = ["Point one.", "Point two.", "Point three.", "Point four.", "Point five."]

        note_path, _ = write_note(
            metadata, output_dir, audio_source, key_takeaways=takeaways
        )

        content = note_path.read_text(encoding="utf-8")
        assert "1. Point one." in content
        assert "5. Point five." in content

    def test_write_note_with_llm_metadata(self, output_dir: Path, temp_dir: Path) -> None:
        metadata = MemoMetadata(
            memo_id="test-123",
            created=datetime(2024, 3, 15, 10, 30),
            transcript="Some transcript",
        )
        audio_source = temp_dir / "source.m4a"
        audio_source.write_bytes(b"fake audio")

        note_path, _ = write_note(
            metadata,
            output_dir,
            audio_source,
            llm_model="llama3.2:3b",
            domains="Business",
            sub_domains="Meeting Notes",
        )

        content = note_path.read_text(encoding="utf-8")
        assert "llm-model: llama3.2:3b" in content
        assert "domains: Business" in content
        assert "sub-domains: Meeting Notes" in content
