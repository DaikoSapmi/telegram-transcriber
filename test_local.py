#!/usr/bin/env python3
"""Run one real local transcription without Telegram."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from config.settings import settings
from src.document_generator import DocumentGenerator
from src.transcriber import Transcriber


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path, help="Audio file to transcribe")
    parser.add_argument("--language", choices=("no", "sme"), default="no")
    parser.add_argument("--output", choices=("txt", "docx", "both"), default="both")
    args = parser.parse_args()

    source = args.audio.expanduser().resolve()
    if not source.is_file():
        parser.error(f"Filen finnes ikke: {source}")
    settings.ensure_directories()

    transcriber = Transcriber(settings)
    with tempfile.TemporaryDirectory(
        prefix="local-test-", dir=settings.work_dir
    ) as work_dir:
        result = transcriber.transcribe(
            source,
            language=args.language,
            work_dir=work_dir,
            progress=lambda percent, text: print(f"{percent:3d}%  {text}", flush=True),
        )
    output_dir = Path(settings.output_dir) / "local-test"
    paths = DocumentGenerator(output_dir).generate(result, source.name, args.output)
    for path in paths:
        print(path.resolve())


if __name__ == "__main__":
    main()
