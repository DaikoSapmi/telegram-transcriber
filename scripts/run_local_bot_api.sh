#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

if [[ ! -f ".env" ]]; then
    echo ".env mangler" >&2
    exit 1
fi
set -a
source .env
set +a

: "${TELEGRAM_API_ID:?TELEGRAM_API_ID mangler i .env}"
: "${TELEGRAM_API_HASH:?TELEGRAM_API_HASH mangler i .env}"

BOT_API_BINARY="${TELEGRAM_BOT_API_BINARY:-telegram-bot-api}"
BOT_API_PORT="${TELEGRAM_BOT_API_PORT:-8081}"
BOT_API_IP_ADDRESS="${TELEGRAM_BOT_API_IP_ADDRESS:-127.0.0.1}"
BOT_API_DIR="${TELEGRAM_BOT_API_DATA_DIR:-$PROJECT_DIR/data/telegram-bot-api}"
BOT_API_TEMP_DIR="${TELEGRAM_BOT_API_TEMP_DIR:-$PROJECT_DIR/data/telegram-bot-api-temp}"
BOT_API_LOG_DIR="${TELEGRAM_BOT_API_LOG_DIR:-$PROJECT_DIR/logs}"
mkdir -p "$BOT_API_DIR" "$BOT_API_TEMP_DIR" "$BOT_API_LOG_DIR"

if [[ "$BOT_API_IP_ADDRESS" != "127.0.0.1" ]]; then
    echo "TELEGRAM_BOT_API_IP_ADDRESS må være 127.0.0.1 av sikkerhetsgrunner." >&2
    exit 1
fi
if [[ "$BOT_API_BINARY" == */* ]]; then
    if [[ ! -x "$BOT_API_BINARY" ]]; then
        echo "Bot API-binæren finnes ikke eller er ikke kjørbar: $BOT_API_BINARY" >&2
        exit 1
    fi
elif ! command -v "$BOT_API_BINARY" >/dev/null 2>&1; then
    echo "Bot API-binæren finnes ikke i PATH: $BOT_API_BINARY" >&2
    exit 1
fi

exec "$BOT_API_BINARY" \
    --http-ip-address="$BOT_API_IP_ADDRESS" \
    --http-port="${BOT_API_PORT}" \
    --dir="$BOT_API_DIR" \
    --temp-dir="$BOT_API_TEMP_DIR" \
    --log="$BOT_API_LOG_DIR/telegram-bot-api.log" \
    --log-max-file-size=100000000 \
    --verbosity=1 \
    --local
