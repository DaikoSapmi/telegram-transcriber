from pathlib import Path

from config.settings import Settings
from src.telegram_bot import TranscriptionBot


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
