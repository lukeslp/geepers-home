#!/bin/bash
# Launch sensor-playground dashboard
#
# Usage:
#   bash launch.sh              # Web dashboard (default)
#   bash launch.sh --tkinter    # Legacy tkinter mode
#   bash launch.sh --demo       # Web dashboard with simulated data

cd "$(dirname "$0")"

# Load .env if present (never commit .env — put your DREAMER_API_KEY there)
if [ -f .env ]; then
    set -a
    # shellcheck source=/dev/null
    source .env
    set +a
fi

# DREAMER_API_KEY must be set for LLM chat, voice, and vision to work.
# Get access at https://dr.eamer.dev/code/api
if [ -z "${DREAMER_API_KEY:-}" ]; then
    echo "[warn] DREAMER_API_KEY not set — chat/voice/vision will be unavailable"
fi

# Legacy tkinter mode
if [ "$1" = "--tkinter" ]; then
    shift
    export DISPLAY="${DISPLAY:-:0}"
    exec python3 main.py "$@"
fi

# Web dashboard (default)
exec python3 web_app.py "$@"
