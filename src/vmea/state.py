"""VMEA State – JSONL state store for reconciliation tracking."""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional


@dataclass
class MemoState:
    """State record for a single exported memo."""

    memo_id: str
    source_hash: str  # Hash of source audio + plist
    note_path: str
    audio_path: str
    exported_at: str  # ISO format
    source_modified: Optional[str] = None  # ISO format
    transcript_source: Optional[str] = None
    export_version: int = 1
    error: Optional[str] = None


@dataclass
class StateStore:
    """JSONL-based state store for tracking exports."""

    path: Path
    _records: dict[str, MemoState] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        """Load existing state on init."""
        self._load()

    def _load(self) -> None:
        """Load state from JSONL file."""
        if not self.path.exists():
            return

        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    record = MemoState(**data)
                    self._records[record.memo_id] = record
                except (json.JSONDecodeError, TypeError):
                    continue  # Skip malformed lines

    def _append(self, record: MemoState) -> None:
        """Append a record to the JSONL file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record)) + "\n")

    def _rewrite(self) -> None:
        """Rewrite the entire state file (for compaction)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            for record in self._records.values():
                f.write(json.dumps(asdict(record)) + "\n")

    def get(self, memo_id: str) -> Optional[MemoState]:
        """Get state for a memo by ID."""
        return self._records.get(memo_id)

    def set(self, record: MemoState) -> None:
        """Set/update state for a memo."""
        self._records[record.memo_id] = record
        self._append(record)

    def remove(self, memo_id: str) -> bool:
        """Remove a memo from state (marks for cleanup)."""
        if memo_id in self._records:
            del self._records[memo_id]
            self._rewrite()  # Need full rewrite to remove
            return True
        return False

    def all(self) -> Iterator[MemoState]:
        """Iterate over all memo states."""
        yield from self._records.values()

    def compact(self) -> int:
        """Compact the state file (remove duplicates, keep latest)."""
        original_size = self.path.stat().st_size if self.path.exists() else 0
        self._rewrite()
        new_size = self.path.stat().st_size if self.path.exists() else 0
        return original_size - new_size

    def __len__(self) -> int:
        return len(self._records)

    def __contains__(self, memo_id: str) -> bool:
        return memo_id in self._records


def compute_source_hash(audio_path: Path, composition_path: Optional[Path]) -> str:
    """Compute a hash of the source files for change detection.

    Args:
        audio_path: Path to .m4a file.
        composition_path: Path to .composition folder (may be None).

    Returns:
        Hex digest of combined hash.
    """
    hasher = hashlib.sha256()

    # Hash audio file
    if audio_path.exists():
        hasher.update(audio_path.read_bytes())

    # Hash plist if present
    if composition_path:
        manifest = composition_path / "manifest.plist"
        if manifest.exists():
            hasher.update(manifest.read_bytes())

    return hasher.hexdigest()[:16]  # Truncate for readability


def should_export(
    memo_id: str,
    source_hash: str,
    state: StateStore,
    conflict_resolution: str = "update",
) -> tuple[bool, str]:
    """Determine if a memo should be exported.

    Args:
        memo_id: Memo identifier.
        source_hash: Current source hash.
        state: State store instance.
        conflict_resolution: "skip", "update", or "overwrite".

    Returns:
        Tuple of (should_export, reason).
    """
    existing = state.get(memo_id)

    if existing is None:
        return True, "new"

    if conflict_resolution == "skip":
        return False, "skip_existing"

    if conflict_resolution == "overwrite":
        return True, "overwrite"

    # "update" mode - only if source changed
    if existing.source_hash != source_hash:
        return True, "source_changed"

    return False, "unchanged"


def record_export(
    state: StateStore,
    memo_id: str,
    source_hash: str,
    note_path: Path,
    audio_path: Path,
    source_modified: Optional[datetime],
    transcript_source: Optional[str],
) -> MemoState:
    """Record a successful export in the state store.

    Args:
        state: State store instance.
        memo_id: Memo identifier.
        source_hash: Source content hash.
        note_path: Path to exported note.
        audio_path: Path to exported audio.
        source_modified: Source modification time.
        transcript_source: Source of transcript ("plist", "tsrp", etc.).

    Returns:
        The created MemoState record.
    """
    record = MemoState(
        memo_id=memo_id,
        source_hash=source_hash,
        note_path=str(note_path),
        audio_path=str(audio_path),
        exported_at=datetime.now().isoformat(),
        source_modified=source_modified.isoformat() if source_modified else None,
        transcript_source=transcript_source,
    )
    state.set(record)
    return record
