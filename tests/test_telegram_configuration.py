from pathlib import Path

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
    application = TranscriptionBot(config).build_application()

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
    assert AILO_RELEASE == "pure-transcription-2026.08.06"


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
