import os
import time
from pathlib import Path

from config.settings import Settings
from src.job_processor import JobProcessor
from src.job_queue import JobQueue


def test_old_orphaned_download_is_removed(tmp_path: Path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    orphan = incoming / "orphan.m4a"
    orphan.write_bytes(b"orphan")
    old = time.time() - 49 * 3600
    os.utime(orphan, (old, old))

    config = Settings(
        temp_dir=str(incoming),
        work_dir=str(tmp_path / "work"),
        output_dir=str(tmp_path / "output"),
        debug_dir=str(tmp_path / "debug"),
        queue_db=str(tmp_path / "jobs.sqlite3"),
        failed_retention_hours=48,
    )
    queue = JobQueue(config.queue_db)
    JobProcessor(queue, config).purge_expired()

    assert not orphan.exists()
