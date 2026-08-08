import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telegram.ext import CommandHandler

from config.settings import Settings
from src.telegram_bot import AILO_RELEASE, TranscriptionBot


def test_local_bot_api_urls_are_applied(tmp_path: Path):
    config = Settings(
        telegram_bot_token="123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
        telegram_local_mode=True,
        telegram_base_url="http://127.0.0.1:9000/bot",
        telegram_base_file_url="http://127.0.0.1:9000/file/bot",
        data_dir=str(tmp_path),
        temp_dir=str(tmp_path / "incoming"),
        work_dir=str(tmp_path / "work"),
        output_dir=str(tmp_path / "output"),
        debug_dir=str(tmp_path / "debug"),
        queue_db=str(tmp_path / "jobs.sqlite3"),
        log_dir=str(tmp_path / "logs"),
    )
    bot = TranscriptionBot(config)
    application = bot.build_application()

    assert str(application.bot.base_url).startswith("http://127.0.0.1:9000/bot")
    assert str(application.bot.base_file_url).startswith(
        "http://127.0.0.1:9000/file/bot"
    )
    assert application.bot.local_mode is True
    assert application.update_processor.max_concurrent_updates == 4
    commands = {
        command
        for handlers in application.handlers.values()
        for handler in handlers
        if isinstance(handler, CommandHandler)
        for command in handler.commands
    }
    assert "version" in commands
    assert "driftstatus" in commands
    assert "health" in commands
    assert "hjelp" in commands
    assert AILO_RELEASE == "pure-transcription-2026.08.08-segmented"


def test_language_choice_is_explicit_and_has_no_automatic_frontend_option():
    keyboard = TranscriptionBot._language_keyboard("job-1")
    buttons = [row[0] for row in keyboard.inline_keyboard]

    assert TranscriptionBot.FRONTEND_LANGUAGES == {"no", "sme"}
    assert [button.callback_data for button in buttons] == [
        "lang:job-1:no",
        "lang:job-1:sme",
    ]
    labels = " ".join(button.text for button in buttons)
    assert "Norsk tale → norsk tekst" in labels
    assert "Nordsamisk tale → nordsamisk tekst" in labels
    assert "Automatisk" not in labels


def test_ailo_explains_same_language_and_no_postprocessing():
    prompt = TranscriptionBot._language_prompt("møte.m4a")

    assert "språket som faktisk snakkes" in prompt
    assert "Norsk tale gir norsk tekst" in prompt
    assert "Nordsamisk tale gir nordsamisk tekst" in prompt
    assert "oversetter ikke" in prompt
    assert "Ingen oversettelse" in TranscriptionBot.PURE_TRANSCRIPTION_NOTE
    assert "språkvask" in TranscriptionBot.PURE_TRANSCRIPTION_NOTE
    assert "sammendrag" in TranscriptionBot.PURE_TRANSCRIPTION_NOTE


def test_runtime_health_reports_components_and_empty_queue(tmp_path: Path):
    config = Settings(
        telegram_bot_token="123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
        telegram_local_mode=True,
        data_dir=str(tmp_path),
        temp_dir=str(tmp_path / "incoming"),
        work_dir=str(tmp_path / "work"),
        output_dir=str(tmp_path / "output"),
        debug_dir=str(tmp_path / "debug"),
        queue_db=str(tmp_path / "jobs.sqlite3"),
        log_dir=str(tmp_path / "logs"),
    )
    bot = TranscriptionBot(config)
    bot.worker_task = SimpleNamespace(done=lambda: False)
    bot._local_api_is_reachable = AsyncMock(return_value=True)
    bot._model_cache_checks = lambda: (("Norsk", True), ("Nordsamisk", True))
    reply_text = AsyncMock()
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(type="private"),
        effective_user=SimpleNamespace(id=42, username="daiko"),
        effective_message=SimpleNamespace(reply_text=reply_text),
    )

    asyncio.run(bot._cmd_runtime_health(update, None))

    message = reply_text.await_args.args[0]
    assert "alle hovedkomponenter svarer" in message
    assert "Køarbeider: kjører" in message
    assert "Lokal Telegram Bot API: svarer" in message
    assert "✅ Norsk Whisper-modell: nedlastet" in message
    assert "✅ Nordsamisk Whisper-modell: nedlastet" in message
    assert "Behandles nå: 0" in message
    assert "Venter i kø: 0" in message
    assert "Bruk /status" in message


def test_runtime_health_formats_heartbeat_age():
    assert TranscriptionBot._format_elapsed(2) == "nå"
    assert TranscriptionBot._format_elapsed(45) == "for 45 sekunder siden"
    assert TranscriptionBot._format_elapsed(125) == "for 2 minutter siden"
    assert TranscriptionBot._format_elapsed(7200) == "for 2 timer siden"


def test_runtime_health_marks_a_missing_model(tmp_path: Path):
    config = Settings(
        telegram_bot_token="123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
        telegram_local_mode=True,
        data_dir=str(tmp_path),
        temp_dir=str(tmp_path / "incoming"),
        work_dir=str(tmp_path / "work"),
        output_dir=str(tmp_path / "output"),
        debug_dir=str(tmp_path / "debug"),
        queue_db=str(tmp_path / "jobs.sqlite3"),
        log_dir=str(tmp_path / "logs"),
    )
    bot = TranscriptionBot(config)
    bot.worker_task = SimpleNamespace(done=lambda: False)
    bot._local_api_is_reachable = AsyncMock(return_value=True)
    bot._model_cache_checks = lambda: (("Norsk", True), ("Nordsamisk", False))
    reply_text = AsyncMock()
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(type="private"),
        effective_user=SimpleNamespace(id=42, username="daiko"),
        effective_message=SimpleNamespace(reply_text=reply_text),
    )

    asyncio.run(bot._cmd_runtime_health(update, None))

    message = reply_text.await_args.args[0]
    assert "minst én kontroll feilet" in message
    assert "✅ Norsk Whisper-modell: nedlastet" in message
    assert "❌ Nordsamisk Whisper-modell: mangler" in message


def test_runtime_health_reports_one_processing_and_one_queued_job(tmp_path: Path):
    config = Settings(
        telegram_bot_token="123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
        telegram_local_mode=True,
        data_dir=str(tmp_path),
        temp_dir=str(tmp_path / "incoming"),
        work_dir=str(tmp_path / "work"),
        output_dir=str(tmp_path / "output"),
        debug_dir=str(tmp_path / "debug"),
        queue_db=str(tmp_path / "jobs.sqlite3"),
        log_dir=str(tmp_path / "logs"),
    )
    bot = TranscriptionBot(config)
    for number in (1, 2):
        job = bot.queue.create(
            chat_id=42,
            user_id=42,
            message_id=number,
            telegram_file_id=f"file-{number}",
            original_filename=f"opptak-{number}.m4a",
            source_path=str(tmp_path / f"opptak-{number}.m4a"),
        )
        bot.queue.set_language(job.id, 42, "no")
        bot.queue.enqueue(job.id, 42, "docx")
    current = bot.queue.claim_next()
    assert current is not None
    bot.queue.update_progress(current.id, 37, "Transkriberer del 1 av 2")
    bot.worker_task = SimpleNamespace(done=lambda: False)
    bot._local_api_is_reachable = AsyncMock(return_value=True)
    bot._model_cache_checks = lambda: (("Norsk", True), ("Nordsamisk", True))
    reply_text = AsyncMock()
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(type="private"),
        effective_user=SimpleNamespace(id=42, username="daiko"),
        effective_message=SimpleNamespace(reply_text=reply_text),
    )

    asyncio.run(bot._cmd_runtime_health(update, None))

    message = reply_text.await_args.args[0]
    assert "Behandles nå: 1" in message
    assert "Venter i kø: 1" in message
    assert "Fremdrift nå: 37% · Transkriberer del 1 av 2" in message
    assert "Dine aktive jobber: 2" in message


def test_hjelp_command_lists_all_commands(tmp_path: Path):
    config = Settings(
        telegram_bot_token="123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
        data_dir=str(tmp_path),
        temp_dir=str(tmp_path / "incoming"),
        work_dir=str(tmp_path / "work"),
        output_dir=str(tmp_path / "output"),
        debug_dir=str(tmp_path / "debug"),
        queue_db=str(tmp_path / "jobs.sqlite3"),
        log_dir=str(tmp_path / "logs"),
    )
    bot = TranscriptionBot(config)
    reply_text = AsyncMock()
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(type="private"),
        effective_user=SimpleNamespace(id=42, username="daiko"),
        effective_message=SimpleNamespace(reply_text=reply_text),
    )

    asyncio.run(bot._cmd_commands(update, None))

    message = reply_text.await_args.args[0]
    for command in (
        "/status",
        "/driftstatus",
        "/cancel",
        "/version",
        "/help",
        "/start",
        "/hjelp",
    ):
        assert command in message
