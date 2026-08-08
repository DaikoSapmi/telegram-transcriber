# Hurtigstart på Mac

Skaff først:

- App `api_id` og `api_hash` fra [my.telegram.org](https://my.telegram.org/apps)
- bot-token fra `@BotFather`

Kjør deretter hele veiviseren:

```bash
./scripts/install_macos.sh
```

Veiviseren bygger den offisielle lokale Bot API-serveren, setter opp Python, lagrer hemmelighetene i `.env`, utfører kontroller og tilbyr engangsovergang samt automatisk oppstart.

I Telegram velger du språket som faktisk snakkes i lydfilen:
`Norsk tale → norsk tekst` eller
`Nordsamisk tale → nordsamisk tekst`. Ailo leverer hele den rene
Whisper-transkripsjonen uten oversettelse, språkvask, sammendrag eller Gemini.

Etter aktivering:

```bash
python3 scripts/diagnose_local_setup.py
./scripts/create_large_test_audio.sh
```

I Telegram viser `/driftstatus` om bot, køarbeider, lokal API, jobbkø og
arbeidsmapper svarer. `/status` viser prosent og køplass for dine aktive jobber,
mens `/hjelp` viser alle kommandoene.

Etter en kodeoppdatering kjører du `./scripts/install_launchd.sh` på nytt. Det
stopper en gammel Ailo-prosess fra denne prosjektmappen før den nye startes.
Send `/version` til Ailo og kontroller at svaret viser
`pure-transcription-2026.08.06` og `ingen Gemini`.

Se [README.md](README.md) for manuelle enkeltsteg og feilsøking.
