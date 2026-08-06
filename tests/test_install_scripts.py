from pathlib import Path


def test_launchd_installer_retires_known_legacy_ailo() -> None:
    script = Path("scripts/install_launchd.sh").read_text(encoding="utf-8")

    assert 'LEGACY_TRANSCRIBER_NAME="no.daiko.ailo-transcriber"' in script
    assert 'launchctl bootout "gui/$(id -u)/$LEGACY_TRANSCRIBER_NAME"' in script
    assert 'launchctl disable "gui/$(id -u)/$LEGACY_TRANSCRIBER_NAME"' in script
    assert "*telegram_bot*.py*" in script


def test_openclaw_cleanup_is_scoped_and_non_deleting() -> None:
    script = Path("scripts/disable_openclaw_macos.sh").read_text(encoding="utf-8")

    assert 'OPENCLAW_DIR="$HOME/.openclaw"' in script
    assert 'launchctl bootout "$USER_DOMAIN/$label"' in script
    assert 'launchctl disable "$USER_DOMAIN/$label"' in script
    assert 'kill "$pid"' in script
    assert "rm " not in script
