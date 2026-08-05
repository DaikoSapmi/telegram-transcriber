from pathlib import Path

from src.job_queue import JobQueue


def create_job(queue: JobQueue, number: int = 1):
    return queue.create(
        chat_id=10,
        user_id=20,
        message_id=30 + number,
        telegram_file_id=f"telegram-{number}",
        original_filename=f"meeting-{number}.m4a",
        source_path=f"/tmp/meeting-{number}.m4a",
    )


def test_selection_queue_claim_and_completion_are_persistent(tmp_path: Path):
    db = tmp_path / "jobs.sqlite3"
    queue = JobQueue(db)
    job = create_job(queue)

    assert job.status == "awaiting_language"
    assert queue.set_language(job.id, 20, "sme").status == "awaiting_output"
    assert queue.enqueue(job.id, 20, "both").status == "queued"
    assert queue.position(job.id) == 1

    reopened = JobQueue(db)
    claimed = reopened.claim_next()
    assert claimed.id == job.id
    assert claimed.language == "sme"
    assert claimed.output_format == "both"
    assert claimed.attempts == 1

    reopened.update_progress(job.id, 42, "Transkriberer del 2 av 5")
    assert reopened.get(job.id).progress == 42
    reopened.mark_completed(job.id, ["one.txt", "one.docx"])
    completed = reopened.get(job.id)
    assert completed.status == "completed"
    assert completed.result_paths == ["one.txt", "one.docx"]


def test_restart_recovers_processing_job(tmp_path: Path):
    queue = JobQueue(tmp_path / "jobs.sqlite3")
    job = create_job(queue)
    queue.set_language(job.id, 20, "no")
    queue.enqueue(job.id, 20, "txt")
    queue.claim_next()

    assert queue.recover_interrupted() == 1
    recovered = queue.get(job.id)
    assert recovered.status == "queued"
    assert recovered.progress_text == "Gjenopptas etter omstart"


def test_cancel_queued_and_processing_jobs(tmp_path: Path):
    queue = JobQueue(tmp_path / "jobs.sqlite3")
    queued = create_job(queue, 1)
    queue.set_language(queued.id, 20, "no")
    queue.enqueue(queued.id, 20, "txt")
    assert queue.request_cancel(queued.id, 20).status == "cancelled"

    running = create_job(queue, 2)
    queue.set_language(running.id, 20, "sme")
    queue.enqueue(running.id, 20, "docx")
    queue.claim_next()
    requested = queue.request_cancel(running.id, 20)
    assert requested.status == "processing"
    assert requested.cancel_requested is True
    assert queue.recover_interrupted() == 0
    assert queue.get(running.id).status == "cancelled"
