"""Tests for VMEA writer module."""

from datetime import datetime
from pathlib import Path

import pytest

from vmea.parser import MemoMetadata
from vmea.writer import (
    format_duration,
    generate_filename,
    generate_frontmatter,
    generate_note_content,
    sanitize_filename,
    write_note,
)


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    def test_simple_title(self) -> None:
        assert sanitize_filename("Meeting Notes") == "meeting-notes"

    def test_special_characters(self) -> None:
        assert sanitize_filename("Hello! World? @#$%") == "hello-world"

    def test_multiple_spaces(self) -> None:
        assert sanitize_filename("Too   Many    Spaces") == "too-many-spaces"

    def test_max_length(self) -> None:
        result = sanitize_filename("A" * 200, max_length=50)
        assert len(result) <= 50

    def test_empty_after_sanitize(self) -> None:
        assert sanitize_filename("!@#$%") == "untitled"

    def test_custom_separator(self) -> None:
        assert sanitize_filename("Hello World", separator="_") == "hello_world"


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

    def test_with_date_and_title(self) -> None:
        metadata = MemoMetadata(
            memo_id="abc123",
            title="Team Meeting",
            created=datetime(2024, 3, 15, 10, 30),
        )
        result = generate_filename(metadata)
        assert result == "2024-03-15-team-meeting.md"

    def test_without_date(self) -> None:
        metadata = MemoMetadata(memo_id="abc123", title="Quick Note")
        result = generate_filename(metadata)
        assert result == "quick-note.md"

    def test_fallback_to_memo_id(self) -> None:
        metadata = MemoMetadata(memo_id="abc123")
        result = generate_filename(metadata)
        assert result == "abc123.md"


class TestGenerateFrontmatter:
    """Tests for generate_frontmatter function."""

    def test_basic_frontmatter(self) -> None:
        metadata = MemoMetadata(
            memo_id="test-123",
            title="Test Recording",
            created=datetime(2024, 3, 15, 10, 30),
            duration_seconds=120.5,
        )
        result = generate_frontmatter(metadata, "test.m4a")

        assert "---" in result
        assert 'memo_id: "test-123"' in result
        assert 'title: "Test Recording"' in result
        assert "duration_seconds: 120.5" in result
        assert 'audio_file: "test.m4a"' in result

    def test_frontmatter_with_transcript(self) -> None:
        metadata = MemoMetadata(
            memo_id="test-123",
            transcript="Hello world",
            transcript_source="plist",
        )
        result = generate_frontmatter(metadata, "test.m4a")

        assert "has_transcript: true" in result
        assert "transcript_source: plist" in result
        assert "- transcript" in result  # tag

    def test_frontmatter_escapes_quotes(self) -> None:
        metadata = MemoMetadata(
            memo_id="test",
            title='Title with "quotes"',
        )
        result = generate_frontmatter(metadata, "test.m4a")

        assert r'title: "Title with \"quotes\""' in result


class TestGenerateNoteContent:
    """Tests for generate_note_content function."""

    def test_note_content_includes_markdown_body_without_transcript(self) -> None:
        metadata = MemoMetadata(
            memo_id="test-123",
            title="Test Recording",
            created=datetime(2024, 3, 15, 10, 30),
            duration_seconds=120.5,
        )

        result = generate_note_content(metadata, "test.m4a", "[[test.m4a]]")

        assert result.startswith("---\n")
        assert "\n# Test Recording\n" in result
        assert "\n## Metadata\n" in result
        assert "[[test.m4a]]" in result
        assert "## Revised Transcript" not in result

    def test_note_content_places_revised_transcript_first_and_original_last(self) -> None:
        metadata = MemoMetadata(
            memo_id="test-123",
            title="Test Recording",
            transcript="raw transcript",
            revised_transcript="revised transcript",
        )

        result = generate_note_content(metadata, "test.m4a", "[[test.m4a]]")

        assert "## Revised Transcript" in result
        assert "revised transcript" in result
        assert "## Original Transcript" in result
        assert "raw transcript" in result
        assert result.index("## Revised Transcript") < result.index("## Metadata")
        assert result.index("## Original Transcript") > result.index("## Metadata")


class TestWriteNote:
    """Tests for write_note function."""

    def test_write_note_creates_markdown_and_audio(self, output_dir: Path, temp_dir: Path) -> None:
        metadata = MemoMetadata(
            memo_id="test-123",
            title="Test Recording",
            created=datetime(2024, 3, 15, 10, 30),
            duration_seconds=120.5,
            transcript="Hello world",
            transcript_source="plist",
        )
        audio_source = temp_dir / "source.m4a"
        audio_source.write_bytes(b"fake audio")

        note_path, audio_path = write_note(metadata, output_dir, audio_source)

        assert note_path.exists()
        assert audio_path.exists()
        assert audio_path.read_bytes() == b"fake audio"

        content = note_path.read_text(encoding="utf-8")
        assert "# Test Recording" in content
        assert "## Revised Transcript" in content
        assert "## Original Transcript" in content
        assert "[[2024-03-15-test-recording.m4a]]" in content

    def test_write_note_cleans_up_when_audio_copy_fails(
        self,
        output_dir: Path,
        temp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        metadata = MemoMetadata(
            memo_id="test-123",
            title="Test Recording",
            created=datetime(2024, 3, 15, 10, 30),
        )
        audio_source = temp_dir / "source.m4a"
        audio_source.write_bytes(b"fake audio")

        note_path = output_dir / generate_filename(metadata)
        audio_path = output_dir / note_path.name.replace(".md", ".m4a")

        def fail_copy(_src: Path, _dst: Path) -> None:
            raise OSError("copy failed")

        monkeypatch.setattr("vmea.writer.shutil.copy2", fail_copy)

        with pytest.raises(OSError, match="copy failed"):
            write_note(metadata, output_dir, audio_source)

        assert not note_path.exists()
        assert not audio_path.exists()
        assert not note_path.with_suffix(".md.tmp").exists()
        assert not audio_path.with_suffix(".m4a.tmp").exists()

    def test_write_note_can_export_audio_to_separate_folder(
        self,
        output_dir: Path,
        temp_dir: Path,
    ) -> None:
        metadata = MemoMetadata(
            memo_id="test-123",
            title="Test Recording",
            created=datetime(2024, 3, 15, 10, 30),
        )
        audio_source = temp_dir / "source.m4a"
        audio_source.write_bytes(b"fake audio")
        audio_output_dir = temp_dir / "audio"

        note_path, audio_path = write_note(
            metadata,
            output_dir,
            audio_source,
            audio_output_folder=audio_output_dir,
        )

        assert note_path.exists()
        assert audio_path == audio_output_dir / "2024-03-15-test-recording.m4a"
        assert audio_path.exists()

        content = note_path.read_text(encoding="utf-8")
        assert "[Open Audio](<../audio/2024-03-15-test-recording.m4a>)" in content

    def test_write_note_falls_back_to_local_source_link_when_copy_fails(
        self,
        output_dir: Path,
        temp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        metadata = MemoMetadata(
            memo_id="test-123",
            title="Test Recording",
            created=datetime(2024, 3, 15, 10, 30),
        )
        audio_source = temp_dir / "source.m4a"
        audio_source.write_bytes(b"fake audio")

        def fail_copy(_src: Path, _dst: Path) -> None:
            raise OSError("copy failed")

        monkeypatch.setattr("vmea.writer.shutil.copy2", fail_copy)

        note_path, audio_path = write_note(
            metadata,
            output_dir,
            audio_source,
            audio_fallback_to_source_link=True,
        )

        assert note_path.exists()
        assert audio_path == audio_source.resolve()

        content = note_path.read_text(encoding="utf-8")
        assert f"[Open Audio](<{audio_source.resolve().as_uri()}>)" in content
