"""Tests for VMEA writer module."""

from datetime import datetime
from pathlib import Path

import pytest

from vmea.parser import MemoMetadata
from vmea.writer import (
    format_duration,
    generate_filename,
    generate_frontmatter,
    sanitize_filename,
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
