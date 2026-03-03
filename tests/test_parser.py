"""Tests for VMEA parser module."""

from vmea.parser import extract_transcript_from_plist


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
