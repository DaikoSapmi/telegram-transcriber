#!/bin/bash
# setup.sh - Oppsett-script for Telegram Transcriber
# Bruk: ./setup.sh

set -e

echo "🎙️  Telegram Transcriber - Oppsett"
echo "===================================="
echo ""

# Sjekk Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 er ikke installert"
    echo "Installer fra https://python.org eller med: brew install python"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
echo "✅ Python funnet: $PYTHON_VERSION"

# Sjekk om virtual environment finnes
if [ ! -d "venv" ]; then
    echo "📦 Oppretter virtual environment..."
    python3 -m venv venv
fi

# Aktiver virtual environment
echo "🔄 Aktiverer virtual environment..."
source venv/bin/activate

# Oppgrader pip
echo "⬆️  Oppgraderer pip..."
pip install --upgrade pip

# Installer avhengigheter
echo "📥 Installerer avhengigheter..."
pip install -r requirements.txt

echo ""
echo "✅ Avhengigheter installert!"
echo ""

# Sjekk om .env finnes
if [ ! -f ".env" ]; then
    echo "⚠️  .env fil finnes ikke ennå"
    echo ""
    echo "Neste steg:"
    echo "1. Kopier .env.example til .env:"
    echo "   cp .env.example .env"
    echo ""
    echo "2. Rediger .env og legg inn:"
    echo "   - TELEGRAM_BOT_TOKEN (hent fra @BotFather)"
    echo "   - ALLOWED_USERS (din Telegram ID eller brukernavn)"
    echo ""
    echo "3. Finn din Telegram ID:"
    echo "   - Gå til @userinfobot på Telegram"
    echo "   - Send en melding, få ID tilbake"
    echo ""
else
    echo "✅ .env fil funnet"
    
    # Sjekk om token er satt
    if grep -q "your_bot_token_here" .env; then
        echo "⚠️  Husk å bytte ut 'your_bot_token_here' med ekte token fra @BotFather!"
    fi
fi

echo ""
echo "📁 Oppretter nødvendige mapper..."
mkdir -p temp output

echo ""
echo "🎯 For å starte bot-en:"
echo "   ./start.sh"
echo ""
echo "Eller manuelt:"
echo "   source venv/bin/activate"
echo "   python -m src.telegram_bot"
echo ""
