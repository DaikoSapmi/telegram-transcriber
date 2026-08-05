#!/usr/bin/env python3
"""Interactively store Telegram credentials and local server paths in .env."""

from __future__ import annotations

import argparse
import getpass
import os
import re
from pathlib import Path

from env_file import read_env, update_env

BOT_TOKEN_PATTERN = re.compile(r"^(\d+):[A-Za-z0-9_-]{20,}$")
API_HASH_PATTERN = re.compile(r"^[A-Fa-f0-9]{32}$")


def _plain_prompt(label: str, current: str = "") -> str:
    suffix = f" [{current}]" if current else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or current


def _secret_prompt(label: str, current: str = "") -> str:
    suffix = " [trykk Enter for å beholde eksisterende]" if current else ""
    value = getpass.getpass(f"{label}{suffix}: ").strip()
    return value or current


def main() -> None:
    project_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=project_dir / ".env")
    parser.add_argument("--bot-api-binary", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--temp-dir", type=Path, required=True)
    parser.add_argument("--log-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8081)
    args = parser.parse_args()

    binary = args.bot_api_binary.expanduser().resolve()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise SystemExit(f"Bot API-binæren finnes ikke eller er ikke kjørbar: {binary}")
    if not 1 <= args.port <= 65535:
        raise SystemExit("Porten må være mellom 1 og 65535")

    current = read_env(args.env_file)
    print("\nTelegram har tre relevante verdier:")
    print("  1. TELEGRAM_API_ID og 2. TELEGRAM_API_HASH fra my.telegram.org")
    print("  3. TELEGRAM_BOT_TOKEN fra @BotFather")
    print(
        "Bot-ID er tallet før kolon i bot-tokenet og trenger ikke en egen variabel.\n"
    )

    api_id = _plain_prompt("Telegram App api_id", current.get("TELEGRAM_API_ID", ""))
    while not api_id.isdigit():
        print("api_id skal bare inneholde sifre.")
        api_id = _plain_prompt("Telegram App api_id", api_id)

    api_hash = _secret_prompt(
        "Telegram App api_hash", current.get("TELEGRAM_API_HASH", "")
    )
    while not API_HASH_PATTERN.fullmatch(api_hash):
        print("api_hash skal være 32 heksadesimale tegn.")
        api_hash = _secret_prompt("Telegram App api_hash")

    bot_token = _secret_prompt(
        "Bot-token fra @BotFather", current.get("TELEGRAM_BOT_TOKEN", "")
    )
    while not BOT_TOKEN_PATTERN.fullmatch(bot_token):
        print("Bot-tokenet skal ha formatet <bot-id>:<hemmelig token>.")
        bot_token = _secret_prompt("Bot-token fra @BotFather")

    allowed_users = _plain_prompt(
        "Tillatte Telegram-ID-er eller @brukernavn, kommaseparert",
        current.get("ALLOWED_USERS", ""),
    )
    if not allowed_users:
        print("ADVARSEL: Tom ALLOWED_USERS tillater alle som finner boten.")

    for directory in (args.data_dir, args.temp_dir, args.log_dir):
        directory.expanduser().resolve().mkdir(parents=True, exist_ok=True)

    updates = {
        "TELEGRAM_BOT_TOKEN": bot_token,
        "TELEGRAM_API_ID": api_id,
        "TELEGRAM_API_HASH": api_hash,
        "ALLOWED_USERS": allowed_users,
        "TELEGRAM_LOCAL_MODE": "true",
        "TELEGRAM_BASE_URL": f"http://127.0.0.1:{args.port}/bot",
        "TELEGRAM_BASE_FILE_URL": f"http://127.0.0.1:{args.port}/file/bot",
        "TELEGRAM_BOT_API_PORT": str(args.port),
        "TELEGRAM_BOT_API_IP_ADDRESS": "127.0.0.1",
        "TELEGRAM_BOT_API_BINARY": str(binary),
        "TELEGRAM_BOT_API_DATA_DIR": str(args.data_dir.expanduser().resolve()),
        "TELEGRAM_BOT_API_TEMP_DIR": str(args.temp_dir.expanduser().resolve()),
        "TELEGRAM_BOT_API_LOG_DIR": str(args.log_dir.expanduser().resolve()),
    }
    update_env(args.env_file, updates)
    print(f"\nKonfigurasjonen er lagret med filmodus 600 i {args.env_file}")
    print(f"Registrert bot-ID: {BOT_TOKEN_PATTERN.fullmatch(bot_token).group(1)}")


if __name__ == "__main__":
    main()
