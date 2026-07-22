#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PID_FILE="${PID_FILE:-logs/streamlit.pid}"

if [[ ! -f "$PID_FILE" ]]; then
    echo "No Streamlit PID file found."
    exit 0
fi

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    echo "Stopped Streamlit PID $PID."
else
    echo "Streamlit PID $PID is not running."
fi

rm -f "$PID_FILE"
