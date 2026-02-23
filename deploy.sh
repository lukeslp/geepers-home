#!/bin/bash
# Deploy sensor-playground to Raspberry Pi
#
# Usage:
#   bash deploy.sh                    # Deploy code to Pi
#   bash deploy.sh --setup            # First-time setup (deps + deploy)
#   bash deploy.sh --tunnel           # Start vision API tunnel only
#   bash deploy.sh --service install  # Install systemd service
#   bash deploy.sh --service start    # Start the service
#
# Configure PI_HOST below or set as environment variable.

set -e

# --- Configuration ---
# From VPS: Pi is reachable via reverse SSH tunnel on port 2222
# From LAN: Pi is reachable at bronx-cheer.local
PI_HOST="${PI_HOST:-coolhand@localhost}"
PI_SSH_PORT="${PI_SSH_PORT:-2222}"
PI_DIR="/home/coolhand/sensor-playground"
VPS_HOST="${VPS_HOST:-dr.eamer.dev}"
VISION_PORT=5030

# --- Helpers ---
info()  { echo -e "\033[1;34m[deploy]\033[0m $*"; }
ok()    { echo -e "\033[1;32m[deploy]\033[0m $*"; }
warn()  { echo -e "\033[1;33m[deploy]\033[0m $*"; }
err()   { echo -e "\033[1;31m[deploy]\033[0m $*" >&2; }

usage() {
    echo "Usage: bash deploy.sh [--setup|--tunnel|--service install|start|stop|status]"
    echo ""
    echo "  (no args)         Sync code to Pi"
    echo "  --setup           First-time: install deps + sync code"
    echo "  --tunnel          Start reverse SSH tunnel for vision API"
    echo "  --service CMD     Manage systemd service (install/start/stop/status)"
    echo "  --refresh         Refresh Chromium browser on Pi (F5)"
    echo "  --kiosk install   Install Chromium kiosk autostart"
    echo ""
    echo "Environment:"
    echo "  PI_HOST           Pi SSH target (default: pi@pistation.local)"
    echo "  VPS_HOST          VPS hostname (default: dr.eamer.dev)"
}

# --- Sync code to Pi ---
deploy_code() {
    info "Syncing code to ${PI_HOST}:${PI_DIR}..."

    rsync -avz --delete \
        -e "ssh -p ${PI_SSH_PORT}" \
        --exclude '__pycache__' \
        --exclude '*.pyc' \
        --exclude '.env' \
        --exclude 'data/' \
        --exclude 'snapshots/' \
        --exclude '.venv/' \
        --exclude 'venv/' \
        --exclude '.claude/' \
        --exclude '*.backup' \
        --exclude '*.md' \
        --exclude '.git/' \
        --exclude '.lgd-nfy0' \
        --exclude 'sensor_data.db*' \
        ./ "${PI_HOST}:${PI_DIR}/"

    ok "Code synced to ${PI_HOST}:${PI_DIR}"
}

# --- First-time setup ---
first_time_setup() {
    info "Running first-time setup on Pi..."

    # Create directory
    ssh -p "$PI_SSH_PORT" "$PI_HOST" "mkdir -p ${PI_DIR}"

    # Sync code first
    deploy_code

    # Run setup script on Pi
    info "Installing dependencies on Pi..."
    ssh -p "$PI_SSH_PORT" "$PI_HOST" "cd ${PI_DIR} && bash setup.sh"

    ok "Setup complete! Run 'bash deploy.sh --service install' to auto-start on boot."
}

# --- SSH tunnel for vision API ---
# Pi connects TO the VPS, pulling port 5030 locally so the
# dashboard can hit http://localhost:5030/api/analyze
start_tunnel() {
    info "Starting SSH tunnel: localhost:${VISION_PORT} -> ${VPS_HOST}:${VISION_PORT}"
    info "Press Ctrl+C to stop"
    echo ""

    # -L binds local port on Pi to VPS port
    # -N no remote command, -T no terminal, -o keeps alive
    ssh -L "${VISION_PORT}:localhost:${VISION_PORT}" \
        -N -T \
        -o ServerAliveInterval=30 \
        -o ServerAliveCountMax=3 \
        -o ExitOnForwardFailure=yes \
        "$VPS_HOST"
}

# --- Systemd service management ---
manage_service() {
    local cmd="$1"

    case "$cmd" in
        install)
            info "Installing web dashboard systemd service on Pi..."
            scp -P "$PI_SSH_PORT" sensor-playground-web.service "${PI_HOST}:/tmp/"
            ssh -p "$PI_SSH_PORT" "$PI_HOST" "sudo cp /tmp/sensor-playground-web.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable sensor-playground-web"
            ok "Service installed and enabled. Start with: bash deploy.sh --service start"
            ;;
        start)
            ssh -p "$PI_SSH_PORT" "$PI_HOST" "sudo systemctl start sensor-playground-web"
            ok "Service started"
            ssh -p "$PI_SSH_PORT" "$PI_HOST" "sudo systemctl status sensor-playground-web --no-pager"
            ;;
        stop)
            ssh -p "$PI_SSH_PORT" "$PI_HOST" "sudo systemctl stop sensor-playground-web"
            ok "Service stopped"
            ;;
        status)
            ssh -p "$PI_SSH_PORT" "$PI_HOST" "sudo systemctl status sensor-playground-web --no-pager" || true
            ;;
        restart)
            ssh -p "$PI_SSH_PORT" "$PI_HOST" "sudo systemctl restart sensor-playground-web"
            ok "Service restarted"
            # Give Flask a moment to start, then refresh browser
            sleep 2
            refresh_browser
            ;;
        logs)
            ssh -p "$PI_SSH_PORT" "$PI_HOST" "journalctl -u sensor-playground-web -f --no-pager"
            ;;
        *)
            err "Unknown service command: $cmd"
            echo "Valid: install, start, stop, restart, status, logs"
            exit 1
            ;;
    esac
}

# --- Refresh Chromium browser ---
refresh_browser() {
    info "Refreshing Chromium on Pi..."
    # wtype sends keys on Wayland (labwc compositor)
    # Chromium runs on XWayland, but wtype targets the focused window
    ssh -p "$PI_SSH_PORT" "$PI_HOST" \
        "WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 wtype -k F5" 2>/dev/null \
        && ok "Browser refreshed (wtype)" \
        || {
            # Fallback: xdotool for XWayland
            ssh -p "$PI_SSH_PORT" "$PI_HOST" "DISPLAY=:0 xdotool key F5" 2>/dev/null \
                && ok "Browser refreshed (xdotool)" \
                || warn "Could not refresh browser — is Chromium running?"
        }
}

# --- Install Chromium kiosk autostart ---
install_kiosk() {
    info "Installing Chromium kiosk autostart on Pi..."
    ssh -p "$PI_SSH_PORT" "$PI_HOST" "mkdir -p ~/.config/labwc"

    # Create labwc autostart that launches Chromium after the panel
    ssh -p "$PI_SSH_PORT" "$PI_HOST" "cat > ~/.config/labwc/autostart << 'AUTOSTART'
# Launch Chromium in kiosk mode after a brief delay
# (wait for the web dashboard service to be ready)
(sleep 5 && chromium --kiosk --noerrdialogs --disable-session-crashed-bubble --disable-infobars --disable-restore-session-state http://localhost:5000) &
AUTOSTART"

    ok "Kiosk autostart installed at ~/.config/labwc/autostart"
    ok "Chromium will launch on next boot pointing to http://localhost:5000"
}

# --- Main ---
case "${1:-}" in
    --setup)
        first_time_setup
        ;;
    --tunnel)
        start_tunnel
        ;;
    --service)
        if [ -z "$2" ]; then
            err "Missing service command"
            usage
            exit 1
        fi
        manage_service "$2"
        ;;
    --refresh)
        refresh_browser
        ;;
    --kiosk)
        if [ "$2" = "install" ]; then
            install_kiosk
        else
            err "Usage: --kiosk install"
            exit 1
        fi
        ;;
    --help|-h)
        usage
        ;;
    "")
        deploy_code
        ;;
    *)
        err "Unknown option: $1"
        usage
        exit 1
        ;;
esac
