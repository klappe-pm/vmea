"""VMEA Configuration – Pydantic models and config loading."""

import tomllib
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class TranscriptSource(StrEnum):
    """Transcript extraction priority."""

    PLIST = "plist"
    TSRP = "tsrp"
    BOTH = "both"


class ConflictResolution(StrEnum):
    """How to handle existing notes."""

    SKIP = "skip"
    UPDATE = "update"
    OVERWRITE = "overwrite"


class AudioExportMode(StrEnum):
    """How to reference audio in exported notes."""

    COPY = "copy"
    SYMLINK = "symlink"
    SOURCE_LINK = "source-link"
    APP_LINK = "app-link"  # Link to open Voice Memos app


class VMEAConfig(BaseModel):
    """Main VMEA configuration."""

    # Output settings
    output_folder: Path = Field(default=Path("~/Documents/Obsidian/Voice Memos"))
    audio_output_folder: Path | None = None
    audio_export_mode: AudioExportMode = AudioExportMode.APP_LINK  # Default to app-link (no file copy)
    audio_fallback_to_source_link: bool = False

    # Metadata & frontmatter
    default_domain: str = ""
    filename_date_format: str = "%Y-%m-%d"

    # Source detection
    source_path_override: Path | None = None

    # Transcript processing
    include_native_transcript: bool = True
    transcript_source_priority: TranscriptSource = TranscriptSource.BOTH

    # LLM cleanup
    llm_cleanup_enabled: bool = True
    ollama_model: str = "llama3.2:3b"  # Single model (backward compat)
    ollama_models: list[str] = Field(default_factory=list)  # Cascade: [transcribe, revise, polish]
    ollama_host: str = "http://localhost:11434"
    ollama_timeout: int = 120
    cleanup_instructions_path: Path | None = None
    fail_on_missing_instruction_file: bool = False
    preserve_raw_transcript: bool = True
    ollama_startup_mode: str = "terminal_managed"  # "terminal_managed" or "background"

    # Whisper transcription (for memos without native transcripts)
    whisper_model: str = "base"  # tiny, base, small, medium, large
    whisper_language: str | None = None  # Auto-detect if None
    transcribe_missing: bool = True  # Transcribe memos without transcripts

    # Reconciliation & state
    conflict_resolution: ConflictResolution = ConflictResolution.UPDATE
    state_file: str = ".vmea-state.jsonl"

    # Background processing
    watch_debounce_seconds: int = 5

    # Advanced
    dry_run: bool = False

    @field_validator(
        "output_folder",
        "audio_output_folder",
        "source_path_override",
        "cleanup_instructions_path",
        mode="before",
    )
    @classmethod
    def expand_path(cls, v: str | Path | None) -> Path | None:
        """Expand ~ in paths."""
        if v is None or v == "":
            return None
        return Path(v).expanduser()

    model_config = {"use_enum_values": True}


def get_config_path() -> Path:
    """Get the config file path."""
    return Path("~/.config/vmea/config.toml").expanduser()


def migrate_legacy_config(path: Path) -> None:
    """Fix enum strings in old config files."""
    if not path.exists():
        return

    with open(path, encoding="utf-8") as f:
        content = f.read()

    original = content

    # Replace legacy enum representations
    content = content.replace('"TranscriptSource.BOTH"', '"both"')
    content = content.replace('"TranscriptSource.PLIST"', '"plist"')
    content = content.replace('"TranscriptSource.TSRP"', '"tsrp"')
    content = content.replace('"ConflictResolution.UPDATE"', '"update"')
    content = content.replace('"ConflictResolution.SKIP"', '"skip"')
    content = content.replace('"ConflictResolution.OVERWRITE"', '"overwrite"')
    content = content.replace('"AudioExportMode.COPY"', '"copy"')
    content = content.replace('"AudioExportMode.SYMLINK"', '"symlink"')
    content = content.replace('"AudioExportMode.SOURCE_LINK"', '"source-link"')
    content = content.replace('"AudioExportMode.APP_LINK"', '"app-link"')
    content = content.replace('"OutputStructure.FLAT"', '"flat"')
    content = content.replace('"OutputStructure.BY_YEAR"', '"by-year"')
    content = content.replace('"OutputStructure.BY_MONTH"', '"by-month"')
    # Legacy LogLevel and OutputStructure enums (removed from config)
    # Still migrate them so old config files don't break on unknown keys
    content = content.replace('"LogLevel.DEBUG"', '"DEBUG"')
    content = content.replace('"LogLevel.INFO"', '"INFO"')
    content = content.replace('"LogLevel.WARNING"', '"WARNING"')
    content = content.replace('"LogLevel.ERROR"', '"ERROR"')

    if content != original:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)


def load_config(config_path: Path | None = None) -> VMEAConfig:
    """Load configuration from TOML file.

    Args:
        config_path: Optional path to config file. Uses default if not provided.

    Returns:
        VMEAConfig instance with loaded or default values.
    """
    path = config_path or get_config_path()

    if path.exists():
        # Migrate legacy enum representations before loading
        migrate_legacy_config(path)
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return VMEAConfig(**data)

    return VMEAConfig()


def save_config(config: VMEAConfig, config_path: Path | None = None) -> None:
    """Save configuration to TOML file.

    Args:
        config: Configuration to save.
        config_path: Optional path to config file. Uses default if not provided.
    """
    import tomli_w

    path = config_path or get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to dict using mode='json' to properly serialize enums as values
    # exclude_none=True to avoid TOML serialization errors for None values
    data = config.model_dump(mode="json", exclude_none=True)
    for key, value in list(data.items()):
        if isinstance(value, Path):
            data[key] = str(value)

    with open(path, "wb") as f:
        tomli_w.dump(data, f)
