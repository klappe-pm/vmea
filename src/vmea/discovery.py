"""VMEA Discovery – Find and enumerate Voice Memos on the system."""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

# Known Voice Memos locations on macOS (checked in order of preference)
# Reference: Apple documentation and empirical testing across macOS versions
VOICE_MEMOS_PATHS = [
    # macOS Sonoma (14.x) / Sequoia (15.x) - Group Containers (most common current path)
    Path("~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings"),
    # iCloud Drive sync staging folder (Mobile Documents)
    Path("~/Library/Mobile Documents/com~apple~VoiceMemos/Recordings"),
    # macOS Sonoma+ Containers path variant
    Path("~/Library/Containers/com.apple.VoiceMemos/Data/Library/Application Support/Recordings"),
    # macOS Ventura (13.x) and earlier
    Path("~/Library/Application Support/com.apple.voicememos/Recordings"),
    # Alternative Application Support path (case variant)
    Path("~/Library/Application Support/com.apple.VoiceMemos/Recordings"),
]


@dataclass
class MemoPair:
    """A paired Voice Memo: .m4a audio file + .composition metadata folder."""

    audio_path: Path
    composition_path: Optional[Path]  # May not exist for older memos
    memo_id: str  # Derived from filename stem

    @property
    def has_composition(self) -> bool:
        """Check if composition metadata exists."""
        return self.composition_path is not None and self.composition_path.exists()


def find_source_path(override: Optional[Path] = None) -> Optional[Path]:
    """Find the Voice Memos source directory.

    Args:
        override: Optional user-specified path.

    Returns:
        Path to Voice Memos directory, or None if not found.
    """
    if override:
        expanded = override.expanduser()
        if expanded.exists():
            return expanded
        return None

    for path in VOICE_MEMOS_PATHS:
        expanded = path.expanduser()
        if expanded.exists():
            return expanded

    return None


def discover_memos(source_path: Path) -> Iterator[MemoPair]:
    """Discover all Voice Memos in the source directory.

    Yields MemoPair objects for each .m4a file found, paired with its
    .composition folder if it exists.

    Args:
        source_path: Path to Voice Memos directory.

    Yields:
        MemoPair for each discovered memo.
    """
    if not source_path.exists():
        return

    for audio_file in source_path.glob("*.m4a"):
        memo_id = audio_file.stem
        composition_path = source_path / f"{memo_id}.composition"

        yield MemoPair(
            audio_path=audio_file,
            composition_path=composition_path if composition_path.exists() else None,
            memo_id=memo_id,
        )


def diagnose_paths() -> list[tuple[Path, bool, int]]:
    """Check all known Voice Memos paths and report status.

    Returns:
        List of (path, exists, memo_count) tuples.
    """
    results = []
    for path in VOICE_MEMOS_PATHS:
        expanded = path.expanduser()
        exists = expanded.exists()
        memo_count = 0
        if exists:
            memo_count = len(list(expanded.glob("*.m4a")))
        results.append((expanded, exists, memo_count))
    return results


def check_file_stability(path: Path, check_count: int = 3, interval: float = 2.0) -> bool:
    """Check if a file is stable (not being written to).

    Used to avoid processing partially-synced iCloud files.

    Args:
        path: Path to check.
        check_count: Number of stability checks.
        interval: Seconds between checks.

    Returns:
        True if file size remained constant across all checks.
    """
    import time

    if not path.exists():
        return False

    sizes: list[int] = []
    for _ in range(check_count):
        try:
            sizes.append(path.stat().st_size)
        except OSError:
            return False
        if len(sizes) < check_count:
            time.sleep(interval)

    return len(set(sizes)) == 1
