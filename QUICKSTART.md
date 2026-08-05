# Hurtigstart på Mac

Skaff først:

- App `api_id` og `api_hash` fra [my.telegram.org](https://my.telegram.org/apps)
- bot-token fra `@BotFather`

Kjør deretter hele veiviseren:

```bash
./scripts/install_macos.sh
```

Veiviseren bygger den offisielle lokale Bot API-serveren, setter opp Python, lagrer hemmelighetene i `.env`, utfører kontroller og tilbyr engangsovergang samt automatisk oppstart.

Etter aktivering:

```bash
python3 scripts/diagnose_local_setup.py
./scripts/create_large_test_audio.sh
```

Se [README.md](README.md) for manuelle enkeltsteg og feilsøking.
