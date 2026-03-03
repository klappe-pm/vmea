"""Tests for VMEA config module - enum serialization and migration."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from vmea.config import (
    ConflictResolution,
    TranscriptSource,
    VMEAConfig,
    load_config,
    migrate_legacy_config,
    save_config,
)


class TestEnumSerialization:
    """Test that enums serialize and deserialize correctly."""

    def test_config_model_dump_uses_enum_values(self) -> None:
        """Test that model_dump(mode='json') outputs enum values, not repr."""
        config = VMEAConfig(
            transcript_source_priority=TranscriptSource.BOTH,
            conflict_resolution=ConflictResolution.UPDATE,
        )
        data = config.model_dump(mode="json")

        # Should be lowercase values, not "TranscriptSource.BOTH"
        assert data["transcript_source_priority"] == "both"
        assert data["conflict_resolution"] == "update"

    def test_config_loads_with_string_enum_values(self, temp_dir: Path) -> None:
        """Test that config loads correctly with lowercase enum values."""
        config_path = temp_dir / "config.toml"
        config_path.write_text(
            '''
output_folder = "/tmp/test"
transcript_source_priority = "both"
conflict_resolution = "skip"
'''
        )

        config = load_config(config_path)
        assert config.transcript_source_priority == TranscriptSource.BOTH
        assert config.conflict_resolution == ConflictResolution.SKIP

    def test_config_rejects_invalid_enum_strings(self, temp_dir: Path) -> None:
        """Test that invalid enum strings raise validation error."""
        config_path = temp_dir / "config.toml"
        config_path.write_text(
            '''
output_folder = "/tmp/test"
transcript_source_priority = "invalid_value"
'''
        )

        with pytest.raises(ValidationError):
            load_config(config_path)


class TestLegacyConfigMigration:
    """Test the migrate_legacy_config function."""

    def test_migrate_fixes_transcript_source_enum(self, temp_dir: Path) -> None:
        """Test migration of TranscriptSource enum strings."""
        config_path = temp_dir / "config.toml"
        config_path.write_text(
            '''
output_folder = "/tmp/test"
transcript_source_priority = "TranscriptSource.BOTH"
'''
        )

        migrate_legacy_config(config_path)

        content = config_path.read_text()
        assert '"TranscriptSource.BOTH"' not in content
        assert '"both"' in content

    def test_migrate_fixes_conflict_resolution_enum(self, temp_dir: Path) -> None:
        """Test migration of ConflictResolution enum strings."""
        config_path = temp_dir / "config.toml"
        config_path.write_text(
            '''
output_folder = "/tmp/test"
conflict_resolution = "ConflictResolution.UPDATE"
'''
        )

        migrate_legacy_config(config_path)

        content = config_path.read_text()
        assert '"ConflictResolution.UPDATE"' not in content
        assert '"update"' in content

    def test_migrate_handles_multiple_enums(self, temp_dir: Path) -> None:
        """Test migration fixes all enum types in one pass."""
        config_path = temp_dir / "config.toml"
        config_path.write_text(
            '''
output_folder = "/tmp/test"
transcript_source_priority = "TranscriptSource.PLIST"
conflict_resolution = "ConflictResolution.SKIP"
audio_export_mode = "AudioExportMode.COPY"
'''
        )

        migrate_legacy_config(config_path)

        content = config_path.read_text()
        assert '"plist"' in content
        assert '"skip"' in content
        assert '"copy"' in content

    def test_migrate_preserves_valid_config(self, temp_dir: Path) -> None:
        """Test that migration doesn't modify already-valid configs."""
        original_content = '''
output_folder = "/tmp/test"
transcript_source_priority = "both"
conflict_resolution = "update"
'''
        config_path = temp_dir / "config.toml"
        config_path.write_text(original_content)

        migrate_legacy_config(config_path)

        assert config_path.read_text() == original_content

    def test_migrate_nonexistent_file_does_nothing(self, temp_dir: Path) -> None:
        """Test that migration handles missing files gracefully."""
        config_path = temp_dir / "nonexistent.toml"
        # Should not raise
        migrate_legacy_config(config_path)
        assert not config_path.exists()


class TestSaveConfig:
    """Test config saving with proper enum serialization."""

    def test_save_and_reload_preserves_enums(self, temp_dir: Path) -> None:
        """Test full round-trip: save config, reload, enums intact."""
        config_path = temp_dir / "config.toml"

        original = VMEAConfig(
            output_folder=temp_dir / "output",
            transcript_source_priority=TranscriptSource.TSRP,
            conflict_resolution=ConflictResolution.OVERWRITE,
        )

        save_config(original, config_path)
        reloaded = load_config(config_path)

        assert reloaded.transcript_source_priority == TranscriptSource.TSRP
        assert reloaded.conflict_resolution == ConflictResolution.OVERWRITE

    def test_save_writes_lowercase_enum_values(self, temp_dir: Path) -> None:
        """Test that saved config contains lowercase enum values."""
        config_path = temp_dir / "config.toml"

        config = VMEAConfig(
            output_folder=temp_dir / "output",
            transcript_source_priority=TranscriptSource.BOTH,
            conflict_resolution=ConflictResolution.UPDATE,
        )

        save_config(config, config_path)
        content = config_path.read_text()

        # Should NOT contain the class name prefix
        assert "TranscriptSource" not in content
        assert "ConflictResolution" not in content


class TestLoadConfigWithMigration:
    """Test that load_config auto-migrates legacy configs."""

    def test_load_auto_migrates_legacy_enums(self, temp_dir: Path) -> None:
        """Test that loading a legacy config auto-migrates and succeeds."""
        config_path = temp_dir / "config.toml"
        config_path.write_text(
            '''
output_folder = "/tmp/test"
transcript_source_priority = "TranscriptSource.BOTH"
conflict_resolution = "ConflictResolution.UPDATE"
'''
        )

        # Should not raise - migration happens automatically
        config = load_config(config_path)

        assert config.transcript_source_priority == TranscriptSource.BOTH
        assert config.conflict_resolution == ConflictResolution.UPDATE

        # Config file should now be fixed
        content = config_path.read_text()
        assert '"both"' in content
        assert '"update"' in content
