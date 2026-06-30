#!/usr/bin/env bash
# RPi Guardian - start the inspection proxy and the dashboard.
# Run on the Raspberry Pi (no root needed):  bash start_guardian.sh
#
# Launches:
#   - mitmdump (transparent) on :8080 running guardian/detector.py
#   - Streamlit dashboard on 192.168.50.1:8501 (open it from Computer B)
#
# Press Ctrl+C to stop both.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARDIAN_DIR="$(cd "$SCRIPT_DIR/../../guardian" && pwd)"
MITMDUMP="$HOME/.local/bin/mitmdump"

DASH_ADDR="${DASH_ADDR:-192.168.50.1}"
DASH_PORT="${DASH_PORT:-8501}"

if [[ ! -x "$MITMDUMP" ]]; then
    echo "mitmdump not found at $MITMDUMP. Run setup_rpi.sh first." >&2
    exit 1
fi

cleanup() {
    echo "Stopping RPi Guardian..."
    [[ -n "${MITM_PID:-}" ]] && kill "$MITM_PID" 2>/dev/null || true
    [[ -n "${DASH_PID:-}" ]] && kill "$DASH_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

cd "$GUARDIAN_DIR"

echo "==> Starting mitmdump on :8080 ..."
"$MITMDUMP" --mode transparent -s detector.py --listen-port 8080 \
    --set block_global=false &
MITM_PID=$!

echo "==> Starting dashboard on http://$DASH_ADDR:$DASH_PORT ..."
python3 -m streamlit run dashboard.py \
    --server.address "$DASH_ADDR" --server.port "$DASH_PORT" \
    --server.headless true &
DASH_PID=$!

echo
echo "RPi Guardian is running."
echo "  Dashboard: http://$DASH_ADDR:$DASH_PORT  (open from Computer B)"
echo "  Press Ctrl+C to stop."
wait
