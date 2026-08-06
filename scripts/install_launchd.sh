#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE_DIR="$PROJECT_DIR/launchd"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
TRANSCRIBER_NAME="com.daikosapmi.telegram-transcriber"
mkdir -p "$LAUNCH_AGENTS_DIR" "$PROJECT_DIR/logs"

cd "$PROJECT_DIR"
python3 scripts/diagnose_local_setup.py --preflight --require-migration

project_transcriber_pids() {
    local pid command
    while read -r pid command; do
        if [[ "$command" == "$PROJECT_DIR/venv/bin/python -m src.telegram_bot"* ]]; then
            echo "$pid"
        fi
    done < <(ps -axo pid=,command=)
}

stop_existing_transcribers() {
    local pid command cwd
    local -a stopped_pids=()
    local -a competing_processes=()

    launchctl bootout "gui/$(id -u)/$TRANSCRIBER_NAME" >/dev/null 2>&1 || true

    while read -r pid command; do
        if [[ "$command" != *"src.telegram_bot"* && "$command" != *telegram_bot*.py* ]]; then
            continue
        fi
        cwd="$(/usr/sbin/lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -n 1 || true)"
        if [[ "$cwd" == "$PROJECT_DIR" || "$command" == *"$PROJECT_DIR"* ]]; then
            echo "Stopper gammel Ailo-prosess fra denne prosjektmappen: PID $pid"
            if kill "$pid" 2>/dev/null; then
                stopped_pids+=("$pid")
            fi
        else
            competing_processes+=("PID $pid, mappe ${cwd:-ukjent}: $command")
        fi
    done < <(ps -axo pid=,command=)

    if (( ${#stopped_pids[@]} )); then
        for pid in "${stopped_pids[@]}"; do
            for _attempt in {1..20}; do
                if ! kill -0 "$pid" 2>/dev/null; then
                    break
                fi
                sleep 0.25
            done
            if kill -0 "$pid" 2>/dev/null; then
                echo "Ailo-prosess PID $pid stoppet ikke. Stopp den manuelt og kjør skriptet på nytt." >&2
                exit 1
            fi
        done
    fi

    if (( ${#competing_processes[@]} )); then
        echo "Fant en annen Telegram-transcriber som kan stjele meldingene fra Ailo:" >&2
        printf '  %s\n' "${competing_processes[@]}" >&2
        echo "Stopp den gamle prosessen og kjør skriptet på nytt." >&2
        exit 1
    fi
}

verify_transcriber_runtime() {
    local target="$LAUNCH_AGENTS_DIR/$TRANSCRIBER_NAME.plist"
    local expected_start="$PROJECT_DIR/start.sh"
    local actual_start
    local running_pids=""

    actual_start="$(/usr/libexec/PlistBuddy -c 'Print :ProgramArguments:1' "$target")"
    if [[ "$actual_start" != "$expected_start" ]]; then
        echo "LaunchAgent peker på feil prosjektmappe: $actual_start" >&2
        exit 1
    fi

    for _attempt in {1..20}; do
        running_pids="$(project_transcriber_pids)"
        if [[ -n "$running_pids" ]]; then
            break
        fi
        sleep 0.5
    done
    if [[ -z "$running_pids" ]]; then
        echo "Den nye Ailo-prosessen startet ikke. Se logs/telegram-transcriber.stderr.log." >&2
        launchctl print "gui/$(id -u)/$TRANSCRIBER_NAME" || true
        exit 1
    fi

    echo "Ny Ailo-prosess kjører fra riktig prosjektmappe: PID ${running_pids//$'\n'/, }"
}

stop_existing_transcribers

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
install_plist "$TRANSCRIBER_NAME"
verify_transcriber_runtime

echo "LaunchAgents installert og startet."
echo "Ailo-versjon: $(<AILO_RELEASE)"
echo "Status: launchctl print gui/$(id -u)/$TRANSCRIBER_NAME"
echo "Send /version til Ailo i Telegram for å bekrefte kjørende kode."
