# Flask Deployment Guide

Guide for deploying the Flask web interface on Raspberry Pi 3B+ with kiosk mode.

## Architecture

The Flask app replaces the tkinter GUI while keeping all sensor collection code:

```
┌─────────────────────────────────────────┐
│  Chromium Kiosk (800x480 touchscreen)  │
│  http://localhost:5000                  │
└─────────────────────────────────────────┘
                   ▲
                   │ HTTP/SSE
                   ▼
┌─────────────────────────────────────────┐
│  Flask App (flask_app.py)               │
│  - SSE stream for real-time updates     │
│  - REST API for chat/camera             │
│  - Static file serving                  │
└─────────────────────────────────────────┘
                   ▲
                   │ EventBus pub/sub
                   ▼
┌─────────────────────────────────────────┐
│  Data Sources (background threads)      │
│  - SensorSource (6 I2C sensors)         │
│  - CameraSource (USB webcam)            │
│  - VisionSource (scene description)     │
│  - SystemSource (CPU/RAM/disk)          │
│  - NetworkSource (ping/IP)              │
│  - RESTSource (weather API)             │
└─────────────────────────────────────────┘
```

## Installation

### 1. Install Flask Dependencies

```bash
cd /home/pi/sensor-playground
sudo pip3 install --break-system-packages Flask Flask-CORS
```

### 2. Verify Existing Setup

Ensure sensors are working with the old GUI:

```bash
python3 main.py --demo
```

### 3. Test Flask App

```bash
python3 flask_app.py
```

Open browser to `http://localhost:5000` - you should see the dashboard.

## Systemd Service

Create `/etc/systemd/system/sensor-dashboard-web.service`:

```ini
[Unit]
Description=Raspberry Pi Sensor Dashboard (Flask)
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/sensor-playground
ExecStart=/usr/bin/python3 /home/pi/sensor-playground/flask_app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable sensor-dashboard-web
sudo systemctl start sensor-dashboard-web
```

Check status:

```bash
sudo systemctl status sensor-dashboard-web
sudo journalctl -u sensor-dashboard-web -f
```

## Kiosk Mode Setup

### Install Chromium (if not present)

```bash
sudo apt update
sudo apt install chromium-browser x11-xserver-utils unclutter
```

### Configure Autostart

Edit `/home/pi/.config/lxsession/LXDE-pi/autostart` (create if needed):

```
@lxpanel --profile LXDE-pi
@pcmanfm --desktop --profile LXDE-pi
@xscreensaver -no-splash

# Disable screen blanking
@xset s off
@xset -dpms
@xset s noblank

# Hide mouse cursor
@unclutter -idle 0.5 -root

# Launch Chromium in kiosk mode
@chromium-browser --kiosk --noerrdialogs --disable-infobars --disable-session-crashed-bubble --disable-restore-session-state --disable-component-update http://localhost:5000
```

### Touchscreen Calibration (if needed)

```bash
sudo apt install xinput-calibrator
DISPLAY=:0 xinput_calibrator
```

Follow on-screen instructions, then save calibration to `~/.config/autostart/touchscreen-calibration.desktop`.

### Reboot to Kiosk

```bash
sudo reboot
```

After reboot, Chromium should launch fullscreen at 800x480 showing the dashboard.

## VPS API Setup

The Flask app proxies chat and vision requests to your VPS. Ensure the VPS is running the Pi Vision API.

### SSH Tunnel (Development)

For local development, create an SSH tunnel to the VPS:

```bash
ssh -L 5030:localhost:5030 dr.eamer.dev
```

Then configure `dashboard.yaml` to use `http://localhost:5030/api/...` instead of HTTPS.

### Production (Direct HTTPS)

In production, the Flask app connects directly to `https://dr.eamer.dev/pivision/api/...` (no tunnel needed).

## Configuration

Edit `dashboard.yaml` to configure sensors and data sources.

### Camera Settings

```yaml
- id: "camera.feed"
  type: "camera"
  device: "/dev/video0"
  width: 320
  height: 240
  fps: 2
  interval: 0.1
  motion_threshold: 3.0
  snapshot_interval: 300
```

### Vision API

```yaml
- id: "camera.vision"
  type: "vision"
  endpoint: "https://dr.eamer.dev/pivision/api/analyze"
  provider: "xai"  # or "openai"
  detail: "brief"
  interval: 60
```

### Sensor Intervals

Adjust polling intervals (in seconds):

```yaml
- id: "sensor.bme280"
  type: "sensor"
  sensor_key: "bme280"
  interval: 2  # Poll every 2 seconds
```

## API Endpoints

### REST API

- `GET /` - Main dashboard page
- `GET /health` - Health check
- `GET /api/sensors` - All sensor readings
- `GET /api/sensors/:id` - Specific sensor
- `GET /api/sensors/:id/history` - Sensor history
- `GET /api/situation` - Structured context for LLM
- `GET /api/camera/frame` - Latest camera JPEG
- `GET /api/camera/status` - Motion detection status
- `POST /api/chat` - Chat with LLM (proxies to VPS)
- `POST /api/vision/analyze` - Vision analysis (proxies to VPS)

### SSE Stream

- `GET /stream` - Real-time sensor updates

See `API_CONTRACT.md` for full details.

## Frontend Customization

The web UI is in `static/index.html`. Customize as needed:

- Layout: 800x480 grid
- Colors: Dark theme (#1a1a1a background)
- Update frequency: 2Hz SSE updates
- Camera: 1 FPS JPEG polling

### Adding Custom Cards

Edit `static/index.html` to add more sensor cards:

```html
<div class="card">
    <div class="card-label">CPU Temp</div>
    <div class="card-value" id="cpu-value">--</div>
    <div class="card-unit">°C</div>
</div>
```

Update JavaScript to handle the sensor:

```javascript
if (sourceId === 'system.stats') {
    if (data.cpu_temp) {
        document.getElementById('cpu-value').textContent = data.cpu_temp.toFixed(1);
    }
}
```

## Troubleshooting

### Flask won't start

Check logs:
```bash
sudo journalctl -u sensor-dashboard-web -f
```

Common issues:
- Port 5000 already in use: `lsof -i :5000`
- Missing dependencies: `pip3 list | grep -i flask`
- Config file not found: Check `dashboard.yaml` exists

### SSE disconnects

- Browser refresh: SSE auto-reconnects after 3 seconds
- Network issues: Check `net.health` source in config
- Server restart: SSE will reconnect automatically

### Camera not showing

- Check device: `ls -l /dev/video0`
- Test ffmpeg: `ffmpeg -f v4l2 -i /dev/video0 -frames:v 1 test.jpg`
- Check permissions: `groups` should include `video`

### Vision API timeout

- SSH tunnel: Ensure tunnel is running (`ps aux | grep ssh`)
- VPS status: Check VPS is running the API (`systemctl status pivision`)
- Network latency: Increase timeout in `flask_app.py` (default: 30s)

### Kiosk not launching

- X11 permissions: `DISPLAY=:0 xhost +`
- Chromium path: `which chromium-browser`
- Autostart syntax: Check `/home/pi/.config/lxsession/LXDE-pi/autostart`

## Performance

### Resource Usage (Pi 3B+)

- Flask app: ~40MB RAM, 5-10% CPU
- Chromium kiosk: ~150MB RAM, 20-30% CPU
- Total system: ~35-40% RAM usage

### Optimization

1. Reduce SSE update frequency (edit `flask_app.py`, line 303: `time.sleep(0.5)` → `time.sleep(1.0)`)
2. Lower camera resolution (edit `dashboard.yaml`: `width: 160, height: 120`)
3. Disable unused sensors (comment out in `dashboard.yaml`)

## Development vs Production

### Development (VPS on localhost via tunnel)

```bash
# Terminal 1: SSH tunnel
ssh -L 5030:localhost:5030 dr.eamer.dev

# Terminal 2: Flask app
python3 flask_app.py

# Browser: http://localhost:5000
```

### Production (systemd + kiosk)

```bash
# Enable service
sudo systemctl enable sensor-dashboard-web
sudo systemctl start sensor-dashboard-web

# Reboot to launch kiosk
sudo reboot
```

## Migration from Tkinter

To switch from the old tkinter GUI to Flask:

1. Stop the old systemd service:
   ```bash
   sudo systemctl stop sensor-playground
   sudo systemctl disable sensor-playground
   ```

2. Install Flask and start the web service:
   ```bash
   sudo pip3 install --break-system-packages Flask Flask-CORS
   sudo systemctl enable sensor-dashboard-web
   sudo systemctl start sensor-dashboard-web
   ```

3. Configure kiosk mode (see above)

4. Reboot:
   ```bash
   sudo reboot
   ```

The web UI will launch in kiosk mode on boot.

## Backup and Recovery

### Backup Configuration

```bash
tar -czf sensor-dashboard-backup.tar.gz \
    flask_app.py \
    dashboard.yaml \
    static/ \
    core/ \
    sources/ \
    sensors/
```

### Restore

```bash
tar -xzf sensor-dashboard-backup.tar.gz
sudo systemctl restart sensor-dashboard-web
```

## Related Files

- `flask_app.py` - Flask application
- `dashboard.yaml` - Sensor configuration
- `API_CONTRACT.md` - API documentation
- `SENSOR_CONTEXT_SCHEMA.md` - Data format spec
- `static/index.html` - Web UI frontend
- `requirements.txt` - Python dependencies
