"""Processing and lifecycle management for one durable transcription job."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config.settings import Settings, settings
from src.document_generator import DocumentGenerator
from src.job_queue import JobQueue, TranscriptionJob
from src.transcriber import Transcriber


class JobProcessor:
    """Run FFmpeg, Whisper, and output generation outside Telegram handlers."""

    def __init__(self, queue: JobQueue, config: Settings = settings):
        self.queue = queue
        self.config = config
        self.transcriber = Transcriber(config)
        self.incoming_root = Path(config.temp_dir).resolve()
        self.work_root = Path(config.work_dir).resolve()
        self.output_root = Path(config.output_dir).resolve()
        self.debug_root = Path(config.debug_dir).resolve()
        for directory in (
            self.incoming_root,
            self.work_root,
            self.output_root,
            self.debug_root,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def process(
        self,
        job: TranscriptionJob,
        progress: Callable[[int, str], None],
    ) -> list[Path]:
        work_dir = self.work_root / job.id
        output_dir = self.output_root / job.id
        result = self.transcriber.transcribe(
            job.source_path,
            language=job.language or "no",
            work_dir=work_dir,
            progress=progress,
            should_cancel=lambda: self.queue.is_cancel_requested(job.id),
            glossary=self.config.glossary,
        )
        progress(96, "Lager resultatfiler")
        generator = DocumentGenerator(output_dir)
        paths = generator.generate(
            result, job.original_filename, job.output_format or "both"
        )
        self._write_debug_json(job, result)
        return paths

    def cleanup_success(self, job: TranscriptionJob, result_paths: list[Path]) -> None:
        if self.config.delete_source_after_delivery:
            self._safe_unlink_source(Path(job.source_path))
        shutil.rmtree(self.work_root / job.id, ignore_errors=True)
        for path in result_paths:
            self._safe_unlink_output(path)
        output_job_dir = self.output_root / job.id
        if output_job_dir.exists():
            try:
                output_job_dir.rmdir()
            except OSError:
                pass

    def cleanup_cancelled(self, job: TranscriptionJob) -> None:
        self._safe_unlink_source(Path(job.source_path))
        shutil.rmtree(self.work_root / job.id, ignore_errors=True)
        shutil.rmtree(self.output_root / job.id, ignore_errors=True)

    def purge_expired(self) -> None:
        now = datetime.now(timezone.utc)
        failure_cutoff = now - timedelta(hours=self.config.failed_retention_hours)
        jobs = self.queue.all_jobs()
        for job in jobs:
            if job.status in {"awaiting_language", "awaiting_output"}:
                try:
                    created = datetime.fromisoformat(job.created_at)
                except ValueError:
                    continue
                if created < failure_cutoff:
                    cancelled = self.queue.request_cancel(job.id, job.user_id)
                    if cancelled:
                        self.cleanup_cancelled(cancelled)
                continue
            if job.status != "failed" or not job.finished_at:
                continue
            try:
                finished = datetime.fromisoformat(job.finished_at)
            except ValueError:
                continue
            if finished < failure_cutoff:
                self.cleanup_cancelled(job)

        referenced_sources = {
            Path(job.source_path).resolve()
            for job in jobs
            if job.status
            in {
                "awaiting_language",
                "awaiting_output",
                "queued",
                "processing",
                "failed",
            }
            or (
                job.status == "completed"
                and not self.config.delete_source_after_delivery
            )
        }
        for path in self.incoming_root.iterdir():
            try:
                if (
                    path.is_file()
                    and path.resolve() not in referenced_sources
                    and path.stat().st_mtime < failure_cutoff.timestamp()
                ):
                    path.unlink()
            except FileNotFoundError:
                continue

        debug_cutoff = now.timestamp() - self.config.debug_retention_hours * 3600
        for path in self.debug_root.glob("*.json"):
            try:
                if path.stat().st_mtime < debug_cutoff:
                    path.unlink()
            except FileNotFoundError:
                continue

    def _write_debug_json(self, job, result) -> Path:
        path = self.debug_root / f"{job.id}.json"
        payload = {
            "job_id": job.id,
            "original_filename": job.original_filename,
            "language": result.language,
            "model": result.model_name,
            "duration_seconds": result.duration_seconds,
            "segments": [segment.to_dict() for segment in result.segments],
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return path

    def _safe_unlink_source(self, path: Path) -> None:
        try:
            resolved = path.resolve()
            if resolved.parent == self.incoming_root:
                resolved.unlink(missing_ok=True)
        except FileNotFoundError:
            pass

    def _safe_unlink_output(self, path: Path) -> None:
        try:
            resolved = path.resolve()
            if self.output_root in resolved.parents:
                resolved.unlink(missing_ok=True)
        except FileNotFoundError:
            pass
