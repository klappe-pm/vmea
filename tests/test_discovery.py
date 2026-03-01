"""Tests for VMEA discovery module."""

from pathlib import Path

from vmea.discovery import MemoPair, discover_memos, find_source_path


def test_find_source_path_with_override(temp_dir: Path) -> None:
    """Test that override path is used when provided."""
    recordings = temp_dir / "custom_recordings"
    recordings.mkdir()

    result = find_source_path(override=recordings)
    assert result == recordings


def test_find_source_path_override_not_exists(temp_dir: Path) -> None:
    """Test that None is returned for non-existent override path."""
    result = find_source_path(override=temp_dir / "nonexistent")
    assert result is None


def test_discover_memos_empty_dir(temp_dir: Path) -> None:
    """Test discovery in empty directory."""
    memos = list(discover_memos(temp_dir))
    assert memos == []


def test_discover_memos_with_audio_only(temp_dir: Path) -> None:
    """Test discovery of memo without composition folder."""
    audio_file = temp_dir / "memo-123.m4a"
    audio_file.write_bytes(b"fake audio")

    memos = list(discover_memos(temp_dir))

    assert len(memos) == 1
    assert memos[0].memo_id == "memo-123"
    assert memos[0].audio_path == audio_file
    assert memos[0].composition_path is None
    assert not memos[0].has_composition


def test_discover_memos_with_composition(mock_voice_memos_dir: Path) -> None:
    """Test discovery of memo with composition folder."""
    memos = list(discover_memos(mock_voice_memos_dir))

    assert len(memos) == 1
    memo = memos[0]
    assert memo.memo_id == "test-memo-001"
    assert memo.has_composition
    assert memo.composition_path is not None
    assert (memo.composition_path / "manifest.plist").exists()


def test_discover_memos_multiple(temp_dir: Path) -> None:
    """Test discovery of multiple memos."""
    for i in range(3):
        (temp_dir / f"memo-{i}.m4a").write_bytes(b"audio")

    memos = list(discover_memos(temp_dir))
    assert len(memos) == 3
    memo_ids = {m.memo_id for m in memos}
    assert memo_ids == {"memo-0", "memo-1", "memo-2"}


def test_memo_pair_properties() -> None:
    """Test MemoPair dataclass properties."""
    pair = MemoPair(
        audio_path=Path("/test/memo.m4a"),
        composition_path=None,
        memo_id="memo",
    )
    assert not pair.has_composition
