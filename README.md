# Ailo – Telegram Transcriber

Lokal, presisjonsorientert transkribering av lange norske og nordsamiske lydopptak via Telegram.

```text
Telegram → lokal Bot API-server → SQLite-kø → FFmpeg → Whisper → TXT/DOCX → Telegram
```

Selve talegjenkjenningen skjer lokalt på Mac-en. Lydfilen går fortsatt via Telegrams servere når brukeren sender den til boten.

Ailo leverer ren Whisper-transkripsjon på samme språk som opptaket. Det finnes
ingen kobling til Gemini eller en annen LLM, og resultatet blir ikke oversatt,
forkortet, oppsummert eller språkvasket.

## Dette er implementert

- lokal Telegram Bot API-server for nedlasting uten den ordinære 20 MB-grensen
- private samtaler og brukerautorisasjon
- entydige knapper for norsk tale → norsk tekst og nordsamisk tale → nordsamisk tekst
- knapper for TXT, Word eller begge
- SQLite-kø med én transkripsjon om gangen
- `/status`, `/driftstatus`, `/cancel`, `/help` og `/hjelp`
- omstartssikre jobber og kontrollpunkter mellom hoveddeler
- FFmpeg-normalisering til 16 kHz mono PCM
- behovsstyrt modellbytte, slik at bare én stor modell er lastet
- sekvensiell Whisper-langform med tidsstempler, kontekst og temperatur-fallback
- eksplisitt vern mot 30-sekunders inputtrunkering og tidlig avbrutt resultat
- 3 sekunders overlapp og deduplisering med tidsstempler og tekst
- MPS på Apple Silicon med automatisk CPU-fallback
- ren UTF-8 TXT og Word med tidsstemplede segmenter
- råsegmenter i JSON i 48 timer for feilsøking
- automatisk sletting av lyd etter vellykket levering og 48 timers feiloppbevaring
- roterende logger og `launchd`-oppsett

Første versjon inneholder bevisst ikke møtereferat, LLM-korrektur, oversettelse eller taleridentifikasjon.

## Modeller

| Valg | Modell |
|---|---|
| Norsk | `NbAiLab/nb-whisper-large` |
| Nordsamisk | `NbAiLab/whisper-large-sme` |

Språkvalget beskriver språket som faktisk tales i opptaket, ikke ønsket
oversettelsesspråk. Nordsamiskmodellen er finjustert fra Whisper Large v2 og
bruker sin egen generasjonskonfigurasjon. Verken `sme`, norsk språkforcing
eller en generell task-override sendes til SME-modellen.

Ved lang lyd slås feature-extractor-trunkering eksplisitt av. Hvis Whisper
likevel stopper mens det fortsatt finnes tydelig hørbar lyd, feiler jobben i
stedet for å levere en avkortet transkripsjon.

## Krav

- macOS med Python 3.10 eller nyere
- FFmpeg i `PATH`
- helst Apple Silicon og minst 16 GB minne; mer minne anbefales for Large-modellene
- en Telegram-bot fra `@BotFather`
- lokal `telegram-bot-api`-binær dersom filer over 20 MB skal støttes
- `api_id` og `api_hash` fra [my.telegram.org](https://my.telegram.org/apps) for lokal Bot API

## Oppsett

### Anbefalt: veiviser for hele Mac-installasjonen

Du trenger tre verdier før aktivering:

- `TELEGRAM_API_ID` og `TELEGRAM_API_HASH` fra [my.telegram.org](https://my.telegram.org/apps)
- `TELEGRAM_BOT_TOKEN` fra `@BotFather`

Bot-ID er tallet før kolon i `TELEGRAM_BOT_TOKEN`. Den trenger ikke en egen miljøvariabel.

Ved opprettelse på `my.telegram.org` kan du for eksempel bruke `Local Transcriber` som App title, `localtranscriber` som Short name og `Desktop` som plattform.

Kjør:

```bash
./scripts/install_macos.sh
```

Veiviseren:

1. kontrollerer Xcode Command Line Tools og Homebrew
2. installerer manglende `cmake`, `gperf`, OpenSSL og FFmpeg
3. kloner og bygger Telegrams offisielle `telegram-bot-api` direkte på Mac-en
4. installerer Python-miljøet
5. ber om de tre Telegram-verdiene uten å vise hemmelighetene på skjermen
6. lagrer dem og lokale serverstier i `.env` med filmodus `600`
7. kontrollerer binær, mapper og localhost-konfigurasjon
8. tilbyr en eksplisitt engangsovergang med `logOut` og installasjon av `launchd`

Skriptet installerer ikke Homebrew eller Xcode automatisk. Hvis en av dem mangler, får du den nøyaktige manuelle handlingen og kan starte veiviseren på nytt etterpå.

### Manuelle enkeltsteg

Installer Python-avhengigheter og opprett `.env`:

```bash
./setup.sh
```

Konfigurer Telegram-verdiene etter at serverbinæren er bygget:

```bash
python3 scripts/configure_telegram_env.py \
  --bot-api-binary "$HOME/telegram-bot-api/bin/telegram-bot-api" \
  --data-dir "$HOME/Library/Application Support/telegram-bot-api/data" \
  --temp-dir "$HOME/Library/Application Support/telegram-bot-api/temp" \
  --log-dir "$HOME/Library/Logs/telegram-bot-api"
```

Kjør engangsovergangen til lokal API. Skriptet krever at du skriver inn bot-ID-en som bekreftelse og lagrer en lokal markør, slik at `logOut` ikke gjentas ved vanlig omstart:

```bash
python3 scripts/migrate_bot_to_local_api.py
```

Start og kontroller manuelt:

```bash
./scripts/run_local_bot_api.sh
# I en annen terminal:
./start.sh
# Kontroll:
python3 scripts/diagnose_local_setup.py
```

Den lokale serveren bindes uttrykkelig til `127.0.0.1`, bruker roterende logg og leser `api_id`/`api_hash` fra `.env`. Ingen domene, portåpning eller TLS-konfigurasjon er nødvendig for polling.

`./setup.sh` laster ned og validerer begge modellene før Ailo startes. Fremdriften
vises i terminalen, etterfulgt av en grønn kontroll for norsk og nordsamisk.
Transformers-vektene er omtrent 6,17 GB per modell, altså rundt 12,4 GB samlet,
i tillegg til små konfigurasjons- og tokeniseringsfiler. Modellarkivene på Hugging
Face er større fordi de også inneholder alternative formater og treningsfiler som
Ailo ikke laster ned.

Kontroller modellene senere uten nettverk eller ny nedlasting:

```bash
./venv/bin/python scripts/download_models.py --check-only
```

Ailo bruker bare lokalt validerte modellfiler under transkribering. Den første
innlastingen av en modell fra disk kan fortsatt ta litt tid, men lydjobben starter
ikke lenger en skjult modellnedlasting.

### Test av fil over 20 MB

Lag en ufarlig WAV-testfil på omtrent 21 MB:

```bash
./scripts/create_large_test_audio.sh
```

Send `data/test-over-20mb.wav` som dokument til boten. Dette verifiserer at filen faktisk går gjennom den lokale Bot API-serveren; stillheten skal gi en tom eller nesten tom transkripsjon.

## Automatisk oppstart på Mac

Når begge prosessene fungerer manuelt:

```bash
./scripts/install_launchd.sh
```

Dette installerer to LaunchAgents i `~/Library/LaunchAgents`, begge med `RunAtLoad` og `KeepAlive`: én for den lokale Bot API-serveren og én for transkriberingsboten.

Status og logger:

```bash
launchctl print gui/$(id -u)/com.daikosapmi.telegram-transcriber
tail -f logs/telegram-transcriber.log
tail -f logs/telegram-bot-api.stderr.log
```

Den roterende serverloggen ligger som standard i `~/Library/Logs/telegram-bot-api/telegram-bot-api.log`.

### Etter oppdatering eller hvis gammel Ailo svarer

Oppdater `main` og installer LaunchAgent på nytt:

```bash
git fetch origin
git switch main
git pull --ff-only origin main
./scripts/install_launchd.sh
python3 scripts/diagnose_local_setup.py
```

Installasjonsskriptet stopper eldre Ailo-prosesser fra samme prosjektmappe før
den nye prosessen startes. Det avbryter med PID og mappe hvis en konkurrerende
Telegram-transcriber fra en annen mappe fremdeles kjører. Send deretter
`/version` til Ailo. For denne utgaven skal svaret inneholde
`pure-transcription-2026.08.08` og `ingen Gemini`.

## Telegram-forløp

1. Send en lydfil.
2. Velg språket som faktisk snakkes: `Norsk tale → norsk tekst` eller
   `Nordsamisk tale → nordsamisk tekst`.
3. Velg `TXT`, `Word` eller `Begge`.
4. Bot-en viser køplass og sender fremdriftsoppdateringer.
5. Hele den rene Whisper-transkripsjonen sendes tilbake uten oversettelse,
   språkvask eller sammendrag, og kildelyden slettes lokalt.

`/cancel <jobb-id>` kan brukes for en bestemt jobb. Uten ID avbrytes brukerens nyeste aktive jobb. Med nyere Transformers-versjoner kontrolleres avbrudd også mellom Whispers interne segmenter; ellers stoppes jobben mellom hoveddeler.

`/driftstatus` (alias `/health`) kontrollerer at Ailo-boten, køarbeideren,
den lokale Telegram Bot API-serveren, SQLite-køen og arbeidsmappene svarer. Den
viser en grønn eller rød kontroll for hver av de to Whisper-modellene, antall
jobber som behandles, venter i kø eller venter på et brukervalg, samt siste
registrerte arbeidersignal. Bruk `/status` for filnavn, prosent og køplass for
egne jobber.

`/hjelp` viser en kort oversikt over alle tilgjengelige Ailo-kommandoer.

`/version` viser den aktive Ailo-utgaven og bekrefter at prosessen kjører uten
Gemini eller annen etterbehandling.

## Langformprofil

Standardprofilen er:

```text
num_beams=5
temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
compression_ratio_threshold=2.4
logprob_threshold=-1.0
no_speech_threshold=0.6
condition_on_prev_tokens=true
main_chunk=15 minutter
overlap=3 sekunder
```

`COMPRESSION_RATIO_THRESHOLD=1.35` er en alternativ testprofil. Bruk manuelt korrigerte utdrag før verdien endres permanent.

`TRANSCRIPTION_GLOSSARY` kan inneholde samiske navn, stedsnavn, organisasjoner og andre spesialord. Ordlisten kombineres med slutten av forrige hoveddel som prompt til neste del.

## Lagring og personvern

- `data/jobs.sqlite3`: kø, status og historikk
- `data/incoming`: mottatt lyd; slettes etter levering
- `data/work`: normalisert WAV; slettes etter levering
- `data/output`: midlertidige TXT/DOCX; slettes etter levering
- `data/debug`: råsegmenter i JSON; standard oppbevaring 48 timer
- `logs`: roterende applikasjonslogger

Ved feil beholdes kilde og arbeidsfiler i `FAILED_RETENTION_HOURS` timer. Oppryddingen kjøres ved oppstart og periodisk mellom jobber.

## Tester

Raske enhetstester:

```bash
venv/bin/python -m pytest
```

Lokal ende-til-ende-test uten Telegram:

```bash
venv/bin/python test_local.py /full/sti/til/opptak.m4a --language no --output both
```

Før produksjon bør minst norsk 5/60/120+ minutter, nordsamisk 5 minutter og ett langt møte, fil over 20 MB, omstart under jobb og MPS/CPU-fallback testes. Presisjon bør måles mot manuelt korrigerte utdrag.
