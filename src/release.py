"""Release identity shared by runtime messages and generated documents."""

from pathlib import Path

RELEASE_FILE = Path(__file__).resolve().parent.parent / "AILO_RELEASE"
AILO_RELEASE = RELEASE_FILE.read_text(encoding="utf-8").strip()

if not AILO_RELEASE:
    raise RuntimeError("AILO_RELEASE er tom")
