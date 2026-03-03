"""VMEA State – JSONL state store for reconciliation tracking."""

import hashlib
import json
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class MemoState:
    """State record for a single exported memo."""

    memo_id: str
    source_hash: str  # Hash of source audio + plist
    note_path: str
    audio_path: str | None = None  # None for app-link mode
    exported_at: str = ""  # ISO format
    source_modified: str | None = None  # ISO format
    transcript_source: str | None = None
    export_version: int = 1
    error: str | None = None


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

        with open(self.path, encoding="utf-8") as f:
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

    def get(self, memo_id: str) -> MemoState | None:
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


def _hash_file_chunked(hasher: "hashlib._Hash", file_path: Path, chunk_size: int = 65536) -> None:
    """Hash a file in chunks to avoid loading large files into memory."""
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)


def compute_source_hash(audio_path: Path, composition_path: Path | None) -> str:
    """Compute a hash of the source files for change detection.

    Uses chunked reading to avoid loading large audio files into memory.

    Args:
        audio_path: Path to .m4a file.
        composition_path: Path to .composition folder (may be None).

    Returns:
        Hex digest of combined hash.
    """
    hasher = hashlib.sha256()

    # Hash audio file content in chunks
    if audio_path.exists():
        stat = audio_path.stat()
        hasher.update(f"{stat.st_size}:{stat.st_mtime_ns}".encode())
        _hash_file_chunked(hasher, audio_path)

    # Hash composition folder contents if present
    if composition_path and composition_path.exists():
        for file in sorted(composition_path.iterdir()):
            if file.is_file():
                stat = file.stat()
                hasher.update(f"{file.name}:{stat.st_size}:{stat.st_mtime_ns}".encode())
                _hash_file_chunked(hasher, file)

    return hasher.hexdigest()[:16]  # Truncate for readability


def should_export(
    memo_id: str,
    source_hash: str,
    state: StateStore,
    conflict_resolution: str = "update",
    source_modified: datetime | None = None,
) -> tuple[bool, str]:
    """Determine if a memo should be exported.

    Args:
        memo_id: Memo identifier.
        source_hash: Current source hash.
        state: State store instance.
        conflict_resolution: "skip", "update", or "overwrite".
        source_modified: Current source modification time (optional backup check).

    Returns:
        Tuple of (should_export, reason).
    """
    existing = state.get(memo_id)

    if existing is None:
        return True, "new"

    # Check if output files still exist on disk - re-export if deleted
    note_exists = Path(existing.note_path).exists() if existing.note_path else False
    # audio_path can be None for app-link mode (no local audio file)
    audio_exists = (
        Path(existing.audio_path).exists() if existing.audio_path else True
    )
    if not note_exists or not audio_exists:
        return True, "missing_output"

    if conflict_resolution == "skip":
        return False, "skip_existing"

    if conflict_resolution == "overwrite":
        return True, "overwrite"

    # "update" mode - check if source changed via hash
    if existing.source_hash != source_hash:
        return True, "source_changed"

    # Backup check: also compare modification times if available
    if source_modified and existing.source_modified:
        try:
            existing_mtime = datetime.fromisoformat(existing.source_modified)
            if source_modified > existing_mtime:
                return True, "source_modified"
        except (ValueError, TypeError):
            pass  # Ignore parsing errors, rely on hash

    return False, "unchanged"


def record_export(
    state: StateStore,
    memo_id: str,
    source_hash: str,
    note_path: Path,
    audio_path: Path | None,
    source_modified: datetime | None,
    transcript_source: str | None,
) -> MemoState:
    """Record a successful export in the state store.

    Args:
        state: State store instance.
        memo_id: Memo identifier.
        source_hash: Source content hash.
        note_path: Path to exported note.
        audio_path: Path to exported audio (None for app-link mode).
        source_modified: Source modification time.
        transcript_source: Source of transcript ("plist", "tsrp", etc.).

    Returns:
        The created MemoState record.
    """
    record = MemoState(
        memo_id=memo_id,
        source_hash=source_hash,
        note_path=str(note_path),
        audio_path=str(audio_path) if audio_path else None,
        exported_at=datetime.now().isoformat(),
        source_modified=source_modified.isoformat() if source_modified else None,
        transcript_source=transcript_source,
    )
    state.set(record)
    return record
