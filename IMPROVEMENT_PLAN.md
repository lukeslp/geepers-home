# Sensor Playground — Comprehensive Improvement Plan

> Synthesized from: CRITIC.md, multi-agent swarm analysis (design, UX, Flask architecture, data visualization, research), and second-opinion consultations (Codex/Grok).
>
> Author: Luke Steuber | Date: 2026-02-12

---

## Executive Summary

The dashboard has excellent bones: glanceable ambient sensors + conversational chat is the right paradigm for a Pi touchscreen. The dark theme is gorgeous. SSE streaming works reliably. But it's being held back by prototype decisions that need to harden into production: hardcoded sensor maps, no data persistence, missing touch feedback, and raw VOC numbers that don't translate to anything a human understands.

This plan prioritizes **6 major feature areas** with concrete implementation details, ordered by impact and dependency.

---

## 1. AQI Calculation & Air Quality Intelligence

### The Problem
The SGP40 returns raw resistance values (15000-35000) that mean nothing to a user. "25,432 VOC" is gibberish. The dashboard currently shows this raw number with a vague "good/fair/poor" label.

### What EPA AQI Actually Is
The EPA Air Quality Index (0-500 scale) is calculated from **pollutant-specific breakpoints**. The main pollutants are:
- **PM2.5** (particulate matter ≤2.5μm) — the most health-relevant for indoor air
- **PM10** (particulate matter ≤10μm)
- **O3** (ozone)
- **CO** (carbon monoxide)
- **SO2** (sulfur dioxide)
- **NO2** (nitrogen dioxide)

**The SGP40 cannot produce EPA AQI.** It measures VOCs (volatile organic compounds), which are *not* one of the six EPA criteria pollutants. The SGP40's raw resistance correlates with VOC concentration but cannot be converted to PM2.5 or any AQI pollutant directly.

### Recommended Approach

#### Phase 1: VOC Index (No New Hardware) — 2-3 hours
Use Sensirion's official **VOC Index Algorithm** to convert raw SGP40 values to a 0-500 VOC Index:
- 0-100: Excellent
- 100-200: Good
- 200-300: Moderate
- 300-400: Unhealthy
- 400-500: Hazardous

```python
# sensors/sgp40.py — add VOC Index calculation
# pip install sensirion-gas-index-algorithm
from sensirion_gas_index_algorithm import VocAlgorithm

class SGP40Sensor(BaseSensor):
    def _init_hardware(self):
        # ... existing init ...
        self._voc_algorithm = VocAlgorithm()

    def _read_hardware(self):
        raw = self._sensor.raw
        voc_index = self._voc_algorithm.process(raw)
        return {
            'voc_raw': raw,
            'voc_index': voc_index,  # 0-500 scale
            'quality': self._classify_voc(voc_index),
        }

    def _classify_voc(self, index):
        if index <= 100: return 'excellent'
        if index <= 200: return 'good'
        if index <= 300: return 'moderate'
        if index <= 400: return 'unhealthy'
        return 'hazardous'
```

Update the frontend to display VOC Index instead of raw value, with a color-coded gauge.

#### Phase 2: Real AQI via PM2.5 Sensor — Hardware Purchase Required
Add a **PMS5003** or **PMSA003I** particulate matter sensor ($15-25):
- PMSA003I (I2C) is plug-and-play with existing I2C bus
- Measures PM1.0, PM2.5, PM10 simultaneously
- Enables real EPA AQI calculation using PM2.5 breakpoints

```python
# EPA AQI breakpoints for PM2.5 (μg/m³, 24-hour average)
PM25_BREAKPOINTS = [
    (0.0,   12.0,    0,  50),   # Good
    (12.1,  35.4,   51, 100),   # Moderate
    (35.5,  55.4,  101, 150),   # Unhealthy for Sensitive Groups
    (55.5, 150.4,  151, 200),   # Unhealthy
    (150.5, 250.4, 201, 300),   # Very Unhealthy
    (250.5, 500.4, 301, 500),   # Hazardous
]

def calculate_aqi(pm25):
    """Convert PM2.5 concentration to EPA AQI."""
    for c_lo, c_hi, i_lo, i_hi in PM25_BREAKPOINTS:
        if c_lo <= pm25 <= c_hi:
            return round((i_hi - i_lo) / (c_hi - c_lo) * (pm25 - c_lo) + i_lo)
    return 500  # Above scale
```

#### Phase 3: Combined Air Quality Dashboard Card
Show a composite view:
- **AQI gauge** (0-500, color-coded arc) from PM2.5
- **VOC Index** as secondary indicator
- **Indoor vs Outdoor comparison** (pull outdoor AQI from EPA AirNow API or OpenAQ)
- **24-hour trend sparkline**

### Hardware Recommendation
**PMSA003I** (Adafruit #4632, ~$20) — I2C interface, no UART needed, integrates with existing I2C bus. Adafruit has CircuitPython library ready to go.

---

## 2. Historical Data & Trend Visualization

### The Problem
Currently, sensor history is only kept in JavaScript memory (last 20 readings). Page refresh loses everything. No way to see trends over hours, days, or weeks.

### Architecture

#### Backend: SQLite Time-Series Store — 3-4 hours

```python
# core/data_store.py — lightweight time-series storage
import sqlite3
import time
from collections import defaultdict

class DataStore:
    """SQLite-backed sensor data store with automatic downsampling."""

    def __init__(self, db_path="sensor_data.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS readings (
                timestamp REAL NOT NULL,
                sensor TEXT NOT NULL,
                field TEXT NOT NULL,
                value REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_readings_time
                ON readings(sensor, field, timestamp);

            CREATE TABLE IF NOT EXISTS hourly_avg (
                hour INTEGER NOT NULL,
                sensor TEXT NOT NULL,
                field TEXT NOT NULL,
                avg_value REAL,
                min_value REAL,
                max_value REAL,
                count INTEGER,
                PRIMARY KEY (hour, sensor, field)
            );
        """)

    def record(self, sensor, field, value):
        """Store a reading. Called from event bus subscriber."""
        self.conn.execute(
            "INSERT INTO readings VALUES (?, ?, ?, ?)",
            (time.time(), sensor, field, value)
        )
        # Commit every ~10 seconds (batched in practice)

    def get_history(self, sensor, field, hours=24, resolution='auto'):
        """Get historical data. Auto-picks resolution based on time range."""
        cutoff = time.time() - (hours * 3600)

        if hours <= 1:
            # Raw data for last hour
            return self._raw_query(sensor, field, cutoff)
        elif hours <= 24:
            # 5-minute averages
            return self._averaged_query(sensor, field, cutoff, 300)
        else:
            # Hourly averages
            return self._hourly_query(sensor, field, cutoff)

    def cleanup(self, max_days=30):
        """Delete raw readings older than max_days. Keep hourly_avg forever."""
        cutoff = time.time() - (max_days * 86400)
        self.conn.execute("DELETE FROM readings WHERE timestamp < ?", (cutoff,))
        self.conn.commit()
```

#### Frontend: Sparklines & Mini-Charts — 4-5 hours

For the 800x480 screen, full Chart.js or D3.js is overkill. Use **inline SVG sparklines**:

```javascript
// Sparkline rendered as inline SVG in sensor cards
function renderSparkline(container, data, color) {
    const w = container.clientWidth;
    const h = 32;  // Fixed height for card footer
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;

    const points = data.map((v, i) => {
        const x = (i / (data.length - 1)) * w;
        const y = h - ((v - min) / range) * (h - 4) - 2;
        return `${x},${y}`;
    }).join(' ');

    container.innerHTML = `
        <svg width="${w}" height="${h}" class="sparkline">
            <polyline points="${points}" fill="none"
                      stroke="${color}" stroke-width="1.5"
                      stroke-linecap="round" stroke-linejoin="round"/>
        </svg>`;
}
```

**New API endpoints:**
- `GET /api/history/<field>?hours=24` — Returns time-series data
- `GET /api/history/summary` — Returns 24h min/max/avg for all sensors

**Detail view on card tap (long-press):**
- Full-width chart overlay (480px wide, 200px tall)
- Time range selector: 1h / 6h / 24h / 7d
- Min/max/avg annotations
- Dismiss on tap outside

#### Retention Policy
- Raw readings: keep 7 days (~1.5MB/day at 6 sensors × 1 reading/5s)
- 5-minute averages: keep 90 days
- Hourly averages: keep forever
- Auto-cleanup via daily cron or background thread

---

## 3. Voice Assistant (Hardware Pending)

### Pi 3B+ Constraints
- 1GB RAM, ARM Cortex-A53 @ 1.4GHz
- No neural accelerator
- Can't run Whisper, Vosk, or Piper TTS locally with acceptable latency

### Recommended Architecture: Local Wake Word + Cloud Everything Else

```
[Microphone] → [Porcupine Wake Word] → [WebSocket to VPS]
                    (local, ~3% CPU)         ↓
                                        [Whisper STT]
                                             ↓
                                        [Claude Chat]
                                             ↓
                                        [Piper TTS]
                                             ↓
                                    [Audio stream back to Pi]
                                             ↓
                                        [Speaker output]
```

#### Phase 1: Wake Word Detection — 2 hours
- **Picovoice Porcupine** (free tier: 3 custom wake words)
- Runs on Pi 3B+ at 2-3% CPU
- Custom wake word: "Hey Station" or "Hey Home"
- When triggered: play a chime, start recording

#### Phase 2: VPS Audio Pipeline — 4-6 hours
Create a new endpoint on the VPS (`/v1/voice/process`):

```python
@app.route('/v1/voice/process', methods=['POST'])
def voice_process():
    """Accept audio, return text response + TTS audio."""
    audio_bytes = request.data  # Raw PCM or WebM

    # 1. Speech-to-Text (Whisper via OpenAI API or local Whisper)
    text = whisper_transcribe(audio_bytes)

    # 2. Chat with sensor context (reuse existing chat logic)
    response = chat_with_context(text, sensor_data)

    # 3. Text-to-Speech (Piper or ElevenLabs)
    audio_out = tts_synthesize(response)

    return Response(audio_out, mimetype='audio/wav')
```

#### Phase 3: Pi Client — 3-4 hours
```python
# voice/pi_client.py
class VoiceClient:
    def __init__(self):
        self.porcupine = pvporcupine.create(keywords=["hey station"])
        self.pa = pyaudio.PyAudio()

    def listen_loop(self):
        while True:
            # Wake word detection (always running, low CPU)
            if self.detect_wake_word():
                self.play_chime()
                audio = self.record_until_silence(max_seconds=10)
                response_audio = self.send_to_vps(audio)
                self.play_audio(response_audio)
```

#### Hardware Needed
- USB microphone (ReSpeaker USB Mic Array ~$8, or any USB mic)
- 8Ω speaker (already have 2 with JST connectors)
- 3.5mm audio or I2S DAC for speaker output

#### Alternative: Web Speech API (Zero Hardware Cost)
If the Pi runs Chromium in kiosk mode, the **Web Speech API** provides:
- `SpeechRecognition` — Browser-native STT (sends to Google)
- `SpeechSynthesis` — Browser-native TTS (offline on some engines)
- No microphone/speaker wiring needed if using the touchscreen's built-in mic/speaker
- Downside: requires internet, less customizable, Google dependency

---

## 4. Weather & Microclimate Visualization

### Current State
Open-Meteo weather data is fetched but displayed as raw JSON in a basic card.

### Improvements

#### Enhanced Weather Card — 2-3 hours
- **Indoor vs Outdoor** comparison (side-by-side temp/humidity)
- **Forecast strip**: Next 12 hours as small icons (☀️🌤️🌧️)
- **Feels-like temperature** calculated from temp + humidity + wind
- **Sunrise/sunset** times with visual indicator

#### Weather Map Integration — 3-4 hours
Options (no API key required):
1. **Open-Meteo Maps** — Free, embeddable weather radar
2. **Windy.com embed** — Beautiful animated weather maps
3. **RainViewer API** — Free radar overlay tiles

For the 800x480 screen, embed a small radar map (320x240) showing precipitation in the area. Refresh every 10 minutes.

```python
# sources/weather_source.py — enhanced weather data
class WeatherSource(DataSource):
    def fetch(self):
        # Open-Meteo with hourly forecast + daily summary
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={self.lat}&longitude={self.lon}"
            f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
            f"weather_code,wind_speed_10m,pressure_msl"
            f"&hourly=temperature_2m,weather_code"
            f"&daily=sunrise,sunset,uv_index_max"
            f"&timezone=auto&forecast_days=1"
        )
        data = requests.get(url).json()
        return {
            'current': data['current'],
            'hourly': data['hourly'],
            'daily': data['daily'],
        }
```

#### Microclimate Comparison
Show how your indoor readings diverge from outdoor:
- Temperature differential (indoor - outdoor)
- Humidity differential
- "Your air quality is X times better/worse than outdoor" (when PM2.5 sensor added)

---

## 5. Smart Alerts & Automation Triggers

### Alert System — 3-4 hours

```python
# core/alerts.py
class AlertManager:
    """Threshold-based alerts with cooldown to prevent spam."""

    def __init__(self, bus, config):
        self.bus = bus
        self.alerts = []
        self.cooldowns = {}  # {alert_id: last_triggered_time}

    def check(self, field, value):
        for alert in self.alerts:
            if alert['field'] != field:
                continue
            if self._evaluate(alert, value) and self._can_trigger(alert):
                self._trigger(alert, field, value)

    def _trigger(self, alert, field, value):
        self.bus.publish('alerts', {
            'level': alert['level'],  # info, warn, critical
            'message': alert['message'].format(value=value, field=field),
            'field': field,
            'value': value,
            'timestamp': time.time(),
        })
        self.cooldowns[alert['id']] = time.time()
```

#### Default Alert Rules (configurable in YAML):
```yaml
alerts:
  - id: temp_high
    field: temperature
    condition: "> 30"
    level: warn
    message: "Temperature is {value}°C — consider opening a window"
    cooldown: 600  # Don't repeat for 10 minutes

  - id: humidity_low
    field: humidity
    condition: "< 25"
    level: info
    message: "Humidity dropped to {value}% — dry air can irritate skin"
    cooldown: 1800

  - id: voc_spike
    field: voc_index
    condition: "> 300"
    level: critical
    message: "Air quality degraded (VOC Index {value}) — ventilate the room"
    cooldown: 300

  - id: uv_high
    field: uvi
    condition: "> 6"
    level: warn
    message: "UV Index is {value} — apply sunscreen if going outside"
    cooldown: 3600
```

#### Frontend Alert Display
- Toast notifications (slide in from top, auto-dismiss after 8s)
- Alert history panel (swipe up from bottom)
- Alert badge on mode toggle button

### MQTT / Home Assistant Integration — 4-6 hours
For users with smart home setups:

```python
# integrations/mqtt_publisher.py
import paho.mqtt.client as mqtt

class MQTTPublisher:
    """Publish sensor data to MQTT for Home Assistant / Node-RED."""

    def __init__(self, bus, broker="localhost", topic_prefix="homestation"):
        self.client = mqtt.Client()
        self.client.connect(broker)
        self.prefix = topic_prefix

        # Subscribe to all sensor events
        bus.subscribe("sensor.*", self._on_sensor)

    def _on_sensor(self, topic, data):
        for field, value in data.items():
            if isinstance(value, (int, float)):
                mqtt_topic = f"{self.prefix}/{field}"
                self.client.publish(mqtt_topic, str(value), retain=True)

    def publish_discovery(self):
        """Publish Home Assistant MQTT discovery messages."""
        sensors = {
            'temperature': {'unit': '°C', 'device_class': 'temperature'},
            'humidity': {'unit': '%', 'device_class': 'humidity'},
            'pressure': {'unit': 'hPa', 'device_class': 'pressure'},
            'voc_index': {'unit': '', 'device_class': 'aqi'},
            'lux': {'unit': 'lx', 'device_class': 'illuminance'},
            'uvi': {'unit': 'UV', 'icon': 'mdi:weather-sunny-alert'},
        }
        for field, meta in sensors.items():
            config = {
                'name': f"Home Station {field.replace('_', ' ').title()}",
                'state_topic': f"{self.prefix}/{field}",
                'unit_of_measurement': meta['unit'],
                'device_class': meta.get('device_class'),
                'unique_id': f"homestation_{field}",
                'device': {
                    'identifiers': ['homestation_pi'],
                    'name': 'Home Station',
                    'model': 'Raspberry Pi 3B+',
                    'manufacturer': 'Luke Steuber',
                },
            }
            topic = f"homeassistant/sensor/homestation_{field}/config"
            self.client.publish(topic, json.dumps(config), retain=True)
```

---

## 6. UX Polish for 800x480 Touchscreen

These are the high-priority fixes from CRITIC.md, ordered by impact.

### 6a. Dynamic Sensor Config (Kill SENSOR_MAP) — 2-3 hours
**The #1 architectural fix.** Add `/api/config` endpoint that returns sensor metadata, units, formatting, and thresholds from `dashboard.yaml`. Frontend builds cards dynamically.

```python
# web_app.py — new endpoint
@app.route("/api/config")
def get_config():
    """Return sensor metadata for frontend card generation."""
    with open("dashboard.yaml") as f:
        config = yaml.safe_load(f)
    # Extract card definitions with display metadata
    cards = []
    for page in config.get("pages", []):
        for card in page.get("cards", []):
            cards.append(card)
    return jsonify({"cards": cards, "pages": [p["name"] for p in config["pages"]]})
```

Then refactor `app.js` to fetch this on load and build `SENSOR_MAP` from it.

### 6b. Touch Feedback — 30 minutes
- Add haptic-style visual feedback: card scales to 0.95 on press, stays compressed until chat response starts
- Add "Asking about temperature..." notification between tap and response
- Increase all touch targets to 44px minimum (iOS standard)

### 6c. Loading States — 30 minutes
- Skeleton loader on initial page render
- Fetch `/api/sensors` snapshot on load, populate cards immediately
- Fade-in animation once first SSE event arrives

### 6d. Chat Persistence — 1 hour
- Save last 20 messages to `localStorage`
- Restore on page load
- "Clear history" button in chat header

### 6e. Improved Converse Mode Layout — 1-2 hours
Instead of cramming all 6 sensors into tiny unreadable cards:
- Show only 3 key sensors (temp, humidity, air quality) in a single row
- Each gets more space, remains readable
- Other sensors accessible via "More sensors" expandable row

### 6f. Better Mode Toggle — 30 minutes
- Replace hamburger icon with semantic icons: grid icon (ambient) / chat bubble (converse)
- Label: "Chat" when in ambient, "Sensors" when in converse
- Animate icon transition

### 6g. Data Freshness Indicator — 30 minutes
- Show "6 active • 2s ago" instead of just "6 sensors"
- Stale data (>30s) shows yellow warning
- Dead connection shows red with retry countdown

---

## 7. Creative Feature Ideas

### Comfort Score — 1-2 hours
Composite "comfort index" (0-100) calculated from:
- Temperature (ideal: 20-24°C)
- Humidity (ideal: 40-60%)
- Air quality (VOC Index < 150)
- Light level (context-dependent: bright during day, dim at night)

Display as a large circular gauge on the main ambient view. The chat assistant can explain why the score is what it is.

### Day/Night Auto-Theme — 30 minutes
Use sunrise/sunset data from Open-Meteo to:
- Dim the screen brightness at night (via `/sys/class/backlight/`)
- Shift color temperature (warmer amber tones at night)
- Reduce SSE update frequency at night (save power)

### Environmental Timelapse — 2-3 hours
Record hourly webcam snapshots + sensor data. Generate a daily timelapse showing how the room changes throughout the day with overlaid sensor data.

### Air Quality Forecast — 1 hour
Use VOC Index trend + window open/close events to predict:
- "Air quality will degrade in ~2 hours if window stays closed"
- "Temperature will reach uncomfortable levels by 3 PM"

### Plant Care Mode — 2-3 hours
If soil moisture sensor is connected:
- Track watering schedule
- Alert when soil is too dry
- Light level recommendations per plant type
- Temperature suitability for common houseplants

---

## Implementation Priority

| Priority | Feature | Effort | Dependencies |
|----------|---------|--------|--------------|
| **P0** | VOC Index Algorithm (replace raw values) | 2h | `sensirion-gas-index-algorithm` pip package |
| **P0** | `/api/config` endpoint (kill SENSOR_MAP) | 3h | None |
| **P0** | Touch feedback + loading states | 1h | None |
| **P1** | SQLite data store + sparklines | 6h | None |
| **P1** | Chat persistence (localStorage) | 1h | None |
| **P1** | Alert system (YAML-configurable) | 4h | None |
| **P1** | Enhanced weather card (indoor vs outdoor) | 3h | None |
| **P2** | PM2.5 sensor (PMSA003I) + real AQI | 4h | Hardware purchase (~$20) |
| **P2** | Comfort Score composite gauge | 2h | P0 VOC Index |
| **P2** | Voice assistant (wake word + VPS pipeline) | 10h | Hardware (mic + speaker) |
| **P2** | MQTT / Home Assistant integration | 5h | MQTT broker (mosquitto) |
| **P3** | Improved converse mode layout | 2h | P0 /api/config |
| **P3** | Day/night auto-theme | 1h | Weather source sunrise data |
| **P3** | Environmental timelapse | 3h | Data store (P1) |
| **P3** | Plant care mode | 3h | Soil moisture sensor wiring |

**Estimated total: ~50 hours for everything, ~12 hours for P0+P1 core improvements.**

---

## Hardware Shopping List

| Item | Price | Purpose | Priority |
|------|-------|---------|----------|
| PMSA003I (PM2.5 sensor) | ~$20 | Real EPA AQI calculation | P2 |
| USB Microphone | ~$8-15 | Voice assistant input | P2 |
| I2S DAC (MAX98357A) | ~$6 | Speaker output | P2 |
| JST-to-speaker adapter | ~$2 | Connect existing speakers | P2 |

**Total hardware budget: ~$35-45**

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│                    Pi 3B+ (Local)                    │
│                                                     │
│  ┌──────────┐   ┌───────────┐   ┌───────────────┐  │
│  │ Sensors  │──▶│ EventBus  │──▶│ SQLite Store  │  │
│  │ (I2C/GPIO)│   │ (WebEventBus)│   │ (time-series) │  │
│  └──────────┘   └─────┬─────┘   └───────────────┘  │
│                       │                              │
│  ┌──────────┐   ┌─────▼─────┐   ┌───────────────┐  │
│  │ Camera   │──▶│ Flask App │──▶│ SSE Stream    │──┼──▶ Browser
│  │ (USB)    │   │ (web_app) │   │ + REST API    │  │   (800x480)
│  └──────────┘   └─────┬─────┘   └───────────────┘  │
│                       │                              │
│  ┌──────────┐   ┌─────▼─────┐                       │
│  │ Porcupine│──▶│ Alert Mgr │──▶ Toasts / MQTT     │
│  │ Wake Word│   └───────────┘                       │
│  └──────────┘                                       │
│                       │                              │
└───────────────────────┼──────────────────────────────┘
                        │ HTTPS
                ┌───────▼──────────┐
                │   VPS (dr.eamer) │
                │                  │
                │  API Gateway     │
                │  ├─ /v1/llm/chat │
                │  ├─ /v1/voice/*  │
                │  └─ Anthropic    │
                └──────────────────┘
```

---

*This plan is designed to be implemented incrementally. Each item is self-contained. Start with P0 items (VOC Index + /api/config + touch feedback) for the biggest bang in the least time.*
