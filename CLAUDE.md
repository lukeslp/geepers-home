# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Geepers Home** — Raspberry Pi sensor dashboard with three runtime modes: a tkinter touchscreen GUI (v3 "Home Station"), a Flask web dashboard (v4.1), and a classic tab-based sensor browser (v1). Reads 23 sensors across I2C, GPIO, 1-Wire, and ADC, plus USB webcam with vision analysis, voice input, weather, news, and radio scanning. Targets Pi 3B/3B+/4/5 with an 800x480 touchscreen.

**Ecosystem dependency**: LLM chat, voice STT, and vision analysis proxy to the API ecosystem at [dr.eamer.dev/code/api](https://dr.eamer.dev/code/api). Local sensor reads work without it, but chat/voice/vision require access to those endpoints.

## Commands

```bash
# First-time setup (installs apt packages, pip packages, enables I2C/SPI/1-Wire)
bash setup.sh

# Web dashboard (default mode, v4.1)
python3 web_app.py
python3 web_app.py --demo              # Simulated sensor data
python3 web_app.py --port 5000         # Custom port

# Production launcher (sets API keys, picks web or tkinter)
bash launch.sh                         # Web dashboard (default)
bash launch.sh --tkinter               # Tkinter Home Station v3
bash launch.sh --demo                  # Web with simulated data

# Tkinter modes
python3 main.py                        # Home Station v3 (extensible cards)
python3 main.py --demo                 # Demo mode
python3 main.py --classic              # v1 tab-based sensor browser
python3 main.py --legacy               # v2 single-page dashboard
python3 main.py --config alt.yaml      # Custom YAML config

# Flask API server (older prototype, mostly superseded by web_app.py)
python3 flask_app.py

# Verbose logging (any mode)
python3 web_app.py --demo --log-level DEBUG

# GPIO tools
python3 tools/gpio_scanner.py          # Color-coded 40-pin header view
python3 tools/gpio_scanner.py --watch  # Monitor pin state changes at 50ms
```

There are no tests, linter, or build system. The app is run directly with `python3`.

## Architecture

### Three Runtime Modes

**v4.1 Web Dashboard (`web_app.py`)** — Default. Flask server with SSE streaming, HTML/CSS/JS frontend in `web/`, chat proxy to VPS LLM gateway. No tkinter dependency. Uses `WebEventBus` for thread-safe pub/sub. Includes SQLite time-series storage (`DataStore`), threshold alerts (`AlertManager`), browser-based voice input, and dynamic sensor config API.

**v3 Home Station (`ui/home_station.py`)** — Tkinter. Multi-page card-based dashboard loaded from `dashboard.yaml`. Uses `EventBus` (tkinter-coupled, queue-drained on main thread). Supports pages, kiosk mode, detail overlays, CSV logging.

**v1/v2 Classic (`ui/app.py`, `ui/dashboard.py`)** — Legacy tkinter modes. Tab-based sensor browser and single-page dashboard. Still functional via `--classic`/`--legacy` flags.

### Core Framework (`core/`)

The v3/v4 architecture uses a plugin-based framework:

- **`EventBus`** (`core/event_bus.py`) — Thread-safe pub/sub for tkinter mode. Background threads push to a Queue; main thread polls at 50ms and dispatches to subscribers.
- **`WebEventBus`** (`core/web_event_bus.py`) — Thread-safe pub/sub for Flask mode. No tkinter dependency. Supports SSE streaming via `sse_stream()` generator.
- **`DataSource`** (`core/data_source.py`) — ABC for background data providers. Subclasses implement `fetch()` which returns `Dict` or `None`. The base class handles threading, polling intervals, and publish.
- **`DataStore`** (`core/data_store.py`) — SQLite time-series store with WAL mode. Buffers writes (10s flush interval), auto-downsamples to hourly averages, provides adaptive-resolution history queries (raw for 1h, 5-min avg for 24h, hourly avg beyond). 7-day raw data retention.
- **`AlertManager`** (`core/alerts.py`) — Threshold-based alert system. Parses rules from `dashboard.yaml` `alerts:` section. Supports `>`, `<`, `>=`, `<=`, `==` operators, severity levels (info/warn/critical), and per-rule cooldown periods. Publishes triggered alerts to the event bus as `"alert"` topic.
- **`BaseCard`** (`core/base_card.py`) — ABC for tkinter display widgets. Subclasses implement `setup_ui()` (once) and `on_data()` (per update). Subscribes to EventBus topics.
- **`PageManager`** (`core/page_manager.py`) — Fixed-grid page layout (3x2 by default). Pagination instead of scrolling for touchscreen reliability.
- **Registry** (`core/registry.py`) — `@register_card("type")` and `@register_source("type")` decorators. YAML config references types by name; registry resolves to classes.

### Plugin Registration Pattern

Sources and cards self-register via decorators. Importing the `sources` or `cards` package triggers all `@register_source`/`@register_card` calls:

```python
@register_source("sensor")
class SensorSource(DataSource):
    def fetch(self): ...
```

To add a new data source: create a class inheriting `DataSource`, decorate with `@register_source("name")`, import it in `sources/__init__.py`, add entries to `dashboard.yaml`.

To add a new card type (tkinter only): create a class inheriting `BaseCard`, decorate with `@register_card("name")`, import it in `cards/__init__.py`, reference it in `dashboard.yaml`.

### Configuration (`dashboard.yaml`)

Single YAML config for both v3 and v4 modes. Three sections:
- **`pages`** — List of pages, each with a list of card configs (type, source_id, display params, thresholds, unit, convert)
- **`sources`** — List of data source configs (type, id, polling interval, hardware params)
- **`alerts`** — List of threshold alert rules (field, condition, level, message, cooldown)

Source types: `sensor`, `system`, `network`, `camera`, `vision`, `rest`, `weather`, `wifi_scanner`, `bluetooth_scanner`, `news`.

Card configs support `unit` (display suffix) and `convert` (e.g. `"c_to_f"`) for unit conversion.

### Sensor Class Hierarchy (`sensors/`)

All 23 sensor classes inherit from `BaseSensor` (`sensors/base.py`), which provides retry logic, reliability tracking, error isolation, and a unified `read(demo=False)` interface. Subclasses implement `_init_hardware()`, `_read_hardware()`, `_simulate()`.

The 9 simple digital GPIO sensors inherit from `DigitalSensor` (`sensors/digital.py`), reducing each to 4 class attributes (`FIELD_NAME`, `INVERT`, `SIM_PROB`, `BIAS`).

`SENSOR_CLASSES` dict in `sensors/__init__.py` maps config keys to classes.

### Data Sources (`sources/`)

| Source | Type | What it does |
|--------|------|-------------|
| `SensorSource` | `sensor` | Wraps any `BaseSensor` subclass, polls at configured interval |
| `SystemSource` | `system` | CPU temp, RAM, disk via `/proc` and `psutil` |
| `NetworkSource` | `network` | Ping, IP address, throughput |
| `CameraSource` | `camera` | USB webcam via ffmpeg subprocess, motion detection via numpy |
| `VisionSource` | `vision` | POSTs camera JPEG to VPS API for scene description |
| `WeatherSource` | `weather` | Open-Meteo API: outdoor temp, humidity, wind, weather code, sunrise/sunset |
| `WiFiScannerSource` | `wifi_scanner` | Scans WiFi APs via `sudo iw dev wlan0 scan`, 60s interval |
| `BluetoothScannerSource` | `bluetooth_scanner` | Scans BLE + classic Bluetooth via `hcitool`, 120s interval |
| `NewsSource` | `news` | NYT RSS headlines (14 sections available), no API key needed |
| `RESTSource` | `rest` | Generic HTTP GET with JSON extraction |

`SensorSource` falls back gracefully when GPIO libraries are unavailable (import with try/except in `sources/__init__.py`).

Radio scanners (`wifi_scanner`, `bluetooth_scanner`) require passwordless sudo configured in `/etc/sudoers.d/sensor-playground` for `/usr/sbin/iw`, `/usr/bin/hcitool`, and `/usr/bin/timeout`. Without this, WiFi falls back to `/proc/net/wireless` (connected network only), and BLE falls back to `bluetoothctl devices` (paired only).

### Web Frontend (`web/`)

`web/templates/index.html` — Jinja2 template served by Flask
`web/static/app.js` — EventSource (SSE) client, sensor card rendering, chat interface
`web/static/style.css` — Dark theme for 800x480 touchscreen

`static/index.html` — Older standalone HTML (used by `flask_app.py`, not `web_app.py`)

### Web API (`web_app.py` v4.1)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/sensors/stream` | GET | SSE stream (events: sensor, vision, weather, voice, news, alert) |
| `/api/sensors` | GET | Snapshot of all latest readings |
| `/api/config` | GET | Sensor metadata from dashboard.yaml (eliminates hardcoded frontend map) |
| `/api/history/<field>` | GET | Time-series data with auto-resolution (`?hours=24&points=300`) |
| `/api/history/summary` | GET | 24h min/max/avg/current for all fields |
| `/api/history/fields` | GET | List of fields with recorded data |
| `/api/alerts` | GET | Currently active (uncleared) alerts |
| `/api/chat` | POST | LLM chat with sensor context (proxies to `api.dr.eamer.dev/v1/llm/chat`) |
| `/api/voice` | POST | Browser audio blob → VPS Whisper STT → transcribed text |
| `/api/camera/frame` | GET | Latest camera JPEG |
| `/api/demo` | POST | Toggle demo mode for all sources |

### Voice Input (Browser -> VPS Whisper)

Browser-based voice input using MediaRecorder API. User taps mic button -> Chromium captures audio via getUserMedia -> WebM/Opus blob POSTs to Flask `/api/voice` -> Flask forwards to VPS `api.dr.eamer.dev/v1/voice/transcribe` -> OpenAI Whisper STT -> transcribed text feeds into `/api/chat` flow.

Chromium kiosk uses `--use-fake-ui-for-media-stream` for auto mic permissions. The Brio 100 webcam provides the microphone.

**Legacy:** `voice/` directory contains an older Python/ALSA-based recording approach (not used by web dashboard).

### Camera & Vision

`CameraSource` captures raw RGB24 frames from USB webcam via ffmpeg subprocess, converts to PIL Image, runs numpy frame differencing for motion detection, saves periodic snapshots.

`VisionSource` POSTs camera JPEGs to `https://dr.eamer.dev/pivision/api/analyze` for scene description via xAI (grok-2-vision) or OpenAI (gpt-4o). Currently commented out in `dashboard.yaml` (on-demand only).

### GPIO Abstraction (`sensors/gpio_utils.py`)

Wraps libgpiod with auto-detection of GPIO chip (`/dev/gpiochip0` for Pi 3/4, `/dev/gpiochip4` for Pi 5). DHT11 uses Adafruit's library directly. DS18B20 uses kernel 1-Wire driver. ADC sensors use `sensors/adc.py` singleton (`ADCManager`).

### Two Flask Apps

**`web_app.py`** (v4.1, current) — Uses `WebEventBus` + `DataStore` + `AlertManager`, Jinja2 templates from `web/templates/`, static from `web/static/`. SSE at `/api/sensors/stream`. Chat proxies to `api.dr.eamer.dev/v1/llm/chat`. Data wired via `_wire_data_store()` monkey-patching `bus.publish` to also record and check alerts.

**`flask_app.py`** (earlier prototype) — Uses its own `FlaskEventBus`, static from `static/`. SSE at `/stream`. Chat proxies to `dr.eamer.dev/pivision/api/chat`.

### Deployment

The Pi (`bronx-cheer.local` on LAN, `coolhand@localhost:2222` from VPS via reverse SSH tunnel) runs the web dashboard as a systemd service.

```bash
# From VPS: deploy code and restart (auto-refreshes browser)
bash deploy.sh                    # Sync code to Pi via rsync (port 2222)
bash deploy.sh --service restart  # Restart service + refresh browser
bash deploy.sh --service logs     # Follow service logs
bash deploy.sh --service status   # Check service status
bash deploy.sh --refresh          # Refresh browser only (no restart)

# First-time setup
bash deploy.sh --setup            # Install deps + sync code
bash deploy.sh --service install  # Install systemd service (sensor-playground-web)
bash deploy.sh --kiosk install    # Install Chromium kiosk autostart

# Other
bash deploy.sh --tunnel           # Start vision API tunnel
```

**IMPORTANT**: After every code change, you MUST deploy and restart:
```bash
bash deploy.sh && bash deploy.sh --service restart
```
This syncs code, restarts Flask, and sends F5 to Chromium via `wtype` (Wayland).

**Chromium Kiosk Mode:**
- Pi runs labwc (Wayland compositor), Chromium runs on XWayland (`--ozone-platform=x11`)
- Autostart: `~/.config/labwc/autostart` launches Chromium in kiosk mode after 5s delay
- Browser refresh: `wtype -k F5` (Wayland-native), fallback `xdotool key F5` (XWayland)
- Kiosk flags: `--kiosk --noerrdialogs --disable-session-crashed-bubble --disable-infobars`
- Both `wtype` and `xdotool` are installed on the Pi

**Systemd services on Pi:**
- `sensor-playground-web.service` — Web dashboard (v4, Flask, auto-restarts on crash, starts on boot)
- `sensor-playground.service` — Old tkinter GUI (disabled, do not use)
- `vision-tunnel.service` — SSH tunnel to VPS vision API

**Pi connection from VPS:**
- SSH: `ssh -p 2222 coolhand@localhost`
- The Pi maintains a reverse SSH tunnel (`ssh -R 2222:localhost:22 dr.eamer.dev`)
- Pi LAN IP: `192.168.0.228`, hostname: `bronx-cheer.local`
- Dashboard URL (on LAN): `http://192.168.0.228:5000`

### Key Pin Assignments

| Sensor | BCM Pin | Voltage | Category |
|--------|---------|---------|----------|
| DHT11 | 4 | 3.3V | Environment |
| Knock | 5 | 5V | Sound |
| Light | 6 | 5V | Light & IR |
| DS18B20 | 12 | 3.3V | Environment |
| RGB LED | 13,19,21 | 3.3V | Output |
| Reed | 16 | 3.3V | Motion |
| PIR | 17 | 5V | Motion |
| Joystick btn | 18 | 5V | Analog |
| Hall | 20 | 3.3V | Motion |
| Sound | 22 | 5V | Sound |
| Buzzer | 23 | 5V | Output |
| Flame | 24 | 3.3V | Light & IR |
| Touch | 25 | 3.3V | Motion |
| Button | 26 | 3.3V | Motion |
| Tilt | 27 | 3.3V | Motion |

I2C sensors (BME280, TSL25911, LTR390, SGP40, ICM20948, ADS1115, SSD1306 OLED) share the I2C bus. ADC sensors (Sound Level, Light Level, Soil Moisture, Joystick X) use ADS1115 channels A0-A3.
