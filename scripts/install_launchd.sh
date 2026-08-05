#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE_DIR="$PROJECT_DIR/launchd"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$LAUNCH_AGENTS_DIR" "$PROJECT_DIR/logs"

cd "$PROJECT_DIR"
python3 scripts/diagnose_local_setup.py --preflight --require-migration

install_plist() {
    local name="$1"
    local source="$TEMPLATE_DIR/$name.plist.example"
    local target="$LAUNCH_AGENTS_DIR/$name.plist"
    local escaped_project="${PROJECT_DIR//&/\\&}"
    /usr/bin/sed "s|__PROJECT_DIR__|$escaped_project|g" "$source" > "$target"
    launchctl bootout "gui/$(id -u)/$name" >/dev/null 2>&1 || true
    launchctl bootstrap "gui/$(id -u)" "$target"
    launchctl enable "gui/$(id -u)/$name"
}

install_plist "com.daikosapmi.telegram-bot-api"
install_plist "com.daikosapmi.telegram-transcriber"

echo "LaunchAgents installert og startet."
echo "Status: launchctl print gui/$(id -u)/com.daikosapmi.telegram-transcriber"
