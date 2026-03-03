"""Pytest configuration and fixtures for VMEA tests."""

import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir() -> Iterator[Path]:
    """Provide a temporary directory that is cleaned up after the test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_config(temp_dir: Path) -> Path:
    """Create a sample config file for testing."""
    config_path = temp_dir / "config.toml"
    config_path.write_text(
        """
output_folder = "{output}"
default_domain = "test-memo"
llm_cleanup_enabled = false
""".format(output=str(temp_dir / "output"))
    )
    return config_path


@pytest.fixture
def mock_voice_memos_dir(temp_dir: Path) -> Path:
    """Create a mock Voice Memos directory structure for testing."""
    recordings_dir = temp_dir / "Recordings"
    recordings_dir.mkdir(parents=True)

    # Create a sample memo structure
    memo_id = "test-memo-001"

    # Create fake .m4a file
    audio_file = recordings_dir / f"{memo_id}.m4a"
    audio_file.write_bytes(b"fake m4a content")

    # Create .composition folder with manifest.plist
    composition_dir = recordings_dir / f"{memo_id}.composition"
    composition_dir.mkdir()

    # Simple plist content (binary plist would be used in real files)
    import plistlib

    plist_data = {
        "title": "Test Recording",
        "duration": 123.45,
        "isFavorited": False,
    }
    manifest_path = composition_dir / "manifest.plist"
    with open(manifest_path, "wb") as f:
        plistlib.dump(plist_data, f)

    return recordings_dir


@pytest.fixture
def output_dir(temp_dir: Path) -> Path:
    """Provide an output directory for test exports."""
    output = temp_dir / "output"
    output.mkdir(parents=True)
    return output
