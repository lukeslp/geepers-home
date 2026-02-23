#!/bin/bash
# Flask app launcher for Raspberry Pi sensor dashboard

set -e

cd "$(dirname "$0")"

echo "Starting Raspberry Pi Sensor Dashboard (Flask)..."

# Check Python version
python3 --version

# Check Flask is installed
if ! python3 -c "import flask" 2>/dev/null; then
    echo "ERROR: Flask not installed. Run:"
    echo "  sudo pip3 install --break-system-packages Flask Flask-CORS"
    exit 1
fi

# Check config file exists
if [ ! -f "dashboard.yaml" ]; then
    echo "ERROR: dashboard.yaml not found"
    exit 1
fi

# Set environment
export PYTHONUNBUFFERED=1
export PORT="${PORT:-5000}"

# Run Flask app
exec python3 flask_app.py
