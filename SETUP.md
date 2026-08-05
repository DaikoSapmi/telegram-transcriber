# Oppsett

Den autoritative oppskriften ligger i [README.md](README.md). Denne versjonen krever lokal Telegram Bot API-server for store filer, FFmpeg, Python-miljøet fra `setup.sh` og en ferdig utfylt `.env`.

Viktig: Boten må logges ut av den offisielle Bot API-serveren med `logOut` før den lokale serveren tas i bruk. Telegram tillater ikke pålitelig samtidig bruk av samme bot på flere Bot API-servere.
