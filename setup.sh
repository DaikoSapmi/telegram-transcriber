#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 mangler. Installer Python 3.10 eller nyere." >&2
    exit 1
fi
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "FFmpeg mangler. Installer med: brew install ffmpeg" >&2
    exit 1
fi

python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else "Python 3.10+ kreves")'

if [[ ! -d "venv" ]]; then
    python3 -m venv venv
fi
"$PROJECT_DIR/venv/bin/python" -m pip install --upgrade pip
"$PROJECT_DIR/venv/bin/python" -m pip install -r requirements.txt

mkdir -p data/incoming data/work data/output data/debug logs
if [[ ! -f ".env" ]]; then
    cp .env.example .env
    echo "Opprettet .env. Legg inn Telegram-verdiene før oppstart."
fi
chmod 600 .env

echo
echo "Laster ned og validerer begge Whisper-modellene."
echo "Første installasjon trenger omtrent 12,4 GB modellvekter og viser fremdrift underveis."
"$PROJECT_DIR/venv/bin/python" scripts/download_models.py

echo "Oppsett fullført. Kjør ./start.sh, eller installer launchd med ./scripts/install_launchd.sh."
