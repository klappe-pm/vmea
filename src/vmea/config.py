"""VMEA Configuration – Pydantic models and config loading."""

import sys
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


class OutputStructure(str, Enum):
    """Output directory structure options."""

    FLAT = "flat"
    BY_YEAR = "by-year"
    BY_MONTH = "by-month"


class TranscriptSource(str, Enum):
    """Transcript extraction priority."""

    PLIST = "plist"
    TSRP = "tsrp"
    BOTH = "both"


class ConflictResolution(str, Enum):
    """How to handle existing notes."""

    SKIP = "skip"
    UPDATE = "update"
    OVERWRITE = "overwrite"


class AudioExportMode(str, Enum):
    """How to reference audio in exported notes."""

    COPY = "copy"
    SYMLINK = "symlink"
    SOURCE_LINK = "source-link"


class LogLevel(str, Enum):
    """Logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class VMEAConfig(BaseModel):
    """Main VMEA configuration."""

    # Output settings
    output_folder: Path = Field(default=Path("~/Documents/Obsidian/Voice Memos"))
    audio_output_folder: Optional[Path] = None
    output_structure: OutputStructure = OutputStructure.FLAT
    audio_export_mode: AudioExportMode = AudioExportMode.COPY
    audio_fallback_to_source_link: bool = False

    # Metadata & frontmatter
    default_domain: str = "voice-memo"
    additional_tags: list[str] = Field(default_factory=list)
    filename_date_format: str = "%Y-%m-%d"
    slug_separator: str = "-"
    max_filename_length: int = 100

    # Source detection
    source_path_override: Optional[Path] = None

    # Transcript processing
    include_native_transcript: bool = True
    transcript_source_priority: TranscriptSource = TranscriptSource.BOTH

    # LLM cleanup
    llm_cleanup_enabled: bool = False
    ollama_model: str = "llama3.2:3b"
    ollama_host: str = "http://localhost:11434"
    ollama_timeout: int = 120
    cleanup_instructions_path: Optional[Path] = None
    keep_original_transcript: bool = True

    # Reconciliation & state
    conflict_resolution: ConflictResolution = ConflictResolution.UPDATE
    state_file: str = ".vmea-state.jsonl"

    # Background processing
    watch_enabled: bool = True
    watch_debounce_seconds: int = 5
    stability_check_count: int = 3
    stability_check_interval: int = 2
    reconcile_interval_minutes: int = 60

    # Logging
    log_level: LogLevel = LogLevel.INFO
    log_file: Optional[Path] = Path("~/.local/share/vmea/vmea.log")
    log_max_size_mb: int = 10
    log_backup_count: int = 3

    # Advanced
    dry_run: bool = False
    workers: int = 0
    skip_before_date: Optional[str] = None
    min_duration_seconds: int = 0

    @field_validator(
        "output_folder",
        "audio_output_folder",
        "log_file",
        "source_path_override",
        "cleanup_instructions_path",
        mode="before",
    )
    @classmethod
    def expand_path(cls, v: Optional[str | Path]) -> Optional[Path]:
        """Expand ~ in paths."""
        if v is None or v == "":
            return None
        return Path(v).expanduser()

    model_config = {"use_enum_values": True}


def get_config_path() -> Path:
    """Get the config file path."""
    return Path("~/.config/vmea/config.toml").expanduser()


def load_config(config_path: Optional[Path] = None) -> VMEAConfig:
    """Load configuration from TOML file.

    Args:
        config_path: Optional path to config file. Uses default if not provided.

    Returns:
        VMEAConfig instance with loaded or default values.
    """
    path = config_path or get_config_path()

    if path.exists():
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return VMEAConfig(**data)

    return VMEAConfig()


def save_config(config: VMEAConfig, config_path: Optional[Path] = None) -> None:
    """Save configuration to TOML file.

    Args:
        config: Configuration to save.
        config_path: Optional path to config file. Uses default if not provided.
    """
    import toml

    path = config_path or get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to dict, handling Path objects
    data = config.model_dump()
    for key, value in data.items():
        if isinstance(value, Path):
            data[key] = str(value)

    with open(path, "w") as f:
        toml.dump(data, f)
