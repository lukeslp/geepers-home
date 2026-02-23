# Architecture Diagrams & Visual Reference

Comprehensive visual guide to the home assistant platform architecture.

---

## 1. SYSTEM CONTEXT DIAGRAM

```
┌─────────────────────────────────────────────────────────────────┐
│                         INTERNET (WiFi)                        │
└────────────────┬────────────────────────────────────┬──────────┘
                 │                                    │
         SSH Reverse Tunnel                    External APIs
          (port 2222)                    (Whisper, ElevenLabs)
                 │                                    │
       ┌─────────▼──────────┐          ┌─────────────▼───────────┐
       │                    │          │                         │
       │   RASPBERRY PI     │          │   VPS (dr.eamer.dev)    │
       │    (1GB RAM)       │          │                         │
       │                    │          │ • LLM (Grok, Claude)    │
       │ • Wake Word        │─────────►│ • STT (Whisper)         │
       │ • Audio I/O        │  HTTPS   │ • TTS (ElevenLabs)      │
       │ • Sensor Polling   │◄─────────│ • Data Analytics        │
       │ • tkinter GUI      │WebSocket │ • Model Storage         │
       │ • GPIO Control     │          │                         │
       │                    │          │                         │
       └────────────────────┘          └─────────────────────────┘
              │                                    ▲
              │ (GPIO)                             │ (REST API)
              │ 23 sensors                         │ /assist/audio
              │ RGB LED, buzzer                    │ /sensor/analyze
              │                                    │ /tts/generate
              ▼
       ┌──────────────────────┐
       │   Peripheral Sensors │
       ├──────────────────────┤
       │ • DHT11, DS18B20     │
       │ • PIR, Reed, Hall    │
       │ • Sound, Light, SGP40│
       │ • ADS1115 ADC        │
       └──────────────────────┘
```

---

## 2. COMPONENT INTERACTION DIAGRAM

```
RASPBERRY PI THREAD MODEL:
┌──────────────────────────────────────────────────────────────┐
│                      tkinter Main Loop                       │
│  (Blocking, GUI refresh, sensor polling via root.after)      │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │ GUI Render  │  │ Sensor Read  │  │ Status Display     │ │
│  │ (50ms)      │  │ (every Xs)   │  │ (update every 100ms)
│  │             │  │              │  │                    │ │
│  └─────────────┘  └──────────────┘  └────────────────────┘ │
│                                                              │
└──────────────────────┬───────────────────────────────────────┘
                       ▲
                       │ (thread-safe queue)
                       │ state updates
                       ▼
┌──────────────────────────────────────────────────────────────┐
│               Voice Assistant Thread (Daemon)                │
│         (Independent, does not block GUI)                    │
│                                                              │
│  ┌──────────────┐      ┌───────────────┐                    │
│  │ Wake Word    │      │ Command       │                    │
│  │ Detector     │─────►│ Processing    │                    │
│  │              │      │               │                    │
│  │ (constantly) │      │ (on trigger)   │                    │
│  │ CPU: <2%     │      │ CPU: 20%+     │                    │
│  └──────────────┘      └──────┬────────┘                    │
│                                 │                            │
│                    ┌────────────┼────────────┐               │
│                    │            │            │               │
│              ┌─────▼───┐  ┌─────▼──┐  ┌─────▼──┐            │
│              │ STT     │  │ LLM    │  │ TTS    │            │
│              │ Request │  │ Query  │  │ Gen    │            │
│              │         │  │        │  │        │            │
│              │(VPS)    │  │(VPS)   │  │(VPS)   │            │
│              └─────────┘  └────────┘  └────────┘            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
                       ▲                    ▼
        ┌──────────────┴─────────────────┬──────┐
        │                                │      │
    [GPIO Write]                    [Audio Out]
   (LED, Buzzer)                    (Speaker)
```

---

## 3. DATA FLOW DIAGRAM - Voice Command Pipeline

```
PHASE 1: WAKE WORD DETECTION
┌─────────────┐
│  Microphone │
│   (16kHz)   │
└──────┬──────┘
       │ raw audio (chunks)
       ▼
┌─────────────────────┐
│  AudioBuffer        │
│  (Ring Buffer)      │
│  2s window          │
└──────┬──────────────┘
       │ 512-sample chunks
       ▼
┌──────────────────────────┐    Confidence
│  Porcupine Lite          │    > 0.5?
│  Wake Word Detector      │───────┐
│  (Local, offline)        │       │
│  CPU: 1-3%               │       ▼
│  Latency: ~50ms          │   [DETECTED]
└──────────────────────────┘
                                    ▼
                            ┌─────────────────┐
                            │  GUI Indicator  │
                            │  "🎤 Listening" │
                            └─────────────────┘

PHASE 2: COMMAND AUDIO COLLECTION
[LISTENING STATE: 2-10 seconds]
┌──────────────────┐
│ Audio from Mic   │
│ "What's the      │
│  temperature?"   │
│ (48kB @ 16kHz)   │
└────────┬─────────┘
         │
         ▼
┌─────────────────────┐
│ Silence Detector    │
│ (RMS threshold)     │
│ When quiet for 2s   │
│ → end of command    │
└────────┬────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│ Command Audio Complete (48-100kB)        │
│ Format: PCM 16-bit, 16kHz, mono          │
│ Stored in RAM (temporary)                │
└────────┬─────────────────────────────────┘
         │
         ▼
    [To Phase 3]

PHASE 3: VPS PROCESSING
┌────────────────────────────────────────────┐
│ Pi RPC Client                              │
│ POST /assist/audio                         │
│ + sensor_context (JSON)                    │
└────────────┬─────────────────────────────┘
             │
             │ HTTPS POST (5KB/s = 2-3s transfer)
             │
             ▼
┌────────────────────────────────────────────┐
│ VPS Audio Receiver                         │
│ • Validate format                          │
│ • Store temp file                          │
│ • Queue for STT                            │
└────────────┬─────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────┐
│ STT Processor (Whisper API)                │
│ Audio → Text                               │
│ Latency: 500-2000ms (depends on duration)  │
└────────────┬─────────────────────────────┘
             │
             ├─► "What's the temperature?"
             │
             ▼
┌─────────────────────────────────────────────────────┐
│ LLM Handler                                         │
│                                                     │
│ Input:                                              │
│  - Transcription                                    │
│  - Sensor Context {dht11: {temp: 22.5, hum: 45}}   │
│  - Intent: "query_sensor"                           │
│                                                     │
│ Prompt:                                             │
│ """                                                 │
│ User asked: "What's the temperature?"               │
│ Current home sensors:                               │
│ - Temperature: 22.5°C                               │
│ - Humidity: 45%                                     │
│                                                     │
│ Generate a natural spoken response.                 │
│ """                                                 │
│                                                     │
│ Model: Grok (xAI, fast responses)                   │
│ Latency: 200-800ms                                  │
└────────────┬─────────────────────────────────────┘
             │
             ├─► "Your home is currently 22.5 degrees Celsius
             │    with 45 percent humidity. That's a
             │    comfortable temperature."
             │
             ▼
┌─────────────────────────────────────────────────────┐
│ TTS Processor (ElevenLabs)                          │
│ Text → Audio                                        │
│ Voice: "Aria" (natural, conversational)             │
│ Latency: 1000-3000ms                                │
│ Output: MP3 or WAV (15-30KB)                        │
└────────────┬─────────────────────────────────────┘
             │
             │ HTTPS Stream (small file, <1s transfer)
             │
             ▼
┌────────────────────────────────────────────┐
│ Pi RPC Client                              │
│ Receives TTS audio stream                  │
│ Buffers in memory (streaming, not full DL) │
└────────────┬─────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────┐
│ Audio Output Manager                       │
│ • Decode MP3/WAV → PCM                     │
│ • Open speaker stream                      │
│ • Write to sounddevice                     │
│ Latency: 200-500ms (buffering + playback)  │
└────────────┬─────────────────────────────┘
             │
             ▼
         [SPEAKER]
     "Your home is currently..."

TOTAL LATENCY: 8-12 seconds
 └─ Listening: 2-5s (user speaking)
 └─ Network: 2-3s (upload)
 └─ STT: 0.5-2s
 └─ LLM: 0.2-0.8s
 └─ TTS: 1-3s
 └─ Network: 0.1s (download)
 └─ Playback: 2-4s (audio duration)

ACCEPTABLE LATENCY for home assistant
(Google Assistant: 2-4s, Alexa: 3-5s, Siri: 2-6s)
```

---

## 4. MEMORY ALLOCATION DIAGRAM

```
RASPBERRY PI 1GB TOTAL MEMORY

┌────────────────────────────────────────────────────┐
│                   1024 MB (100%)                   │
│                                                    │
│ ┌──────────────────────────────────────────────┐  │
│ │ OS Kernel + System Services         300 MB   │  │
│ │ • init, systemd, NetworkManager             │  │
│ │ • Kernel buffers, filesystem cache          │  │
│ └──────────────────────────────────────────────┘  │
│                                                    │
│ ┌──────────────────────────────────────────────┐  │
│ │ Python Runtime                      50 MB   │  │
│ │ • Python interpreter                        │  │
│ │ • Standard library                          │  │
│ └──────────────────────────────────────────────┘  │
│                                                    │
│ ┌──────────────────────────────────────────────┐  │
│ │ tkinter GUI (SensorPlayground)     80 MB    │  │
│ │ • Image buffers (800×480)                   │  │
│ │ • Widget state + font cache                 │  │
│ │ • Sensor history (200 points × 23 sensors)  │  │
│ └──────────────────────────────────────────────┘  │
│                                                    │
│ ┌──────────────────────────────────────────────┐  │
│ │ Sensor Polling Loop              40 MB     │  │
│ │ • GPIO/I2C drivers loaded                   │  │
│ │ • ADC manager state                         │  │
│ │ • DHT11, DS18B20 libraries                  │  │
│ └──────────────────────────────────────────────┘  │
│                                                    │
│ ┌──────────────────────────────────────────────┐  │
│ │ Voice Assistant (NEW)            70 MB     │  │
│ │ ┌────────────────────────────────────────┐  │  │
│ │ │ Porcupine Lite (wake word)   40 MB    │  │  │
│ │ │ • Pre-trained model loaded at startup  │  │  │
│ │ │ • Shared between chunks                │  │  │
│ │ └────────────────────────────────────────┘  │  │
│ │                                              │  │
│ │ ┌────────────────────────────────────────┐  │  │
│ │ │ AudioManager & Buffers       20 MB     │  │  │
│ │ │ • Input stream (sounddevice)           │  │  │
│ │ │ • Output stream                        │  │  │
│ │ │ • Ring buffer (2s @ 16kHz): 64KB      │  │  │
│ │ │ • Temporary audio chunks               │  │  │
│ │ └────────────────────────────────────────┘  │  │
│ │                                              │  │
│ │ ┌────────────────────────────────────────┐  │  │
│ │ │ HomeAssistant State & RPC    10 MB    │  │  │
│ │ │ • State machine, session data          │  │  │
│ │ │ • WebSocket connection info            │  │  │
│ │ └────────────────────────────────────────┘  │  │
│ └──────────────────────────────────────────────┘  │
│                                                    │
│ ┌──────────────────────────────────────────────┐  │
│ │ Available Headroom              384 MB     │  │
│ │ • Spike buffer (TTS audio cache)           │  │
│ │ • Thread stack space                       │  │
│ │ • Emergency reserves                       │  │
│ └──────────────────────────────────────────────┘  │
│                                                    │
└────────────────────────────────────────────────────┘

Legend:
✓ Safe zone (allocated + 50% headroom)
⚠ Warning zone (80%+ utilization)
✗ Critical zone (>95%, swap thrashing)

Current state: ~615MB used, 384MB free ✓ SAFE
Worst-case (TTS spike): ~650MB, 374MB free ✓ SAFE
```

---

## 5. NETWORK COMMUNICATION DIAGRAM

```
CONNECTIVITY MODEL:

Pi Network Interface:
┌─────────────────┐
│ WiFi Module     │
│ 2.4 GHz 802.11n │
│ ~100-500 kbps   │
│ (typical home)  │
└────────┬────────┘
         │
         │ WiFi signal
         │ (encrypted WPA2)
         │
         ▼
    [Home Router]
         │
         │ Internet
         │
         ▼
    [ISP Gateway]
         │
         ▼
    [Internet Cloud]
         │
         ▼
    [VPS dr.eamer.dev]

CONNECTION LAYERS:

Layer 1: SSH Tunnel (always-on)
┌─────────────────────────────────────────────┐
│ SSH Reverse Tunnel                          │
│ Pi initiates: ssh -R 2222:localhost:22 vps  │
│ Keeps persistent connection                 │
│ Detects dropouts via keepalive (60s)        │
│ Auto-reconnect on failure                   │
│ Encrypted: AES-256 + HMAC                   │
│ Authentication: SSH public key (~2KB)       │
│ Overhead: ~1KB per minute idle              │
└─────────────────────────────────────────────┘
         │
         ├──► /etc/systemd/system/ssh-tunnel.service
         │    └─ Managed by systemd watchdog
         │
         └──► Connection available on VPS localhost:2222

Layer 2: Audio Upload (on demand)
┌─────────────────────────────────────────────┐
│ HTTPS POST /assist/audio                    │
│ From: Pi RPC Client                         │
│ To: VPS (dr.eamer.dev:443)                  │
│ Body: multipart/form-data                   │
│   - file: audio.wav (binary)                │
│   - sensor_context: JSON                    │
│ Size: 24-96 kB (2-8 seconds @ 48kbps)      │
│ Transfer time: 200-2000ms                   │
│ Retry: 3x with exponential backoff          │
│ Timeout: 10s                                │
│ Encryption: TLS 1.3 + cert pinning          │
└─────────────────────────────────────────────┘

Layer 3: Response Download (streaming)
┌─────────────────────────────────────────────┐
│ HTTPS Stream /tts/generate                  │
│ From: VPS                                   │
│ To: Pi RPC Client                           │
│ Content-Type: audio/mp3                     │
│ Size: 16-32 kB (TTS duration)               │
│ Transfer time: 100-1000ms                   │
│ Streaming: piped directly to audio output   │
│           (no full download to disk)        │
│ Buffer: 4KB in-memory ring buffer           │
│ Encryption: TLS 1.3                         │
└─────────────────────────────────────────────┘

Layer 4: WebSocket (optional, future)
┌─────────────────────────────────────────────┐
│ WebSocket Connection (potential future)     │
│ From: Pi                                    │
│ To: VPS (via SSH tunnel localhost:2222)     │
│ Purpose: Real-time bi-directional updates   │
│ Frame size: <4KB per message                │
│ Latency: <100ms                             │
│ Heartbeat: 30s (keepalive)                  │
│ Encryption: WSS (WebSocket Secure)          │
└─────────────────────────────────────────────┘

BANDWIDTH REQUIREMENTS:

Idle (wake word listening):
  └─ ~1-2 KB/min (SSH tunnel keepalive)
  └─ Acceptable for background operation

Voice Command (typical):
  └─ Upload: 24 KB / 1s = 24 kbps, ~1 sec
  └─ Download: 20 KB / 4s = 5 kbps, ~1 sec
  └─ Total: ~30 seconds of bandwidth per 12-second command ✓
  └─ Can handle 2-3 commands before needing slower connection

High-Frequency Commands (10/min):
  └─ ~5 MB/hour peak
  └─ Still within typical home WiFi limits (>10 Mbps)

FAILURE MODES:

Network Dropout (>30s):
  └─ Pi: Wake word still works (local)
  └─ Pi: Voice commands queued locally
  └─ Pi: Attempt reconnection every 5s
  └─ GUI: Shows "VPS unreachable" (yellow indicator)
  └─ User: Can still use local sensors + GUI

Network Restored:
  └─ Pi: Automatic reconnection
  └─ Pi: Resume queued commands
  └─ GUI: Indicator returns to normal

Slow Network (<100 kbps):
  └─ Latency: 30-60 seconds (still usable)
  └─ Audio quality: Reduced (8kHz mono possible)
  └─ LLM: May use faster model (smaller, less capable)
```

---

## 6. STATE MACHINE DIAGRAM

```
HomeAssistant State Transitions:

                    ┌────────────────┐
                    │      IDLE      │
                    │ (VPS optional) │
                    │ CPU: <3%       │
                    └────────┬───────┘
                             │
                wake_word    │
                detected()   │
                             ▼
                    ┌────────────────────┐
                    │    LISTENING       │
                    │ (collecting audio) │
                    │ CPU: 2-5%          │
                    │ Duration: 2-10s    │
                    │                    │
                    │ [GUI: 🎤]          │
                    └───────┬────────────┘
                            │
        silence_detected()   │ (2s quiet)
        OR timeout (15s)     │
                            ▼
                    ┌──────────────────────┐
                    │    PROCESSING        │
                    │ (VPS: STT + LLM)     │
                    │ CPU: 30-50% (wait)   │
                    │ Duration: 0.5-3s     │
                    │                      │
                    │ [GUI: 🔄 Spinning]   │
                    └──────┬───────────────┘
                           │
        response_received()│
        OR timeout (10s)   │
                           ▼
                    ┌──────────────────────┐
                    │    RESPONDING        │
                    │ (TTS: generate+play) │
                    │ CPU: 10-20%          │
                    │ Duration: 2-5s       │
                    │                      │
                    │ [GUI: 🔊 Speaking]   │
                    └──────┬───────────────┘
                           │
        audio_finished()   │
        OR timeout (8s)    │
                           ▼
                    ┌────────────────┐
                    │      IDLE      │
                    │  (back to      │
                    │  listening)    │
                    └────────────────┘

ERROR RECOVERY PATHS:

Any state → Exception
           │
           ├─► Log error
           ├─► Speak error message: "Sorry, error occurred"
           ├─► GUI error indicator (red X)
           │
           └─► Wait 2s → back to IDLE


VPS Timeout Handling:

PROCESSING (waiting for VPS)
    │
    ├─ [5s] No response
    │   └─► Retry (exponential backoff)
    │
    ├─ [10s] Still no response
    │   └─► Assume VPS down
    │   └─► Use local fallback: "Processing locally..."
    │
    ├─ [15s] Give up
        └─► RESPOND with: "VPS connection failed.
                          Voice is temporarily unavailable.
                          Try again in a moment."
        └─► back to IDLE


Interrupt Handling (user cancellation):

LISTENING
    │
    └─► User presses GUI "Cancel" button
        │
        ├─► Clear audio buffer
        ├─► State → IDLE immediately
        ├─► GUI: "Cancelled"
        │
        └─► Ready for next command


State Persistence:

Session Data (kept for 5 minutes):
  • Last command transcription
  • Sensor context at time of command
  • User preferences (volume, voice speed)
  • Conversation history (for future multi-turn)

Memory (not persisted):
  • Current audio buffer (cleared after processing)
  • Thread state (reinitialized on restart)
  • Temporary VPS response (discarded after TTS)
```

---

## 7. SENSOR DATA FLOW

```
SENSOR READING → VOICE CONTEXT → LLM INSIGHT

Existing System (unchanged):
┌─────────────────────────────┐
│ main.py (startup)           │
└────────┬────────────────────┘
         │ create sensors from config
         ▼
┌─────────────────────────────────┐
│ SensorPlayground GUI            │
│ (tkinter app)                   │
└────────┬─────────────────────┬──┘
         │                     │
    root.after() polling    Display on UI
    every X ms              & log to CSV
         │
         ▼
┌─────────────────────────────────┐
│ Sensor Classes (existing)       │
│ • DHT11: read() → {temp, hum}   │
│ • SGP40: read() → {voc}         │
│ • PIR: read() → {motion: True}  │
│ • ADS1115: read() → {value}     │
│ etc.                            │
└──────────┬──────────────────────┘
           │ returns dict
           ▼
    ┌──────────────────┐
    │ GUI Display      │
    │ (Labels + Graphs)│
    └──────────────────┘

NEW: Voice Context Integration
════════════════════════════════════

Voice Assistant (background thread)
    │
    ├─ On user command: "What's the temperature?"
    │
    └──► _gather_sensor_context()
         │
         ├─► Read current sensor values
         │   (via shared config or callback)
         │
         ├─► Timestamp each value
         │
         └──► Build JSON payload:
             {
               "dht11": {
                 "temperature": 22.5,
                 "humidity": 45.2,
                 "timestamp": 1707580123
               },
               "sgp40": {
                 "voc": 52,
                 "timestamp": 1707580122
               },
               "pir": {
                 "motion_detected": false
               }
             }
             │
             └──► Send to VPS with audio

VPS Side: Sensor Analysis
═════════════════════════════════════

Receives:
  • Transcription: "What's the temperature?"
  • Sensor context: {...}

LLM Prompt:
  """
  User asked: "What's the temperature?"

  Current sensor data:
  - Temperature: 22.5°C
  - Humidity: 45%
  - Air quality (VOC): 52

  Provide a natural, conversational response.
  """

LLM Response:
  "Your home temperature is 22.5 degrees Celsius.
   It's a comfortable temperature with moderate humidity
   at 45 percent. Air quality is good."

TTS Output:
  [audio bytes] → sent back to Pi → played on speaker


SENSOR TREND ANALYSIS (Optional Advanced Feature)
═════════════════════════════════════════════════

User asks: "Is air quality getting worse?"

Pi → VPS:
  {
    "sensor_id": "sgp40",
    "readings": [
      {ts: T, value: 48},
      {ts: T+10s, value: 50},
      {ts: T+20s, value: 52},
      ...  // 10 minutes history
    ],
    "time_window": "10m"
  }

VPS SensorAssistant:
  Calculates:
    • Slope: +0.4 units/min (upward trend)
    • Rate: +24 units/hour
    • Baseline: 40-45, Current: 52
    • Anomaly: +12 units above baseline

  Factors:
    • Time of day
    • Recent activity (cooking?)
    • Weather patterns
    • Historical patterns

  LLM Prompt:
    """
    Analyze this air quality trend:
    - Rising from 48 to 52 (10% increase)
    - Rate of change: +24 units/hour
    - Baseline: 40-45, Currently 15% above baseline

    What caused this? Should user be concerned?
    """

  Response:
    "Air quality has degraded by about 10% in the last
     10 minutes. This could be due to cooking, heating,
     or reduced ventilation. Consider opening a window
     or improving circulation."
```

---

## 8. DEPLOYMENT ARCHITECTURE

```
DEVELOPMENT → STAGING → PRODUCTION

┌─────────────────────────────────────────────────────┐
│             DEVELOPMENT (Laptop/Desktop)            │
├─────────────────────────────────────────────────────┤
│                                                     │
│ local venv + sensor-playground-mirror              │
│ ├── main.py --demo (GUI testing)                   │
│ ├── voice tests (mock VPS)                         │
│ └── unit tests (pytest)                            │
│                                                     │
│ Changes → git commit                               │
│                                                     │
└─────────────────────────────────────────────────────┘
                       ↓ (git push)

┌─────────────────────────────────────────────────────┐
│               STAGING (VPS: test environment)       │
├─────────────────────────────────────────────────────┤
│                                                     │
│ /home/coolhand/projects/sensor-playground-mirror   │
│ └── venv: test                                     │
│     ├── Flask API (port 5123, test)                │
│     └── Mock sensor data                           │
│                                                     │
│ Pi (real hardware, test WiFi):                     │
│ ├── Connect to test VPS endpoint                   │
│ ├── Run full integration tests                     │
│ └── Performance benchmarking                       │
│                                                     │
│ Changes verified → merge to main                   │
│                                                     │
└─────────────────────────────────────────────────────┘
                       ↓ (systemctl restart)

┌─────────────────────────────────────────────────────┐
│        PRODUCTION (VPS + Pi, Real Deployment)      │
├─────────────────────────────────────────────────────┤
│                                                     │
│ VPS (dr.eamer.dev)                                │
│ ├── /etc/systemd/system/sensor-playground.service │
│ │   └── python voice_api.py (port 5025)           │
│ │       └── Uses shared library (LLM, TTS, etc.)  │
│ │       └── SQLite: sensor history DB             │
│ │       └── Logging: /var/log/voice-api.log       │
│ │                                                  │
│ └── systemctl enable sensor-playground            │
│     └── Auto-restart on reboot                    │
│     └── Restart on crash (watchdog)               │
│                                                     │
│ Pi (sensor-playground-mirror)                      │
│ ├── /etc/systemd/system/sensor-playground.service │
│ │   └── python main.py (full app)                 │
│ │       └── GUI + Voice + Sensors                 │
│ │       └── Logging: syslog                       │
│ │                                                  │
│ └── /etc/systemd/system/ssh-tunnel.service        │
│     └── ssh -R 2222:localhost:22 vps              │
│     └── Restart on disconnect                     │
│     └── Credentials: ~/.ssh/id_rsa                │
│                                                     │
│ Monitoring:                                        │
│ ├── journalctl -u sensor-playground -f            │
│ ├── systemctl status sensor-playground            │
│ ├── curl http://localhost:5025/health             │
│ ├── ps aux | grep main.py                         │
│ └── free -h (memory usage)                        │
│                                                     │
│ Rollback Plan:                                     │
│ ├── Keep previous version tagged (git)            │
│ ├── systemctl stop sensor-playground              │
│ ├── git checkout <prev-tag>                       │
│ ├── systemctl start sensor-playground             │
│ └── Automatic restart (watchdog): 1 minute        │
│                                                     │
└─────────────────────────────────────────────────────┘


CONTINUOUS DEPLOYMENT:

git push to main
    │
    ├─► GitHub Actions / CI/CD
    │   ├─ Run tests (pytest)
    │   ├─ Type checking (mypy)
    │   ├─ Lint check (ruff)
    │   └─ Build check
    │
    └─► Manual approval required
        │
        └─► Deploy to VPS:
            ├─ ssh vps 'cd /home/coolhand/... && git pull'
            ├─ systemctl restart sensor-playground
            ├─ Monitor logs for 5 minutes
            ├─ Verify: curl /health endpoint
            └─ Alert on failure (email)
```

---

## 9. PERFORMANCE PROFILE

```
RESOURCE USAGE OVER TIME:

                CPU %
             ▲  80%  ┌──────────────┐
             │       │ TTS Gen      │
             │       │ (LLM call)   │
             │  60%  │              │
             │       │ ┌────────────┼─────────┐
             │       │ │STT         │ LLM     │
             │  40%  │ ├────────────┤ ├───────┤
             │  20%  │ │Sleep       │ │       │ ┌──────────┐
             │   5%  ├─┘ Wake word  └─┘       └─┤GUI update
             │  ──────────────────────────────────────────────────►
                    0  2  4  6  8 10 12 14 16 18 20 22 24 26 28 30 s

Timeline:
 0-2s: Waiting for wake word (CPU 1%)
 2-10s: User speaking (CPU 2-3%)
10-12s: Silence detected (CPU 1%)
12-14s: Audio upload to VPS (CPU 3%)
14-15s: STT processing (CPU 15-20%, waiting on network)
15-16s: LLM inference (CPU 25-40%, waiting on network)
16-17s: TTS generation (CPU 20-30%, waiting on network)
17-18s: Audio download + decode (CPU 5%)
18-24s: Playback on speaker (CPU <1%)
24+s: Back to IDLE

MEMORY % (1GB total)
             ▲  80%
             │
             │  60% ┌──────────────────────────────────────────┐
             │      │ Baseline: OS + GUI + Voice Assistant     │
             │  40% │                                          │
             │      │ ┌──────────────────────────────────────┐ │
             │  20% │ │ Peak: TTS buffer + audio streaming   │ │
             │   ─  ├─┘                                      └─┤
             │      │ Headroom: 380MB (safe)                  │
             │ ──────────────────────────────────────────────────────►
                    Idle  Wake  Listen Process  Respond Idle

NETWORK (kbps)

             ▲200kbps
             │
             │      Upload      Download
             │      audio       TTS audio
             │        │           │
             │        ▼           ▼
             │      ┌─┐       ┌──────┐
             │   ┌──┘ └───┐   │      │
             │  50│       └───┘      │
             │   │                  │
             │ ──────────────────────────────────► time
                0  5s 10s  15s 20s  25s

Peak: ~200 kbps during upload
Average: ~50 kbps
Idle: ~1 kbps (SSH keepalive)

LATENCY BREAKDOWN (typical 10s command):

Component          Latency   Contribution
─────────────────────────────────────────
Wake word detect   50ms      Instant
Listen (user)      2-5s      Variable
Upload audio       1-2s      Network-dependent
STT (Whisper)      500-1500ms Service-dependent
LLM (Grok)        200-800ms  Model inference
TTS (ElevenLabs)  1000-3000ms Voice quality
Download audio     100-500ms  Network
Playback           2-4s       Audio duration
─────────────────────────────────────────
Total             8-16s      Acceptable

Worst-case (slow network): 20-25s
Best-case (fast LLM):      6-8s
Typical (average):         10-12s ✓
```

---

## 10. DEPLOYMENT CHECKLIST DIAGRAM

```
PRE-DEPLOYMENT VERIFICATION:

┌─────────────────────────────────────────────────┐
│          Phase 1: Audio Hardware               │
├─────────────────────────────────────────────────┤
│ [ ] USB sound card connected                    │
│ [ ] Microphone device listed: arecord -l       │
│ [ ] Speaker device listed: aplay -l            │
│ [ ] Record test: arecord -f S16_LE -r 16000    │
│ [ ] Playback test: aplay test.wav              │
│ [ ] Levels OK (not clipping, not silent)       │
│ [ ] Microphone not picking up background noise │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│          Phase 2: Wake Word Engine             │
├─────────────────────────────────────────────────┤
│ [ ] Picovoice SDK installed: pip show pvporcup │
│ [ ] Access key obtained (free tier OK)         │
│ [ ] Porcupine model downloaded                 │
│ [ ] Test script runs without error             │
│ [ ] Wake word detected 9/10 times (accuracy)   │
│ [ ] False positives < 1/10 (noise rejection)   │
│ [ ] CPU usage < 5% during listening            │
│ [ ] Memory stable (no leaks)                    │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│          Phase 3: Network & SSH Tunnel        │
├─────────────────────────────────────────────────┤
│ [ ] SSH key pair generated: ssh-keygen -t ed25519
│ [ ] Public key on VPS: ~/.ssh/authorized_keys  │
│ [ ] SSH tunnel connects: ssh -R 2222:... vps   │
│ [ ] Tunnel stays connected after 10 minutes    │
│ [ ] Reverse connection works: ssh pi@localhost:2222
│ [ ] systemd service enabled and running        │
│ [ ] Service auto-restarts on disconnect        │
│ [ ] Logs show successful tunnel establishment  │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│          Phase 4: VPS API Endpoints            │
├─────────────────────────────────────────────────┤
│ [ ] Flask app installed on VPS                 │
│ [ ] POST /assist/audio endpoint responds       │
│ [ ] GET /health endpoint returns 200           │
│ [ ] POST /sensor/analyze endpoint works        │
│ [ ] POST /tts/generate endpoint works          │
│ [ ] Endpoint timeout: 10s (sanity check)       │
│ [ ] Error handling: returns JSON with message  │
│ [ ] Logging configured: /var/log/voice-api.log│
│ [ ] HTTPS working: curl https://dr.eamer.dev/..
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│          Phase 5: End-to-End Integration      │
├─────────────────────────────────────────────────┤
│ [ ] Pi audio file uploads to VPS successfully  │
│ [ ] VPS STT returns correct transcription      │
│ [ ] VPS LLM returns sensible response          │
│ [ ] VPS TTS returns audio (MP3 or WAV)         │
│ [ ] Pi receives and decodes TTS audio          │
│ [ ] Speaker plays response clearly             │
│ [ ] Full latency < 15s (acceptable)            │
│ [ ] Retry logic works on network failure       │
│ [ ] GUI stays responsive during voice command  │
│ [ ] Memory doesn't grow (no leaks)             │
│ [ ] Logs show no errors                        │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│          Phase 6: Production Readiness        │
├─────────────────────────────────────────────────┤
│ [ ] Documentation complete and tested          │
│ [ ] Rollback procedure documented              │
│ [ ] Monitoring alerts set up                   │
│ [ ] Backup of config files created             │
│ [ ] SSH keys backed up securely                │
│ [ ] Systemd services enabled for auto-start    │
│ [ ] Tested reboot cycle (cold start)           │
│ [ ] Performance baseline established           │
│ [ ] Load test: 10 commands in 2 minutes        │
│ [ ] Stress test: 100 commands continuously     │
│ [ ] User training / documentation reviewed     │
└─────────────────────────────────────────────────┘
```

---

**Generated for**: sensor-playground home assistant architecture
**Purpose**: Visual reference for all stakeholders
**Status**: Phase 1 Ready
