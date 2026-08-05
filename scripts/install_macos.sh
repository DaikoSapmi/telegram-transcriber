#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE_DIR="${TELEGRAM_BOT_API_SOURCE_DIR:-$HOME/telegram-bot-api}"
BUILD_DIR="$SOURCE_DIR/build-local-transcriber"
DATA_DIR="$HOME/Library/Application Support/telegram-bot-api/data"
TEMP_DIR="$HOME/Library/Application Support/telegram-bot-api/temp"
LOG_DIR="$HOME/Library/Logs/telegram-bot-api"

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "Dette installasjonsskriptet er bare for macOS." >&2
    exit 1
fi

echo "Telegram Transcriber – macOS-installasjon"
echo "Kontoopplysninger hentes fra my.telegram.org og @BotFather."
echo

if ! xcode-select -p >/dev/null 2>&1; then
    echo "Xcode Command Line Tools mangler. Kjør først:" >&2
    echo "  xcode-select --install" >&2
    echo "Start deretter dette skriptet på nytt." >&2
    exit 2
fi
if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew mangler. Kontroller kommandoen på https://brew.sh og kjør:" >&2
    echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"' >&2
    echo "Start deretter dette skriptet på nytt." >&2
    exit 2
fi

FORMULAS=(cmake gperf openssl@3 ffmpeg)
MISSING=()
for formula in "${FORMULAS[@]}"; do
    if ! brew list --formula "$formula" >/dev/null 2>&1; then
        MISSING+=("$formula")
    fi
done
if (( ${#MISSING[@]} )); then
    echo "Installerer Homebrew-avhengigheter: ${MISSING[*]}"
    brew install "${MISSING[@]}"
fi

if [[ ! -d "$SOURCE_DIR/.git" ]]; then
    if [[ -e "$SOURCE_DIR" ]]; then
        echo "$SOURCE_DIR finnes, men er ikke et Git-repository. Velg en annen TELEGRAM_BOT_API_SOURCE_DIR." >&2
        exit 1
    fi
    git clone --recursive https://github.com/tdlib/telegram-bot-api.git "$SOURCE_DIR"
else
    echo "Bruker eksisterende offisiell kildekode i $SOURCE_DIR"
    git -C "$SOURCE_DIR" submodule update --init --recursive
fi

OPENSSL_ROOT="$(brew --prefix openssl@3)"
cmake \
    -S "$SOURCE_DIR" \
    -B "$BUILD_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DOPENSSL_ROOT_DIR="$OPENSSL_ROOT" \
    -DCMAKE_INSTALL_PREFIX:PATH="$SOURCE_DIR"

CPU_COUNT="$(sysctl -n hw.logicalcpu)"
if (( CPU_COUNT > 4 )); then
    CPU_COUNT=4
fi
cmake --build "$BUILD_DIR" --target install --parallel "$CPU_COUNT"

BOT_API_BINARY="$SOURCE_DIR/bin/telegram-bot-api"
if [[ ! -x "$BOT_API_BINARY" ]]; then
    echo "Bygget fullførte uten forventet binær: $BOT_API_BINARY" >&2
    exit 1
fi
"$BOT_API_BINARY" --help >/dev/null

mkdir -p "$DATA_DIR" "$TEMP_DIR" "$LOG_DIR"
cd "$PROJECT_DIR"
./setup.sh
python3 scripts/configure_telegram_env.py \
    --bot-api-binary "$BOT_API_BINARY" \
    --data-dir "$DATA_DIR" \
    --temp-dir "$TEMP_DIR" \
    --log-dir "$LOG_DIR"
python3 scripts/diagnose_local_setup.py --preflight

echo
echo "Bygg, Python-miljø og .env er klare."
read -r -p "Vil du flytte boten til lokal API og installere automatisk oppstart nå? [j/N] " ACTIVATE
if [[ "$ACTIVATE" =~ ^[JjYy]$ ]]; then
    python3 scripts/migrate_bot_to_local_api.py
    ./scripts/install_launchd.sh
    READY=false
    for _attempt in {1..15}; do
        if python3 scripts/diagnose_local_setup.py >/dev/null 2>&1; then
            READY=true
            break
        fi
        sleep 2
    done
    if [[ "$READY" == "true" ]]; then
        python3 scripts/diagnose_local_setup.py
    else
        python3 scripts/diagnose_local_setup.py || true
        echo "Tjenestene ble installert, men ble ikke klare innen 30 sekunder." >&2
        exit 1
    fi
else
    echo "Ingen Telegram- eller launchd-endringer ble gjort."
    echo "Når du er klar:"
    echo "  python3 scripts/migrate_bot_to_local_api.py"
    echo "  ./scripts/install_launchd.sh"
    echo "  python3 scripts/diagnose_local_setup.py"
fi
