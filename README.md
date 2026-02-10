# Telegram Transcriber

Transkribering av lydfiler via Telegram med støtte for norsk og nordsamisk.

## Funksjoner

- 🎙️ **Mottar lydfiler** via Telegram
- 📝 **Genererer Word-dokumenter** (.docx)
- 🗣️ **Støtter norsk og nordsamisk** (via NbAiLab Whisper)
- 📊 **Møtereferat** med AI (flere LLM-leverandører støttet)
- 🌍 **Dokument på norsk eller engelsk**
- 👥 **Talegjenkjenning** (eksperimentelt)
- ⏱️ **Valgfrie tidsstempler**
- 🔒 **Sikker håndtering** (midlertidige filer slettes)
- 🤖 **Fleksible LLM-valg**: OpenAI, Anthropic, Gemini, Kimi, eller lokal Ollama

## Kom i gang

### 1. Installer avhengigheter

```bash
pip install -r requirements.txt
```

### 2. Konfigurer miljøvariabler

Opprett en `.env` fil:

```env
TELEGRAM_BOT_TOKEN=din_bot_token_her
ASR_MODEL=NbAiLab/nb-whisper-large
ASR_DEVICE=auto
DEFAULT_LANGUAGE=no
```

Hent bot token fra [@BotFather](https://t.me/botfather) på Telegram.

### 3. Kjør bot-en

```bash
python -m src.telegram_bot
```

## Bruk

### 1. Send lydfil
Send en lydfil (m4a, mp3, wav, ogg) til bot-en.

### 2. Velg format og språk
Bot-en spør om:
- **Format:** `1` (full transkripsjon) eller `2` (møtereferat)
- **Dokument-språk:** `n` (norsk) eller `e` (engelsk)
- **Valgfritt:** `tidsstempel` for tidskoder

**Eksempler:**
- `1 n` → Full transkripsjon på norsk
- `2 e` → Møtereferat på engelsk
- `1 n tidsstempel` → Transkripsjon på norsk med tidskoder

### 3. Motta dokument
Bot-en sender Word-dokumentet når det er klart.

### Nordsamisk lyd
For lyd på nordsamisk, skriv "samisk" før du sender filen.

## 🤖 LLM Konfigurasjon (for møtereferat)

Velg én eller flere LLM-leverandører:

| Leverandør | Miljøvariabel | Modell-eksempel | Kommentar |
|------------|---------------|-----------------|-----------|
| **OpenAI** | `OPENAI_API_KEY` | `gpt-4o-mini` | Pålitelig, rimelig |
| **Anthropic** | `ANTHROPIC_API_KEY` | `claude-3-haiku` | God på lange tekster |
| **Google** | `GEMINI_API_KEY` | `gemini-1.5-flash` | Rask, god kontekst |
| **Kimi** | `KIMI_API_KEY` | `kimi-k2.5` | Stor kontekst-vindu |
| **Ollama** | Ingen nøkkel | `llama3.2` | **Gratis, lokal, privat** |

### Anbefaling: Ollama (lokal LLM)

**Beste valg for personvern - alt skjer lokalt:**

1. **Installer Ollama:**
   ```bash
   brew install ollama
   ```

2. **Last ned en modell:**
   ```bash
   # Rask og god (anbefalt)
   ollama pull llama3.2
   
   # Eller større modell (bedre kvalitet, tregere)
   ollama pull mistral
   ```

3. **Start Ollama:**
   ```bash
   ollama serve
   ```

4. **Konfigurer .env:**
   ```env
   LLM_PROVIDER=ollama
   OLLAMA_MODEL=llama3.2
   ```

**Fordeler:**
- ✅ 100% gratis
- ✅ Ingen data sendes til skyen
- ✅ Fungerer offline
- ✅ Ingen API-nøkler nødvendig

### Eksempel

```
Deg: samisk
Bot: ✅ Språk satt til: Nordsamisk

Deg: [sender lydfil]
Bot: ⏳ Laster ned fil...
Bot: 🎙️ Transkriberer på Nordsamisk...
Bot: 📝 Genererer Word-dokument...
Bot: [sender .docx fil]
```

## Støttede formater

- M4A (iPhone voice memos)
- MP3
- WAV
- OGG
- OPUS

## Arkitektur

```
Telegram → telegram_bot.py → transcriber.py → document_generator.py → Word-doc
                ↓
         Whisper (NbAiLab)
```

## Konfigurasjon

| Variabel | Beskrivelse | Standard |
|----------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | Bot token fra BotFather | (påkrevd) |
| `ASR_MODEL` | Whisper-modell | `NbAiLab/nb-whisper-large` |
| `ASR_DEVICE` | Enhet (cpu/mps/cuda/auto) | `auto` |
| `DEFAULT_LANGUAGE` | Standard språk | `no` |
| `INCLUDE_TIMESTAMP` | Tidsstempler som standard | `False` |
| `DELETE_TEMP_FILES` | Slette midlertidige filer | `True` |

## Sikkerhet

- **Brukerautorisering**: Kun godkjente Telegram-brukere kan bruke bot-en
- Midlertidige filer slettes etter prosessering
- Ingen lagring i skyen
- Lokalt prosessering kun

### Sette opp autorisering

I `.env` filen, legg til godkjente brukere:

```env
# Kommaseparert liste med bruker-ID-er og/eller brukernavn
ALLOWED_USERS=123456789,@dittbrukernavn,987654321
```

**Finne din bruker-ID:**
1. Send melding til bot-en @userinfobot
2. Den svarer med din ID

**Eller bruk brukernavn:**
- Format: `@brukernavn` (uten @ i .env: `brukernavn`)

**Viktig:** Hvis `ALLOWED_USERS` er tom, tillates alle (ikke anbefalt i produksjon).

## Krav

- Python 3.9+
- 8GB+ RAM (16GB+ anbefalt for Whisper)
- macOS/Linux/Windows

## Lisens

MIT License

## Takk til

- [NbAiLab](https://github.com/NbAiLab) for Whisper-modellen
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
