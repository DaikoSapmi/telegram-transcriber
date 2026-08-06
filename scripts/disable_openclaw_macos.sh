#!/bin/bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "Dette oppryddingsskriptet er bare for macOS." >&2
    exit 1
fi

OPENCLAW_DIR="$HOME/.openclaw"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
USER_DOMAIN="gui/$(id -u)"
stopped_pids=""

echo "Stopper og deaktiverer LaunchAgents som peker på $OPENCLAW_DIR"
for plist in "$LAUNCH_AGENTS_DIR"/*.plist; do
    [[ -f "$plist" ]] || continue
    if ! /usr/bin/grep -Fq "$OPENCLAW_DIR" "$plist"; then
        continue
    fi
    label="$(/usr/libexec/PlistBuddy -c 'Print :Label' "$plist" 2>/dev/null || true)"
    if [[ -z "$label" ]]; then
        echo "Fant OpenClaw-plist uten lesbar Label: $plist" >&2
        continue
    fi
    echo "  Stopper og deaktiverer $label"
    launchctl bootout "$USER_DOMAIN/$label" >/dev/null 2>&1 || true
    launchctl disable "$USER_DOMAIN/$label"
done

echo "Stopper gjenværende prosesser som kjører fra $OPENCLAW_DIR"
while read -r pid command; do
    cwd="$(/usr/sbin/lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -n 1 || true)"
    if [[ "$cwd" != "$OPENCLAW_DIR" && "$cwd" != "$OPENCLAW_DIR/"* && "$command" != *"$OPENCLAW_DIR/"* ]]; then
        continue
    fi
    echo "  Stopper PID $pid: $command"
    if kill "$pid" 2>/dev/null; then
        stopped_pids="$stopped_pids $pid"
    fi
done < <(ps -axo pid=,command=)

for pid in $stopped_pids; do
    for _attempt in {1..20}; do
        if ! kill -0 "$pid" 2>/dev/null; then
            break
        fi
        sleep 0.25
    done
    if kill -0 "$pid" 2>/dev/null; then
        echo "OpenClaw-prosess PID $pid stoppet ikke. Stopp den manuelt med: kill $pid" >&2
        exit 1
    fi
done

remaining=false
while read -r pid command; do
    cwd="$(/usr/sbin/lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -n 1 || true)"
    if [[ "$cwd" == "$OPENCLAW_DIR" || "$cwd" == "$OPENCLAW_DIR/"* || "$command" == *"$OPENCLAW_DIR/"* ]]; then
        echo "OpenClaw-prosess kjører fortsatt, PID $pid: $command" >&2
        remaining=true
    fi
done < <(ps -axo pid=,command=)

if [[ "$remaining" == "true" ]]; then
    exit 1
fi

echo "Alle OpenClaw LaunchAgents er deaktivert og alle OpenClaw-prosesser er stoppet."
echo "Ingen filer under $OPENCLAW_DIR ble slettet."
