#!/usr/bin/env python3
"""Perform the one-time cloud Bot API logOut before local Bot API startup."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from env_file import read_env


def main() -> None:
    project_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=project_dir / ".env")
    parser.add_argument(
        "--yes", action="store_true", help="Skip the explicit confirmation"
    )
    parser.add_argument(
        "--force", action="store_true", help="Repeat logOut for the same bot"
    )
    args = parser.parse_args()

    values = read_env(args.env_file)
    token = values.get("TELEGRAM_BOT_TOKEN", "")
    if ":" not in token or not token.split(":", 1)[0].isdigit():
        raise SystemExit("TELEGRAM_BOT_TOKEN mangler eller er ugyldig i .env")
    bot_id = token.split(":", 1)[0]
    marker = project_dir / "data" / ".local_api_migration"
    marker_lines = (
        marker.read_text(encoding="utf-8").splitlines() if marker.is_file() else []
    )
    if marker_lines and marker_lines[0] == bot_id and not args.force:
        print(f"Bot {bot_id} er allerede registrert som flyttet til lokal API.")
        return

    if not args.yes:
        print("Dette logger boten ut av Telegrams offisielle Bot API-server.")
        print("Stopp andre prosesser som bruker boten før du fortsetter.")
        confirmation = input(f"Skriv bot-ID {bot_id} for å fortsette: ").strip()
        if confirmation != bot_id:
            raise SystemExit("Avbrutt uten endringer.")

    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/logOut",
        data=b"",
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
        raise SystemExit(f"Telegram logOut feilet: {error}") from error
    if not payload.get("ok") or payload.get("result") is not True:
        raise SystemExit(
            f"Telegram avviste logOut: {payload.get('description', payload)}"
        )

    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        f"{bot_id}\n{datetime.now(timezone.utc).isoformat()}\n", encoding="utf-8"
    )
    marker.chmod(0o600)
    print(
        "Bot-en er logget ut av sky-API-et og kan startes på lokal Bot API-server nå."
    )
    print(
        "Telegram tillater ikke flytting tilbake til skyserveren de første 10 minuttene."
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nAvbrutt uten endringer.")
