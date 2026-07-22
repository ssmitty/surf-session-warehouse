#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PORT="${PORT:-8501}"
PID_FILE="${PID_FILE:-logs/streamlit.pid}"
LOG_FILE="${LOG_FILE:-logs/streamlit.log}"
DEFAULT_PYTHON="$ROOT_DIR/.venv/bin/python"
if [[ -x "$ROOT_DIR/.venv_dashboard/bin/python" ]]; then
    DEFAULT_PYTHON="$ROOT_DIR/.venv_dashboard/bin/python"
fi
PYTHON_BIN="${DASHBOARD_PYTHON:-$DEFAULT_PYTHON}"

mkdir -p "$(dirname "$PID_FILE")" "$(dirname "$LOG_FILE")"

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "Streamlit is already running on port $PORT with PID $(cat "$PID_FILE")."
    exit 0
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Python runtime not found: $PYTHON_BIN" >&2
    echo "Set DASHBOARD_PYTHON=/path/to/python or create .venv first." >&2
    exit 1
fi

nohup "$PYTHON_BIN" -m streamlit run app/streamlit_app.py \
    --server.port "$PORT" \
    --server.headless true \
    >"$LOG_FILE" 2>&1 &

echo "$!" > "$PID_FILE"

for _ in {1..10}; do
    if curl -fsS "http://localhost:$PORT/_stcore/health" >/dev/null 2>&1; then
        echo "Streamlit started on http://localhost:$PORT with PID $(cat "$PID_FILE")."
        echo "Logs: $LOG_FILE"
        exit 0
    fi

    if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "Streamlit failed to start. Recent log output:" >&2
        tail -n 40 "$LOG_FILE" >&2
        rm -f "$PID_FILE"
        exit 1
    fi

    sleep 1
done

echo "Streamlit is still starting on http://localhost:$PORT with PID $(cat "$PID_FILE")."
echo "Logs: $LOG_FILE"
