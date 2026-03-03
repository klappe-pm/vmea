"""Tests for VMEA state module."""

from datetime import datetime
from pathlib import Path

from vmea.state import (
    MemoState,
    StateStore,
    compute_source_hash,
    record_export,
    should_export,
)


class TestStateStore:
    """Tests for JSONL-based state store."""

    def test_empty_state_store(self, temp_dir: Path) -> None:
        state_path = temp_dir / ".vmea-state.jsonl"
        store = StateStore(path=state_path)
        assert len(store) == 0
        assert list(store.all()) == []

    def test_set_and_get(self, temp_dir: Path) -> None:
        state_path = temp_dir / ".vmea-state.jsonl"
        store = StateStore(path=state_path)

        record = MemoState(
            memo_id="memo-001",
            source_hash="abc123",
            note_path="/output/note.md",
        )
        store.set(record)

        assert len(store) == 1
        assert "memo-001" in store
        retrieved = store.get("memo-001")
        assert retrieved is not None
        assert retrieved.source_hash == "abc123"

    def test_get_nonexistent_returns_none(self, temp_dir: Path) -> None:
        state_path = temp_dir / ".vmea-state.jsonl"
        store = StateStore(path=state_path)
        assert store.get("nonexistent") is None

    def test_remove(self, temp_dir: Path) -> None:
        state_path = temp_dir / ".vmea-state.jsonl"
        store = StateStore(path=state_path)

        record = MemoState(
            memo_id="memo-001",
            source_hash="abc123",
            note_path="/output/note.md",
        )
        store.set(record)
        assert "memo-001" in store

        removed = store.remove("memo-001")
        assert removed is True
        assert "memo-001" not in store
        assert len(store) == 0

    def test_remove_nonexistent_returns_false(self, temp_dir: Path) -> None:
        state_path = temp_dir / ".vmea-state.jsonl"
        store = StateStore(path=state_path)
        assert store.remove("nonexistent") is False

    def test_persistence_across_loads(self, temp_dir: Path) -> None:
        state_path = temp_dir / ".vmea-state.jsonl"

        # Write some state
        store1 = StateStore(path=state_path)
        store1.set(MemoState(memo_id="memo-001", source_hash="abc", note_path="/a.md"))
        store1.set(MemoState(memo_id="memo-002", source_hash="def", note_path="/b.md"))

        # Reload from disk
        store2 = StateStore(path=state_path)
        assert len(store2) == 2
        assert store2.get("memo-001") is not None
        assert store2.get("memo-002") is not None

    def test_compact_deduplicates(self, temp_dir: Path) -> None:
        state_path = temp_dir / ".vmea-state.jsonl"
        store = StateStore(path=state_path)

        # Write same memo twice (simulating update)
        store.set(MemoState(memo_id="memo-001", source_hash="v1", note_path="/a.md"))
        store.set(MemoState(memo_id="memo-001", source_hash="v2", note_path="/a.md"))

        # File has 2 lines but store has 1 record
        assert len(store) == 1
        assert store.get("memo-001").source_hash == "v2"

        # Compact should reduce file size
        saved = store.compact()
        assert saved > 0

        # Reload and verify
        store2 = StateStore(path=state_path)
        assert len(store2) == 1
        assert store2.get("memo-001").source_hash == "v2"

    def test_skips_malformed_lines(self, temp_dir: Path) -> None:
        state_path = temp_dir / ".vmea-state.jsonl"
        state_path.write_text('not valid json\n{"memo_id":"m1","source_hash":"h","note_path":"/p"}\n')

        store = StateStore(path=state_path)
        assert len(store) == 1
        assert "m1" in store


class TestComputeSourceHash:
    """Tests for source hash computation."""

    def test_hash_audio_file(self, temp_dir: Path) -> None:
        audio = temp_dir / "memo.m4a"
        audio.write_bytes(b"audio content")

        h = compute_source_hash(audio, None)
        assert isinstance(h, str)
        assert len(h) == 16

    def test_hash_changes_with_content(self, temp_dir: Path) -> None:
        audio = temp_dir / "memo.m4a"

        audio.write_bytes(b"content A")
        h1 = compute_source_hash(audio, None)

        audio.write_bytes(b"content B")
        h2 = compute_source_hash(audio, None)

        assert h1 != h2

    def test_hash_includes_composition(self, temp_dir: Path) -> None:
        audio = temp_dir / "memo.m4a"
        audio.write_bytes(b"audio")

        comp = temp_dir / "memo.composition"
        comp.mkdir()
        (comp / "manifest.plist").write_bytes(b"plist data")

        h_with = compute_source_hash(audio, comp)
        h_without = compute_source_hash(audio, None)

        assert h_with != h_without

    def test_hash_nonexistent_file(self, temp_dir: Path) -> None:
        audio = temp_dir / "nonexistent.m4a"
        h = compute_source_hash(audio, None)
        assert isinstance(h, str)
        assert len(h) == 16


class TestShouldExport:
    """Tests for export decision logic."""

    def test_new_memo_should_export(self, temp_dir: Path) -> None:
        store = StateStore(path=temp_dir / "state.jsonl")
        do_export, reason = should_export("new-memo", "hash1", store)
        assert do_export is True
        assert reason == "new"

    def test_skip_existing_with_skip_policy(self, temp_dir: Path) -> None:
        store = StateStore(path=temp_dir / "state.jsonl")
        note = temp_dir / "note.md"
        note.write_text("existing")
        store.set(MemoState(
            memo_id="memo-001",
            source_hash="hash1",
            note_path=str(note),
        ))

        do_export, reason = should_export("memo-001", "hash1", store, "skip")
        assert do_export is False
        assert reason == "skip_existing"

    def test_overwrite_policy_always_exports(self, temp_dir: Path) -> None:
        store = StateStore(path=temp_dir / "state.jsonl")
        note = temp_dir / "note.md"
        note.write_text("existing")
        store.set(MemoState(
            memo_id="memo-001",
            source_hash="hash1",
            note_path=str(note),
        ))

        do_export, reason = should_export("memo-001", "hash1", store, "overwrite")
        assert do_export is True
        assert reason == "overwrite"

    def test_update_detects_changed_hash(self, temp_dir: Path) -> None:
        store = StateStore(path=temp_dir / "state.jsonl")
        note = temp_dir / "note.md"
        note.write_text("existing")
        store.set(MemoState(
            memo_id="memo-001",
            source_hash="old_hash",
            note_path=str(note),
        ))

        do_export, reason = should_export("memo-001", "new_hash", store, "update")
        assert do_export is True
        assert reason == "source_changed"

    def test_update_skips_unchanged(self, temp_dir: Path) -> None:
        store = StateStore(path=temp_dir / "state.jsonl")
        note = temp_dir / "note.md"
        note.write_text("existing")
        store.set(MemoState(
            memo_id="memo-001",
            source_hash="same_hash",
            note_path=str(note),
        ))

        do_export, reason = should_export("memo-001", "same_hash", store, "update")
        assert do_export is False
        assert reason == "unchanged"

    def test_missing_output_triggers_reexport(self, temp_dir: Path) -> None:
        store = StateStore(path=temp_dir / "state.jsonl")
        store.set(MemoState(
            memo_id="memo-001",
            source_hash="hash1",
            note_path="/nonexistent/note.md",
        ))

        do_export, reason = should_export("memo-001", "hash1", store, "skip")
        assert do_export is True
        assert reason == "missing_output"


class TestRecordExport:
    """Tests for recording exports to state."""

    def test_record_export_creates_state(self, temp_dir: Path) -> None:
        store = StateStore(path=temp_dir / "state.jsonl")
        note_path = temp_dir / "note.md"
        audio_path = temp_dir / "audio.m4a"

        record = record_export(
            state=store,
            memo_id="memo-001",
            source_hash="hash123",
            note_path=note_path,
            audio_path=audio_path,
            source_modified=datetime(2025, 1, 15, 10, 30),
            transcript_source="tsrp",
        )

        assert record.memo_id == "memo-001"
        assert record.source_hash == "hash123"
        assert record.transcript_source == "tsrp"
        assert "memo-001" in store

    def test_record_export_with_none_audio(self, temp_dir: Path) -> None:
        store = StateStore(path=temp_dir / "state.jsonl")
        note_path = temp_dir / "note.md"

        record = record_export(
            state=store,
            memo_id="memo-001",
            source_hash="hash123",
            note_path=note_path,
            audio_path=None,
            source_modified=None,
            transcript_source=None,
        )

        assert record.audio_path is None
        assert record.source_modified is None
