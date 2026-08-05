"""Durable SQLite job queue used by the Telegram front end and worker."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

ACTIVE_STATUSES = ("awaiting_language", "awaiting_output", "queued", "processing")
TERMINAL_STATUSES = ("completed", "failed", "cancelled")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class TranscriptionJob:
    id: str
    chat_id: int
    user_id: int
    message_id: int
    telegram_file_id: str
    original_filename: str
    source_path: str
    language: str | None
    output_format: str | None
    status: str
    progress: int
    progress_text: str
    error: str | None
    result_paths: list[str]
    cancel_requested: bool
    attempts: int
    created_at: str
    updated_at: str
    started_at: str | None
    finished_at: str | None

    def to_dict(self) -> dict:
        return asdict(self)


class JobQueue:
    """Small durable queue with atomic claiming and restart recovery."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    telegram_file_id TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    language TEXT,
                    output_format TEXT,
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL DEFAULT 0,
                    progress_text TEXT NOT NULL DEFAULT '',
                    error TEXT,
                    result_paths TEXT NOT NULL DEFAULT '[]',
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_user_created ON jobs(user_id, created_at DESC)"
            )

    @staticmethod
    def _row_to_job(row: sqlite3.Row | None) -> TranscriptionJob | None:
        if row is None:
            return None
        values = dict(row)
        values["result_paths"] = json.loads(values["result_paths"] or "[]")
        values["cancel_requested"] = bool(values["cancel_requested"])
        return TranscriptionJob(**values)

    def create(
        self,
        *,
        chat_id: int,
        user_id: int,
        message_id: int,
        telegram_file_id: str,
        original_filename: str,
        source_path: str,
    ) -> TranscriptionJob:
        job_id = uuid.uuid4().hex[:12]
        now = _utc_now()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    id, chat_id, user_id, message_id, telegram_file_id,
                    original_filename, source_path, status, progress,
                    progress_text, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'awaiting_language', 0, 'Venter på språkvalg', ?, ?)
                """,
                (
                    job_id,
                    chat_id,
                    user_id,
                    message_id,
                    telegram_file_id,
                    original_filename,
                    source_path,
                    now,
                    now,
                ),
            )
        return self.get(job_id)  # type: ignore[return-value]

    def get(self, job_id: str) -> TranscriptionJob | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
        return self._row_to_job(row)

    def set_language(
        self, job_id: str, user_id: int, language: str
    ) -> TranscriptionJob | None:
        if language not in {"no", "sme", "auto"}:
            raise ValueError(f"Ugyldig språk: {language}")
        now = _utc_now()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET language = ?, status = 'awaiting_output',
                    progress_text = 'Venter på resultatvalg', updated_at = ?
                WHERE id = ? AND user_id = ? AND status = 'awaiting_language'
                """,
                (language, now, job_id, user_id),
            )
        return self.get(job_id) if cursor.rowcount else None

    def enqueue(
        self, job_id: str, user_id: int, output_format: str
    ) -> TranscriptionJob | None:
        if output_format not in {"txt", "docx", "both"}:
            raise ValueError(f"Ugyldig resultatformat: {output_format}")
        now = _utc_now()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET output_format = ?, status = 'queued', progress = 0,
                    progress_text = 'Venter i kø', updated_at = ?
                WHERE id = ? AND user_id = ? AND status = 'awaiting_output'
                """,
                (output_format, now, job_id, user_id),
            )
        return self.get(job_id) if cursor.rowcount else None

    def claim_next(self) -> TranscriptionJob | None:
        now = _utc_now()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT id FROM jobs WHERE status = 'queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row is None:
                connection.execute("COMMIT")
                return None
            connection.execute(
                """
                UPDATE jobs
                SET status = 'processing', progress = 1,
                    progress_text = 'Starter', started_at = COALESCE(started_at, ?),
                    updated_at = ?, attempts = attempts + 1
                WHERE id = ? AND status = 'queued'
                """,
                (now, now, row["id"]),
            )
            claimed = connection.execute(
                "SELECT * FROM jobs WHERE id = ?", (row["id"],)
            ).fetchone()
            connection.execute("COMMIT")
        return self._row_to_job(claimed)

    def update_progress(self, job_id: str, progress: int, text: str) -> None:
        progress = max(0, min(99, int(progress)))
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs SET progress = ?, progress_text = ?, updated_at = ?
                WHERE id = ? AND status = 'processing'
                """,
                (progress, text, _utc_now(), job_id),
            )

    def request_cancel(self, job_id: str, user_id: int) -> TranscriptionJob | None:
        now = _utc_now()
        with self._lock, self._connect() as connection:
            job = connection.execute(
                "SELECT status FROM jobs WHERE id = ? AND user_id = ?",
                (job_id, user_id),
            ).fetchone()
            if job is None or job["status"] not in ACTIVE_STATUSES:
                return None
            if job["status"] == "processing":
                connection.execute(
                    "UPDATE jobs SET cancel_requested = 1, progress_text = 'Avbryter', updated_at = ? WHERE id = ?",
                    (now, job_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE jobs SET status = 'cancelled', cancel_requested = 1,
                        progress_text = 'Avbrutt', updated_at = ?, finished_at = ?
                    WHERE id = ?
                    """,
                    (now, now, job_id),
                )
        return self.get(job_id)

    def is_cancel_requested(self, job_id: str) -> bool:
        job = self.get(job_id)
        return bool(job and job.cancel_requested)

    def mark_completed(self, job_id: str, result_paths: Iterable[str]) -> None:
        now = _utc_now()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs SET status = 'completed', progress = 100,
                    progress_text = 'Ferdig', result_paths = ?, error = NULL,
                    updated_at = ?, finished_at = ? WHERE id = ?
                """,
                (json.dumps(list(result_paths), ensure_ascii=False), now, now, job_id),
            )

    def mark_failed(self, job_id: str, error: str) -> None:
        now = _utc_now()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs SET status = 'failed', progress_text = 'Feilet', error = ?,
                    updated_at = ?, finished_at = ? WHERE id = ?
                """,
                (error[:4000], now, now, job_id),
            )

    def mark_cancelled(self, job_id: str) -> None:
        now = _utc_now()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs SET status = 'cancelled', progress_text = 'Avbrutt',
                    cancel_requested = 1, updated_at = ?, finished_at = ? WHERE id = ?
                """,
                (now, now, job_id),
            )

    def recover_interrupted(self) -> int:
        """Put jobs interrupted by process termination back at the front of the queue."""
        now = _utc_now()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs SET status = 'cancelled', progress_text = 'Avbrutt',
                    updated_at = ?, finished_at = ?
                WHERE status = 'processing' AND cancel_requested = 1
                """,
                (now, now),
            )
            cursor = connection.execute(
                """
                UPDATE jobs SET status = 'queued', progress = 0,
                    progress_text = 'Gjenopptas etter omstart', updated_at = ?
                WHERE status = 'processing' AND cancel_requested = 0
                """,
                (now,),
            )
        return cursor.rowcount

    def position(self, job_id: str) -> int | None:
        job = self.get(job_id)
        if not job or job.status != "queued":
            return None
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS jobs_ahead FROM jobs
                WHERE status = 'queued' AND created_at < ?
                """,
                (job.created_at,),
            ).fetchone()
        return int(row["jobs_ahead"]) + 1

    def active_for_user(self, user_id: int) -> list[TranscriptionJob]:
        placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM jobs WHERE user_id = ? AND status IN ({placeholders}) ORDER BY created_at",
                (user_id, *ACTIVE_STATUSES),
            ).fetchall()
        return [self._row_to_job(row) for row in rows if row is not None]  # type: ignore[misc]

    def latest_active_for_user(self, user_id: int) -> TranscriptionJob | None:
        jobs = self.active_for_user(user_id)
        return jobs[-1] if jobs else None

    def latest_for_user(self, user_id: int) -> TranscriptionJob | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()
        return self._row_to_job(row)

    def all_jobs(self) -> list[TranscriptionJob]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at"
            ).fetchall()
        return [self._row_to_job(row) for row in rows if row is not None]  # type: ignore[misc]
