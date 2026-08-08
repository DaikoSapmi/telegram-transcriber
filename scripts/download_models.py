#!/usr/bin/env python3
"""Download or verify both Whisper models before Ailo starts receiving jobs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from scripts.env_file import read_env
from src.model_cache import cached_model, download_model, format_gigabytes

DEFAULT_NORWEGIAN_MODEL = "NbAiLab/nb-whisper-large"
DEFAULT_SAMI_MODEL = "NbAiLab/whisper-large-sme"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=PROJECT_DIR / ".env")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Kontroller lokal modellbuffer uten nettverk eller nedlasting",
    )
    args = parser.parse_args()
    values = read_env(args.env_file)
    models = (
        ("Norsk", values.get("NORWEGIAN_MODEL", DEFAULT_NORWEGIAN_MODEL)),
        ("Nordsamisk", values.get("SAMI_MODEL", DEFAULT_SAMI_MODEL)),
    )
    loader = cached_model if args.check_only else download_model
    failures = 0

    for position, (language, model_name) in enumerate(models, start=1):
        action = "Kontrollerer" if args.check_only else "Laster ned og kontrollerer"
        print(
            f"\n[{position}/{len(models)}] {action} {language.lower()}: {model_name}",
            flush=True,
        )
        try:
            snapshot = loader(model_name)
        except (OSError, RuntimeError, ValueError) as error:
            failures += 1
            print(f"❌ {language} Whisper-modell: {error}", flush=True)
            continue
        print(
            f"✅ {language} Whisper-modell er nedlastet "
            f"({format_gigabytes(snapshot.weight_bytes)})",
            flush=True,
        )

    if failures:
        mode = "lokalt" if args.check_only else "under nedlasting"
        raise SystemExit(f"{failures} modellkontroll(er) feilet {mode}.")
    print("\n✅ Begge Whisper-modellene er klare for lydfiler.", flush=True)


if __name__ == "__main__":
    main()
