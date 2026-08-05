import stat
import subprocess
import sys
from pathlib import Path

from scripts.env_file import read_env, update_env


def test_update_env_preserves_comments_quotes_spaces_and_mode(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "# Existing comment\nTELEGRAM_API_ID=old\nTELEGRAM_API_ID=duplicate\nKEEP_ME=yes\n",
        encoding="utf-8",
    )
    update_env(
        env_path,
        {
            "TELEGRAM_API_ID": "123456",
            "TELEGRAM_BOT_API_DATA_DIR": "/Users/Test/Library/Application Support/data",
        },
    )

    text = env_path.read_text(encoding="utf-8")
    values = read_env(env_path)
    assert text.count("TELEGRAM_API_ID=") == 1
    assert "# Existing comment" in text
    assert values["TELEGRAM_API_ID"] == "123456"
    assert (
        values["TELEGRAM_BOT_API_DATA_DIR"]
        == "/Users/Test/Library/Application Support/data"
    )
    assert values["KEEP_ME"] == "yes"
    assert stat.S_IMODE(env_path.stat().st_mode) == 0o600


def test_diagnostic_preflight_runs_with_valid_local_configuration(tmp_path: Path):
    env_path = tmp_path / ".env"
    data_dir = tmp_path / "data"
    temp_dir = tmp_path / "temp"
    log_dir = tmp_path / "logs"
    for directory in (data_dir, temp_dir, log_dir):
        directory.mkdir()
    update_env(
        env_path,
        {
            "TELEGRAM_BOT_TOKEN": "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef",
            "TELEGRAM_API_ID": "123456",
            "TELEGRAM_API_HASH": "0123456789abcdef0123456789abcdef",
            "TELEGRAM_BOT_API_BINARY": sys.executable,
            "TELEGRAM_BOT_API_DATA_DIR": str(data_dir),
            "TELEGRAM_BOT_API_TEMP_DIR": str(temp_dir),
            "TELEGRAM_BOT_API_LOG_DIR": str(log_dir),
            "TELEGRAM_BOT_API_IP_ADDRESS": "127.0.0.1",
            "TELEGRAM_BOT_API_PORT": "8081",
            "TELEGRAM_LOCAL_MODE": "true",
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/diagnose_local_setup.py",
            "--preflight",
            "--env-file",
            str(env_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
