#!/bin/bash
# Launch sensor-playground dashboard
#
# Usage:
#   bash launch.sh              # Web dashboard (default)
#   bash launch.sh --tkinter    # Legacy tkinter mode
#   bash launch.sh --demo       # Web dashboard with simulated data

cd "$(dirname "$0")"

# API gateway key for LLM chat
export DREAMER_API_KEY="REDACTED"

# Legacy tkinter mode
if [ "$1" = "--tkinter" ]; then
    shift
    export DISPLAY="${DISPLAY:-:0}"
    exec python3 main.py "$@"
fi

# Web dashboard (default)
exec python3 web_app.py "$@"
