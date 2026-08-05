#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_PATH="${1:-$PROJECT_DIR/data/test-over-20mb.wav}"
mkdir -p "$(dirname "$OUTPUT_PATH")"

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "FFmpeg mangler." >&2
    exit 1
fi

# 11 minutes of 16 kHz mono PCM is approximately 21 MB.
ffmpeg \
    -nostdin \
    -hide_banner \
    -loglevel error \
    -y \
    -f lavfi \
    -i anullsrc=r=16000:cl=mono \
    -t 660 \
    -c:a pcm_s16le \
    "$OUTPUT_PATH"

SIZE_BYTES="$(stat -f %z "$OUTPUT_PATH")"
SIZE_MB=$(( SIZE_BYTES / 1024 / 1024 ))
echo "Opprettet: $OUTPUT_PATH (${SIZE_MB} MB)"
echo "Send filen som dokument i Telegram for å teste lokal Bot API over 20 MB."
