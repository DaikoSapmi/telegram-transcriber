# 🔧 Oppsett-guide for Telegram Transcriber

Denne guiden hjelper deg med å sette opp Telegram Transcriber lokalt.

---

## 📋 Steg 1: Forberedelser

### Sjekk at du har:
- [ ] Mac/PC med macOS, Linux eller Windows
- [ ] Python 3.9 eller nyere
- [ ] Minst 8GB RAM (16GB+ anbefalt)
- [ ] 10GB ledig diskplass (Whisper-modellen er stor)
- [ ] Telegram-konto
- [ ] ffmpeg installert (se under)

### Installere ffmpeg (påkrevd):

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

**Windows:**
1. Last ned fra https://ffmpeg.org/download.html
2. Legg til i PATH

**Hvorfor?** ffmpeg trengs for å konvertere lydfiler (m4a, mp3, etc.) til format som Whisper forstår.

---

## 🚀 Steg 2: Kjør oppsett-script

Åpne Terminal og kjør:

```bash
cd telegram-transcriber
./setup.sh
```

Dette vil:
1. ✅ Sjekke Python-installasjon
2. ✅ Opprette virtual environment
3. ✅ Installere alle avhengigheter
4. ✅ Opprette nødvendige mapper

---

## 🤖 Steg 3: Lag Telegram Bot

1. **Åpne Telegram** og søk etter **@BotFather**
2. **Start en chat** og send: `/newbot`
3. **Velg navn** på bot-en din (f.eks. "Rune sin transkriber")
4. **Velg brukernavn** (må ende på "bot", f.eks. "runetranscriberbot")
5. **Kopier tokenet** du får tilbake (ser ut som: `123456789:ABCdef...`)

---

## ⚙️ Steg 4: Konfigurer .env

1. **Kopier eksempel-filen:**
   ```bash
   cp .env.example .env
   ```

2. **Rediger .env** med din favoritt-editor:
   ```bash
   nano .env        # eller
   code .env        # VS Code
   open -e .env     # macOS TextEdit
   ```

3. **Fyll inn dine verdier:**
   ```env
   TELEGRAM_BOT_TOKEN=123456789:DITT_TOKEN_HER
   ALLOWED_USERS=@runefjellheim
   ```

### Finn din Telegram ID:

1. Gå til **@userinfobot** på Telegram
2. Send en melding
3. Du får svar: "Your user ID: **123456789**"
4. Legg til ID-en i ALLOWED_USERS

---

## 🧪 Steg 5: Test lokalt (valgfritt, men anbefalt)

Kjør lokal test for å verifisere at alt fungerer:

```bash
./test_local.py
```

Dette vil:
- Sjekke konfigurasjon
- Laste ned Whisper-modellen (tar 5-15 min første gang)
- Teste transkribering
- Generere et test-dokument

**Obs:** Nedlasting av modellen krever 3-5GB og tar tid!

---

## ▶️ Steg 6: Start bot-en

Når alt er klart:

```bash
./start.sh
```

Du skal se:
```
🎙️  Starter Telegram Transcriber...
✅ Konfigurasjon OK
🚀 Starter bot...
```

---

## 💬 Steg 7: Test med Telegram

1. **Finn bot-en din** på Telegram (søk etter brukernavnet du valgte)
2. **Send `/start`**
3. **Du skal få:** "🎙️ Velkommen til Transkriberingsbot!"
4. **Send en lydfil** (m4a, mp3, wav, ogg)
5. **Vent** på transkripsjon
6. **Motta Word-dokument** 🎉

---

## 🛑 Stoppe bot-en

Trykk **Ctrl+C** i terminal-vinduet.

---

## 🔄 Starte bot-en igjen

```bash
cd telegram-transcriber
./start.sh
```

---

## 🆘 Feilsøking

### "ModuleNotFoundError"
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### "Permission denied"
```bash
chmod +x setup.sh start.sh test_local.py
```

### "TELEGRAM_BOT_TOKEN ikke satt"
- Sjekk at `.env` filen eksisterer
- Sjekk at token er kopiert riktig fra @BotFather
- Ingen ekstra mellomrom eller hermetegn

### "Uautorisert tilgang"
- Sjekk `ALLOWED_USERS` i `.env`
- Bruk enten din Telegram ID (tall) eller brukernavn (med @)

### Whisper laster ikke
- Sjekk at du har nok diskplass (10GB+)
- Sjekk internett-forbindelse
- Første nedlasting tar 5-15 minutter

---

## 📝 Kommandoer

| Kommando | Beskrivelse |
|----------|-------------|
| `./setup.sh` | Førstegangsoppsett |
| `./start.sh` | Starte bot-en |
| `./test_local.py` | Teste uten Telegram |
| `Ctrl+C` | Stoppe bot-en |

---

## 🎛️ Avansert: Endre innstillinger

Rediger `.env` filen:

```env
# Bytte til mindre modell (raskere, mindre nøyaktig)
ASR_MODEL=NbAiLab/nb-whisper-small

# Tving CPU (hvis GPU/MPS gir problemer)
ASR_DEVICE=cpu

# Alltid ha tidsstempler
INCLUDE_TIMESTAMP=true

# Deaktiver talegjenkjenning
INCLUDE_SPEAKER_DETECTION=false
```

---

## ✅ Sjekkliste før bruk

- [ ] `./setup.sh` kjørt uten feil
- [ ] `.env` fil opprettet
- [ ] TELEGRAM_BOT_TOKEN satt
- [ ] ALLOWED_USERS satt (din ID/brukernavn)
- [ ] `./test_local.py` kjørt (valgfritt)
- [ ] `./start.sh` starter uten feil
- [ ] Testet med Telegram

---

**Godt arbeid! Nå kan du transkribere lydfiler via Telegram!** 🎉
