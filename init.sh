#!/bin/bash
# ============================================================================
# Sensor Playground — Pi Connection Init & Status
# ============================================================================
#
# Quick reference for the SSH topology, Pi services, and connectivity.
# Run this to check status or source it for the helper functions.
#
# Usage:
#   bash init.sh              # Full status check
#   bash init.sh tunnel       # Check/diagnose tunnel only
#   bash init.sh pi [cmd]     # Run command on Pi (if tunnel is up)
#   bash init.sh services     # Show Pi systemd service status
#   bash init.sh help         # Show this help
#
# ============================================================================

set -euo pipefail

# --- SSH Topology ---
#
# The Pi has NO public IP. All access goes through a reverse SSH tunnel.
#
#   ┌──────────────────────────────────────────────────────┐
#   │                    dr.eamer.dev (VPS)                 │
#   │                                                      │
#   │   localhost:2222  ◄──── reverse tunnel ────  Pi:22    │
#   │   (SSH to Pi)          (Pi initiates)                │
#   │                                                      │
#   │   VPS:5030  ────── forward tunnel ──────►  Pi:5030   │
#   │   (vision API)         (Pi pulls)          (local)   │
#   └──────────────────────────────────────────────────────┘
#
# Tunnel 1 — Reverse SSH (Pi → VPS, opens VPS:2222 → Pi:22)
#   Pi runs:   ssh -R 2222:localhost:22 dr.eamer.dev
#   Managed by: autossh or systemd on Pi
#   Effect:    VPS can SSH to Pi via `ssh -p 2222 coolhand@localhost`
#
# Tunnel 2 — Vision API (Pi → VPS, pulls VPS:5030 → Pi:localhost:5030)
#   Pi runs:   ssh -L 5030:localhost:5030 -N -T dr.eamer.dev
#   Managed by: vision-tunnel.service on Pi
#   Effect:    Pi dashboard can POST to localhost:5030 for vision analysis
#
# Tunnel 3 — Chat API (Pi → internet)
#   Dashboard POSTs to: https://api.dr.eamer.dev/v1/llm/chat
#   Requires:  Pi has internet access (WiFi or Ethernet)
#   NOT a tunnel — uses Pi's normal internet connection
#

# --- Configuration ---
# Override any of these with environment variables
PI_HOST="${PI_HOST:-pi@localhost}"
PI_PORT="${PI_PORT:-2222}"
PI_DIR="${PI_DIR:-/home/pi/geepers-home}"
PI_LAN_IP="${PI_LAN_IP:-raspberrypi.local}"
PI_HOSTNAME="${PI_HOSTNAME:-raspberrypi.local}"
VPS_HOST="${VPS_HOST:-dr.eamer.dev}"
DASHBOARD_PORT="${DASHBOARD_PORT:-5000}"

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# --- Helpers ---
ok()   { echo -e "${GREEN}[OK]${NC}    $*"; }
fail() { echo -e "${RED}[FAIL]${NC}  $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }
info() { echo -e "${BLUE}[INFO]${NC}  $*"; }

# --- Pi-Side Service Configurations (mirrored here for reference) ---
#
# These are the systemd services installed on the Pi.
# Kept here so we know the setup without needing to SSH in.
#
# 1. sensor-playground-web.service
#    - Runs: /bin/bash /home/pi/geepers-home/launch.sh
#    - WorkingDirectory: /home/pi/geepers-home
#    - User: pi (adjust to your username)
#    - Restart: always (5s delay)
#    - Requires: DREAMER_API_KEY in .env (see .env.example)
#    - Provides: Web dashboard on port 5000
#    - URL on LAN: http://<pi-lan-ip>:5000
#
# 2. vision-tunnel.service
#    - Runs: ssh -L 5030:localhost:5030 -N -T dr.eamer.dev
#    - User: pi (NOTE: different user than dashboard!)
#    - Restart: always (10s delay)
#    - Provides: localhost:5030 → VPS vision API
#    - Required for: Camera "Describe Scene" feature
#
# 3. reverse-ssh-tunnel (exact service name TBD — may be autossh)
#    - Runs: ssh -R 2222:localhost:22 dr.eamer.dev
#    - Provides: VPS can reach Pi via localhost:2222
#    - Required for: deploy.sh, remote debugging, service management
#    - When DOWN: No remote access to Pi at all from VPS
#
# 4. sensor-playground.service (DISABLED — old tkinter GUI)
#    - Do not enable. Superseded by sensor-playground-web.service.
#
# --- Chromium Kiosk (not a systemd service) ---
#    - Autostart: ~/.config/labwc/autostart
#    - Command: chromium --kiosk --noerrdialogs --disable-session-crashed-bubble
#              --disable-infobars --disable-restore-session-state
#              --use-fake-ui-for-media-stream http://localhost:5000
#    - Compositor: labwc (Wayland), Chromium on XWayland (--ozone-platform=x11)
#    - Mic permissions: auto-granted via --use-fake-ui-for-media-stream
#    - Refresh: wtype -k F5 (Wayland) or xdotool key F5 (X11 fallback)
#
# --- Pi Hardware ---
#    - Model: Raspberry Pi (3B/3B+/4/5)
#    - Display: 7" 800x480 touchscreen
#    - Camera: Logitech Brio 100 USB webcam (also provides microphone)
#    - OS: Raspberry Pi OS (Bookworm), labwc compositor
#    - Python: 3.11
#    - GPIO: 23 sensors on I2C, GPIO, 1-Wire, ADC
#    - LAN IP: 192.168.0.228
#    - Hostname: bronx-cheer.local

# ============================================================================
# Functions
# ============================================================================

check_tunnel() {
    echo ""
    info "Checking reverse SSH tunnel (VPS:${PI_PORT} → Pi:22)..."
    if ssh -p "$PI_PORT" -o ConnectTimeout=5 -o BatchMode=yes "$PI_HOST" "echo ok" 2>/dev/null; then
        ok "Reverse tunnel is UP — Pi reachable at ${PI_HOST}:${PI_PORT}"
        return 0
    else
        fail "Reverse tunnel is DOWN — cannot reach Pi from VPS"
        echo ""
        echo "  The Pi initiates this tunnel. To fix:"
        echo "  1. Physical access to Pi, or"
        echo "  2. Someone on the LAN: ssh ${PI_HOST%@*}@${PI_LAN_IP}"
        echo "  3. Then on Pi, restart the tunnel service:"
        echo "     sudo systemctl restart reverse-ssh-tunnel  # (or autossh service)"
        echo "     # or manually: ssh -R 2222:localhost:22 ${VPS_HOST} -N &"
        echo ""
        return 1
    fi
}

check_services() {
    echo ""
    info "Checking Pi services (requires tunnel)..."
    if ! ssh -p "$PI_PORT" -o ConnectTimeout=5 -o BatchMode=yes "$PI_HOST" "echo ok" 2>/dev/null; then
        fail "Cannot reach Pi — tunnel is down"
        return 1
    fi

    echo ""
    info "sensor-playground-web.service (dashboard):"
    ssh -p "$PI_PORT" "$PI_HOST" "systemctl is-active sensor-playground-web 2>/dev/null || echo inactive" | while read -r status; do
        if [ "$status" = "active" ]; then ok "Dashboard running"; else fail "Dashboard: $status"; fi
    done

    info "vision-tunnel.service:"
    ssh -p "$PI_PORT" "$PI_HOST" "systemctl is-active vision-tunnel 2>/dev/null || echo inactive" | while read -r status; do
        if [ "$status" = "active" ]; then ok "Vision tunnel running"; else warn "Vision tunnel: $status"; fi
    done

    echo ""
    info "Dashboard accessible on Pi?"
    ssh -p "$PI_PORT" "$PI_HOST" "curl -s -o /dev/null -w '%{http_code}' http://localhost:${DASHBOARD_PORT}/ 2>/dev/null" | while read -r code; do
        if [ "$code" = "200" ]; then ok "Dashboard responding (HTTP $code)"; else fail "Dashboard HTTP $code"; fi
    done

    info "Chat API reachable from Pi?"
    ssh -p "$PI_PORT" "$PI_HOST" "curl -s -o /dev/null -w '%{http_code}' --max-time 5 https://api.dr.eamer.dev/health 2>/dev/null" | while read -r code; do
        if [ "$code" = "200" ]; then ok "Chat API reachable ($code)"; else fail "Chat API unreachable ($code) — Pi may lack internet"; fi
    done

    info "Vision API reachable from Pi (via tunnel)?"
    ssh -p "$PI_PORT" "$PI_HOST" "curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://localhost:5030/health 2>/dev/null" | while read -r code; do
        if [ "$code" = "200" ]; then ok "Vision API reachable ($code)"; else warn "Vision API unreachable ($code)"; fi
    done
}

run_on_pi() {
    if ! ssh -p "$PI_PORT" -o ConnectTimeout=5 -o BatchMode=yes "$PI_HOST" "echo ok" 2>/dev/null; then
        fail "Cannot reach Pi — tunnel is down"
        return 1
    fi
    ssh -p "$PI_PORT" "$PI_HOST" "$@"
}

show_help() {
    echo "Sensor Playground — Pi Connection Init & Status"
    echo ""
    echo "Usage:"
    echo "  bash init.sh              Full status check (tunnel + services)"
    echo "  bash init.sh tunnel       Check tunnel only"
    echo "  bash init.sh services     Check Pi services"
    echo "  bash init.sh pi [cmd]     Run command on Pi"
    echo "  bash init.sh deploy       Deploy code + restart (shortcut)"
    echo "  bash init.sh logs         Follow dashboard logs"
    echo "  bash init.sh help         This help text"
    echo ""
    echo "Quick commands when tunnel is up:"
    echo "  bash init.sh pi uptime"
    echo "  bash init.sh pi 'systemctl status sensor-playground-web'"
    echo "  bash init.sh pi 'journalctl -u sensor-playground-web -n 20'"
    echo ""
    echo "SSH topology:"
    echo "  VPS → Pi:   ssh -p ${PI_PORT} ${PI_HOST}"
    echo "  LAN → Pi:   ssh ${PI_HOST%@*}@${PI_LAN_IP}"
    echo "  LAN → Pi:   ssh ${PI_HOST%@*}@${PI_HOSTNAME}"
}

full_status() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Sensor Playground — Connection Status"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    check_tunnel
    local tunnel_up=$?

    if [ $tunnel_up -eq 0 ]; then
        check_services
    fi

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Quick Reference"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  Deploy + restart:  bash deploy.sh && bash deploy.sh --service restart"
    echo "  Follow logs:       bash deploy.sh --service logs"
    echo "  SSH to Pi:         ssh -p ${PI_PORT} ${PI_HOST}"
    echo "  Pi LAN:            http://${PI_LAN_IP}:${DASHBOARD_PORT}"
    echo ""
}

# ============================================================================
# Main
# ============================================================================

case "${1:-}" in
    tunnel)    check_tunnel ;;
    services)  check_services ;;
    pi)        shift; run_on_pi "$@" ;;
    deploy)    bash "$(dirname "$0")/deploy.sh" && bash "$(dirname "$0")/deploy.sh" --service restart ;;
    logs)      bash "$(dirname "$0")/deploy.sh" --service logs ;;
    help|-h|--help) show_help ;;
    "")        full_status ;;
    *)         echo "Unknown: $1"; show_help; exit 1 ;;
esac
