"""Environment based configuration for the local transcriber."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "ja"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value else default


def _env_temperatures(name: str, default: tuple[float, ...]) -> tuple[float, ...]:
    value = os.getenv(name)
    if not value:
        return default
    return tuple(float(item.strip()) for item in value.split(",") if item.strip())


@dataclass(slots=True)
class Settings:
    """Application settings loaded from environment variables."""

    telegram_bot_token: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", "")
    )
    allowed_users: str = field(default_factory=lambda: os.getenv("ALLOWED_USERS", ""))
    telegram_local_mode: bool = field(
        default_factory=lambda: _env_bool("TELEGRAM_LOCAL_MODE", True)
    )
    telegram_base_url: str = field(
        default_factory=lambda: os.getenv(
            "TELEGRAM_BASE_URL", "http://127.0.0.1:8081/bot"
        )
    )
    telegram_base_file_url: str = field(
        default_factory=lambda: os.getenv(
            "TELEGRAM_BASE_FILE_URL", "http://127.0.0.1:8081/file/bot"
        )
    )
    telegram_concurrent_updates: int = field(
        default_factory=lambda: _env_int("TELEGRAM_CONCURRENT_UPDATES", 4)
    )
    max_file_size_mb: int = field(
        default_factory=lambda: _env_int("MAX_FILE_SIZE_MB", 2000)
    )

    norwegian_model: str = field(
        default_factory=lambda: os.getenv("NORWEGIAN_MODEL", "NbAiLab/nb-whisper-large")
    )
    sami_model: str = field(
        default_factory=lambda: os.getenv("SAMI_MODEL", "NbAiLab/whisper-large-sme")
    )
    asr_device: str = field(default_factory=lambda: os.getenv("ASR_DEVICE", "auto"))
    sample_rate: int = field(default_factory=lambda: _env_int("SAMPLE_RATE", 16_000))
    main_chunk_seconds: int = field(
        default_factory=lambda: _env_int("MAIN_CHUNK_SECONDS", 900)
    )
    overlap_seconds: int = field(default_factory=lambda: _env_int("OVERLAP_SECONDS", 3))
    num_beams: int = field(default_factory=lambda: _env_int("NUM_BEAMS", 5))
    temperatures: tuple[float, ...] = field(
        default_factory=lambda: _env_temperatures(
            "TEMPERATURES", (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
        )
    )
    compression_ratio_threshold: float = field(
        default_factory=lambda: _env_float("COMPRESSION_RATIO_THRESHOLD", 2.4)
    )
    logprob_threshold: float = field(
        default_factory=lambda: _env_float("LOGPROB_THRESHOLD", -1.0)
    )
    no_speech_threshold: float = field(
        default_factory=lambda: _env_float("NO_SPEECH_THRESHOLD", 0.6)
    )
    glossary: str = field(
        default_factory=lambda: os.getenv("TRANSCRIPTION_GLOSSARY", "")
    )
    prompt_context_chars: int = field(
        default_factory=lambda: _env_int("PROMPT_CONTEXT_CHARS", 1200)
    )

    data_dir: str = field(default_factory=lambda: os.getenv("DATA_DIR", "data"))
    temp_dir: str = field(
        default_factory=lambda: os.getenv("TEMP_DIR", "data/incoming")
    )
    work_dir: str = field(default_factory=lambda: os.getenv("WORK_DIR", "data/work"))
    output_dir: str = field(
        default_factory=lambda: os.getenv("OUTPUT_DIR", "data/output")
    )
    debug_dir: str = field(default_factory=lambda: os.getenv("DEBUG_DIR", "data/debug"))
    queue_db: str = field(
        default_factory=lambda: os.getenv("QUEUE_DB", "data/jobs.sqlite3")
    )
    delete_source_after_delivery: bool = field(
        default_factory=lambda: _env_bool("DELETE_SOURCE_AFTER_DELIVERY", True)
    )
    failed_retention_hours: int = field(
        default_factory=lambda: _env_int("FAILED_RETENTION_HOURS", 48)
    )
    debug_retention_hours: int = field(
        default_factory=lambda: _env_int("DEBUG_RETENTION_HOURS", 48)
    )
    worker_poll_seconds: float = field(
        default_factory=lambda: _env_float("WORKER_POLL_SECONDS", 1.0)
    )
    log_dir: str = field(default_factory=lambda: os.getenv("LOG_DIR", "logs"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    log_max_bytes: int = field(
        default_factory=lambda: _env_int("LOG_MAX_BYTES", 10_000_000)
    )
    log_backup_count: int = field(
        default_factory=lambda: _env_int("LOG_BACKUP_COUNT", 5)
    )

    def get_allowed_users(self) -> set[str]:
        return {item.strip() for item in self.allowed_users.split(",") if item.strip()}

    def is_user_allowed(self, user_id: str, username: str = "") -> bool:
        allowed = self.get_allowed_users()
        if not allowed:
            return True
        normalized_allowed = {item.casefold() for item in allowed}
        normalized_username = username.lstrip("@").casefold()
        return (
            str(user_id) in normalized_allowed
            or f"@{normalized_username}" in normalized_allowed
            or normalized_username in normalized_allowed
        )

    def model_for_language(self, language: str) -> str:
        if language == "sme":
            return self.sami_model
        return self.norwegian_model

    def ensure_directories(self) -> None:
        for value in (
            self.data_dir,
            self.temp_dir,
            self.work_dir,
            self.output_dir,
            self.debug_dir,
            self.log_dir,
        ):
            Path(value).mkdir(parents=True, exist_ok=True)
        Path(self.queue_db).parent.mkdir(parents=True, exist_ok=True)

    def validate(self) -> None:
        if not self.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN må settes i .env")
        if self.max_file_size_mb <= 0 or self.max_file_size_mb > 2000:
            raise ValueError("MAX_FILE_SIZE_MB må være mellom 1 og 2000")
        if self.telegram_concurrent_updates < 1:
            raise ValueError("TELEGRAM_CONCURRENT_UPDATES må være minst 1")
        if self.main_chunk_seconds < 31:
            raise ValueError("MAIN_CHUNK_SECONDS må være minst 31")
        if not 0 <= self.overlap_seconds < self.main_chunk_seconds / 2:
            raise ValueError(
                "OVERLAP_SECONDS må være null eller positiv og mindre enn halve hoveddelen"
            )
        if self.num_beams < 1:
            raise ValueError("NUM_BEAMS må være minst 1")
        if self.failed_retention_hours < 0 or self.debug_retention_hours < 0:
            raise ValueError("Oppbevaringstid kan ikke være negativ")
        if self.asr_device not in {"auto", "cpu", "mps", "cuda"}:
            raise ValueError("ASR_DEVICE må være auto, cpu, mps eller cuda")
        if not self.temperatures:
            raise ValueError("TEMPERATURES kan ikke være tom")

    @staticmethod
    def get_language_name(code: str) -> str:
        return {
            "no": "Norsk",
            "sme": "Nordsamisk",
            "auto": "Automatisk (eksperimentell)",
        }.get(code, code)


settings = Settings()
