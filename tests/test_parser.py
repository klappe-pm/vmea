"""Tests for VMEA parser module."""

from datetime import datetime

from vmea.parser import (
    extract_transcript_from_plist,
    generate_title_from_date,
    parse_date_from_filename,
)


class TestExtractTranscriptFromPlist:
    """Tests for plist transcript extraction."""

    def test_extracts_direct_transcript_string(self) -> None:
        plist_data = {"transcript": "Hello world"}

        assert extract_transcript_from_plist(plist_data) == "Hello world"

    def test_extracts_nested_attributed_string_runs(self) -> None:
        plist_data = {
            "transcriptPayload": {
                "attributedString": {
                    "runs": ["Hello", 0, " world", 1],
                }
            }
        }

        assert extract_transcript_from_plist(plist_data) == "Hello world"

    def test_extracts_segmented_transcript_text(self) -> None:
        plist_data = {
            "speechTranscript": {
                "segments": [
                    {"text": "Hello"},
                    {"text": "world"},
                ]
            }
        }

        assert extract_transcript_from_plist(plist_data) == "Hello world"

    def test_returns_none_when_no_transcript_candidate_exists(self) -> None:
        plist_data = {"title": "Voice Memo", "duration": 12.5}

        assert extract_transcript_from_plist(plist_data) is None


class TestParseDateFromFilename:
    """Tests for filename date parsing."""

    def test_parses_standard_filename_format(self) -> None:
        result = parse_date_from_filename("20250115 143022-ABCD")
        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 14
        assert result.minute == 30
        assert result.second == 22

    def test_returns_none_for_invalid_format(self) -> None:
        result = parse_date_from_filename("random-memo-id")
        assert result is None

    def test_returns_none_for_empty_string(self) -> None:
        result = parse_date_from_filename("")
        assert result is None


class TestGenerateTitleFromDate:
    """Tests for date-based title generation."""

    def test_generates_correct_format(self) -> None:
        dt = datetime(2025, 8, 9, 20, 27, 43)
        title = generate_title_from_date(dt)
        assert "Voice Memo" in title
        assert "Aug" in title
        assert "9" in title
        assert "2025" in title
        assert "PM" in title

    def test_am_time(self) -> None:
        dt = datetime(2025, 1, 1, 9, 0, 0)
        title = generate_title_from_date(dt)
        assert "AM" in title
        assert "9" in title

    def test_noon(self) -> None:
        dt = datetime(2025, 6, 15, 12, 0, 0)
        title = generate_title_from_date(dt)
        assert "PM" in title
        assert "12:" in title

    def test_midnight(self) -> None:
        dt = datetime(2025, 6, 15, 0, 30, 0)
        title = generate_title_from_date(dt)
        assert "AM" in title
        assert "12:" in title
