#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

if [[ ! -x "venv/bin/python" ]]; then
    echo "Virtual environment mangler. Kjør ./setup.sh først." >&2
    exit 1
fi
if [[ ! -f ".env" ]]; then
    echo ".env mangler. Kopier .env.example og fyll inn verdiene." >&2
    exit 1
fi

exec "$PROJECT_DIR/venv/bin/python" -m src.telegram_bot
