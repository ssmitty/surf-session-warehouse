#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.ssmitty.surf-session-warehouse.streamlit"
PLIST_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"
PYTHON_BIN="${DASHBOARD_PYTHON:-$HOME/.cache/surf-session-warehouse-venv/bin/python}"
PORT="${PORT:-8501}"

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Python runtime not found: $PYTHON_BIN" >&2
    echo "Set DASHBOARD_PYTHON=/path/to/python before installing the service." >&2
    exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$ROOT_DIR/logs"

cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_BIN</string>
        <string>-m</string>
        <string>streamlit</string>
        <string>run</string>
        <string>app/streamlit_app.py</string>
        <string>--server.port</string>
        <string>$PORT</string>
        <string>--server.headless</string>
        <string>true</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$ROOT_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$ROOT_DIR/logs/streamlit-launchd.log</string>
    <key>StandardErrorPath</key>
    <string>$ROOT_DIR/logs/streamlit-launchd.err.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONUNBUFFERED</key>
        <string>1</string>
    </dict>
</dict>
</plist>
PLIST

launchctl bootout "gui/$(id -u)" "$PLIST_PATH" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
launchctl kickstart -k "gui/$(id -u)/$LABEL"

echo "Installed dashboard service at http://localhost:$PORT."
echo "Logs: $ROOT_DIR/logs/streamlit-launchd.log"
