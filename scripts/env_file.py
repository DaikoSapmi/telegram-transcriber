"""Small, dependency-free reader and updater for the project's .env file."""

from __future__ import annotations

import re
import shlex
from pathlib import Path

KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
LINE_PATTERN = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
SAFE_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9_./:@,+\-=]*$")


def read_env(path: str | Path) -> dict[str, str]:
    env_path = Path(path)
    if not env_path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        match = LINE_PATTERN.match(line)
        if not match:
            continue
        key, raw_value = match.groups()
        raw_value = raw_value.strip()
        if not raw_value:
            values[key] = ""
            continue
        try:
            parsed = shlex.split(raw_value, comments=True, posix=True)
        except ValueError:
            values[key] = raw_value
            continue
        values[key] = parsed[0] if parsed else ""
    return values


def quote_env_value(value: str) -> str:
    if SAFE_VALUE_PATTERN.fullmatch(value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$")
    return f'"{escaped}"'


def update_env(path: str | Path, updates: dict[str, str]) -> None:
    env_path = Path(path)
    invalid = [key for key in updates if not KEY_PATTERN.fullmatch(key)]
    if invalid:
        raise ValueError(f"Ugyldige miljøvariabler: {', '.join(invalid)}")

    existing_lines = (
        env_path.read_text(encoding="utf-8").splitlines() if env_path.is_file() else []
    )
    written: set[str] = set()
    output: list[str] = []
    for line in existing_lines:
        match = LINE_PATTERN.match(line)
        key = match.group(1) if match else None
        if key in updates:
            if key not in written:
                output.append(f"{key}={quote_env_value(updates[key])}")
                written.add(key)
        else:
            output.append(line)

    remaining = {key: value for key, value in updates.items() if key not in written}
    if remaining:
        if output and output[-1].strip():
            output.append("")
        output.append(
            "# Local Telegram Bot API (managed by scripts/configure_telegram_env.py)"
        )
        output.extend(
            f"{key}={quote_env_value(value)}" for key, value in remaining.items()
        )

    env_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = env_path.with_suffix(env_path.suffix + ".tmp")
    temporary.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(env_path)
    env_path.chmod(0o600)
