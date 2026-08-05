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
if [[ ! -s "AILO_RELEASE" ]]; then
    echo "AILO_RELEASE mangler eller er tom." >&2
    exit 1
fi

echo "Starter Ailo $(<AILO_RELEASE) fra $PROJECT_DIR"
exec "$PROJECT_DIR/venv/bin/python" -m src.telegram_bot
