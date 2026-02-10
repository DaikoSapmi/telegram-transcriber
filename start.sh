#!/bin/bash
# start.sh - Start Telegram Transcriber bot
# Bruk: ./start.sh

echo "🎙️  Starter Telegram Transcriber..."
echo ""

# Sjekk om virtual environment finnes
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment ikke funnet"
    echo "Kjør først: ./setup.sh"
    exit 1
fi

# Aktiver virtual environment
source venv/bin/activate

# Sjekk om .env finnes
if [ ! -f ".env" ]; then
    echo "❌ .env fil ikke funnet"
    echo "Kjør: cp .env.example .env"
    echo "Og rediger med din Telegram Bot Token"
    exit 1
fi

# Sjekk om token er satt
if grep -q "your_bot_token_here" .env 2>/dev/null || ! grep -q "TELEGRAM_BOT_TOKEN" .env 2>/dev/null; then
    echo "❌ TELEGRAM_BOT_TOKEN ikke satt i .env"
    echo "Hent token fra @BotFather på Telegram"
    exit 1
fi

echo "✅ Konfigurasjon OK"
echo "🚀 Starter bot..."
echo ""
echo "Trykk Ctrl+C for å stoppe"
echo ""

# Kjør bot-en
python -m src.telegram_bot
