#!/usr/bin/env python3
"""Check credentials, binary, directories, local port, and Bot API health."""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from env_file import read_env


def _result(ok: bool, message: str) -> bool:
    print(f"{'✅' if ok else '❌'} {message}")
    return ok


def main() -> None:
    project_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=project_dir / ".env")
    parser.add_argument(
        "--preflight", action="store_true", help="Do not require a running local server"
    )
    parser.add_argument(
        "--require-migration",
        action="store_true",
        help="Require a matching one-time logOut marker",
    )
    args = parser.parse_args()
    values = read_env(args.env_file)
    checks: list[bool] = []

    release_file = project_dir / "AILO_RELEASE"
    release = (
        release_file.read_text(encoding="utf-8").strip()
        if release_file.is_file()
        else ""
    )
    checks.append(_result(bool(release), f"Ailo-kildeversjon: {release or 'mangler'}"))

    required = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_API_ID", "TELEGRAM_API_HASH")
    missing = [key for key in required if not values.get(key)]
    checks.append(
        _result(
            not missing,
            "Telegram-hemmeligheter finnes i .env"
            if not missing
            else f"Mangler i .env: {', '.join(missing)}",
        )
    )
    if args.require_migration:
        token = values.get("TELEGRAM_BOT_TOKEN", "")
        bot_id = token.split(":", 1)[0] if ":" in token else ""
        marker = project_dir / "data" / ".local_api_migration"
        marker_lines = (
            marker.read_text(encoding="utf-8").splitlines() if marker.is_file() else []
        )
        checks.append(
            _result(
                bool(bot_id and marker_lines and marker_lines[0] == bot_id),
                "Engangsovergangen med logOut er registrert",
            )
        )

    binary_value = values.get("TELEGRAM_BOT_API_BINARY", "telegram-bot-api")
    binary = Path(binary_value).expanduser()
    if binary.is_absolute() or "/" in binary_value:
        resolved_binary = binary.resolve()
    else:
        found = shutil.which(binary_value)
        resolved_binary = Path(found) if found else binary
    binary_ok = resolved_binary.is_file() and os.access(resolved_binary, os.X_OK)
    checks.append(_result(binary_ok, f"Bot API-binær: {resolved_binary}"))
    if binary_ok:
        try:
            process_env = os.environ.copy()
            process_env.update(
                {
                    "TELEGRAM_API_ID": values.get("TELEGRAM_API_ID", ""),
                    "TELEGRAM_API_HASH": values.get("TELEGRAM_API_HASH", ""),
                }
            )
            subprocess.run(
                [str(resolved_binary), "--help"],
                check=True,
                env=process_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
            checks.append(_result(True, "Bot API-binæren kan startes"))
        except (OSError, subprocess.SubprocessError):
            checks.append(_result(False, "Bot API-binæren feilet med --help"))

    for key in (
        "TELEGRAM_BOT_API_DATA_DIR",
        "TELEGRAM_BOT_API_TEMP_DIR",
        "TELEGRAM_BOT_API_LOG_DIR",
    ):
        raw_path = values.get(key, "")
        path = Path(raw_path).expanduser()
        ok = bool(raw_path) and path.is_dir() and os.access(path, os.W_OK)
        checks.append(_result(ok, f"Skrivbar mappe {key}: {path}"))

    host = values.get("TELEGRAM_BOT_API_IP_ADDRESS", "127.0.0.1")
    port = int(values.get("TELEGRAM_BOT_API_PORT", "8081"))
    checks.append(
        _result(
            values.get("TELEGRAM_LOCAL_MODE", "").casefold() == "true",
            "TELEGRAM_LOCAL_MODE er aktivert",
        )
    )
    if host != "127.0.0.1":
        checks.append(
            _result(False, f"Serveren er ikke begrenset til 127.0.0.1: {host}")
        )
    else:
        checks.append(_result(True, "Serveren er konfigurert for kun localhost"))

    if not args.preflight:
        try:
            with socket.create_connection((host, port), timeout=3):
                pass
            checks.append(_result(True, f"Lokal Bot API lytter på {host}:{port}"))
        except OSError:
            checks.append(
                _result(False, f"Ingen lokal Bot API svarer på {host}:{port}")
            )

        token = values.get("TELEGRAM_BOT_TOKEN", "")
        if token:
            try:
                with urllib.request.urlopen(
                    f"http://{host}:{port}/bot{token}/getMe", timeout=10
                ) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                checks.append(
                    _result(
                        payload.get("ok") is True, "Lokal getMe godkjente bot-tokenet"
                    )
                )
            except (OSError, urllib.error.URLError, json.JSONDecodeError):
                checks.append(_result(False, "Lokal getMe feilet"))

        if sys.platform == "darwin":
            label = "com.daikosapmi.telegram-transcriber"
            plist_path = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
            try:
                with plist_path.open("rb") as plist_file:
                    plist = plistlib.load(plist_file)
                arguments = plist.get("ProgramArguments", [])
                expected_start = str(project_dir / "start.sh")
                actual_start = arguments[1] if len(arguments) > 1 else ""
                checks.append(
                    _result(
                        actual_start == expected_start,
                        f"LaunchAgent bruker denne prosjektmappen: {actual_start}",
                    )
                )
            except (OSError, plistlib.InvalidFileException):
                checks.append(
                    _result(False, f"Kunne ikke lese LaunchAgent: {plist_path}")
                )

            launchctl = subprocess.run(
                ["launchctl", "print", f"gui/{os.getuid()}/{label}"],
                capture_output=True,
                text=True,
                check=False,
            )
            checks.append(
                _result(
                    launchctl.returncode == 0 and "state = running" in launchctl.stdout,
                    "Ny Ailo LaunchAgent kjører",
                )
            )

    if not all(checks):
        raise SystemExit(1)
    print("\nAlle kontroller bestått.")


if __name__ == "__main__":
    main()
