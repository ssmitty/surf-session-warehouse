#!/usr/bin/env bash
set -euo pipefail

LABEL="com.ssmitty.surf-session-warehouse.streamlit"
PLIST_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$(id -u)" "$PLIST_PATH" 2>/dev/null || true
rm -f "$PLIST_PATH"

echo "Uninstalled dashboard service."
