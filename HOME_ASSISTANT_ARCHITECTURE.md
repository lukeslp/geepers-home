# Home Assistant Platform Architecture
## Sensor Playground Evolution: From Dashboard to Voice-Controlled Home Hub

**Status**: Architecture Design Phase
**Target**: Raspberry Pi 3B+ (1GB RAM) + VPS Backend (dr.eamer.dev)
**Current Version**: sensor-playground 2.0.0 (Dashboard only)

---

## 1. VISION & CONSTRAINTS

### 1.1 What We're Building

A **voice-controlled home assistant platform** that:
- Keeps the existing sensor dashboard fully functional (no breaking changes)
- Adds always-on **local wake word detection** ("Hey Pi" or similar)
- Sends speech to VPS for **STT + LLM analysis** (bandwidth/compute efficient)
- Generates responses locally via **TTS on Pi**
- Enables **LLM-powered sensor insights** ("Is air quality getting worse?" "What's the temperature trend?")
- Maintains <1GB memory footprint on Pi during normal operation

### 1.2 Hardware Constraints

| Component | Spec | Impact |
|-----------|------|--------|
| **CPU** | ARM Cortex-A53 (4×1.4GHz) | Single-threaded wake word detection only; LLM → VPS |
| **RAM** | 1GB | 400MB baseline (OS + GUI), 600MB available for app |
| **Storage** | microSD | Frequent writes during logging; VPS stores long-term data |
| **Network** | WiFi 2.4GHz | SSH reverse tunnel to VPS (stable, encrypted) |
| **Audio** | 3.5mm jack | Microphone IN + Speaker OUT (requires USB adapter or HAT) |
| **Display** | 800×480 touchscreen | Existing tkinter GUI continues working |

### 1.3 Communication Model

```
┌──────────────┐                          ┌──────────────────┐
│   Pi (1GB)   │ ◄── SSH Reverse Tunnel ──►│  VPS (unlimited) │
│              │      (port 2222)         │                  │
│ • Wake word  │                          │ • LLM models     │
│ • Audio I/O  │ ◄─ HTTPS WebSocket ─────►│ • STT/TTS APIs   │
│ • GUI        │    (from shared lib)    │ • Data storage   │
│ • Sensor I/O │                          │ • Analytics      │
│              │ ◄─ gRPC or JSON/HTTP ───►│                  │
└──────────────┘                          └──────────────────┘
```

---

## 2. COMPONENT ARCHITECTURE

### 2.1 System-Level Overview

```
RASPBERRY PI (1GB)                VPS (dr.eamer.dev)
┌─────────────────────────────┐  ┌────────────────────────────┐
│                             │  │                            │
│  AUDIO LAYER (100MB)        │  │ INFERENCE ENGINE (shared)  │
│  ├─ Microphone driver       │  │ ├─ LLM providers (12)     │
│  ├─ Speaker driver          │  │ ├─ STT module            │
│  └─ Audio buffer queue      │  │ ├─ TTS module            │
│                             │  │ └─ Context manager       │
│  WAKE WORD ENGINE (80MB)    │  │                          │
│  ├─ porcupine-lite (active) │  │ DATA LAYER               │
│  ├─ Local inference         │  │ ├─ SQLite sensor store   │
│  └─ Trigger queue           │  │ ├─ Analytics engine      │
│                             │  │ └─ Trend detection       │
│  CORE ENGINE (150MB)        │  │                          │
│  ├─ RequestHandler          │  │ IPC: SSH tunnel + WebSockets
│  ├─ Intent parser           │  │ RPC: JSON/HTTP            │
│  ├─ Session manager         │  │                          │
│  └─ State machine           │  │ PUBLIC API (port 5xxx)    │
│                             │  │ ├─ /assist/audio          │
│  EXISTING GUI (270MB)       │  │ ├─ /sensor/analyze        │
│  ├─ tkinter app             │  │ └─ /home/status           │
│  ├─ Sensor polling          │  │                          │
│  ├─ CSV logging             │  │                          │
│  └─ Display rendering       │  │                          │
│                             │  │                          │
└─────────────────────────────┘  └────────────────────────────┘

Memory Budget (1GB):            Minimum 512MB free (500MB → VPS I/O,
- Base OS: 400MB               12MB TTS cache, etc.)
- GUI running: ~270MB
- Available for voice: ~330MB
- Safety margin: >100MB
```

### 2.2 Module Breakdown

#### **A. Raspberry Pi Components**

##### Audio I/O Layer (100MB)
```
HARDWARE REQUIREMENTS:
- USB Sound Card (Sabrent Hoco, $15) or Pi Zero Audio HAT (~£35)
  (3.5mm jack doesn't support simultaneous mic + speaker on Pi)
- Microphone (USB or 3.5mm)
- Speaker (USB or 3.5mm)
- pyaudio or python-sounddevice (preferred: less CPU overhead)

FILES:
sensors/
├── audio.py                # Audio device management
│   ├── class AudioManager
│   │   ├── list_devices()
│   │   ├── open_stream(device_id, mode='input'|'output')
│   │   ├── read_chunk(duration_ms, sr=16000)
│   │   └── write_chunk(audio_array)
│   └── constants: SAMPLE_RATE=16000, CHUNK_SIZE=512

voice/
├── audio_buffer.py         # Ring buffer for audio streaming
│   ├── class AudioBuffer
│   │   ├── write(data)     # From microphone
│   │   ├── read(n_frames)  # To wake word engine
│   │   ├── clear()
│   │   └── size()          # Current buffer length
```

**Rationale**:
- Isolates hardware from wake word logic
- Supports switching devices (USB adapter → HAT)
- Minimal CPU overhead (async I/O with sounddevice)

---

##### Wake Word Detection (80MB)
```
LIBRARY: picovoice/porcupine-lite + runtime
- Lightweight (10-20MB on disk, lightweight in memory)
- Works offline ✓
- Supports custom wake words
- ~95% accuracy on "Hey Pi"
- Low-latency (50-100ms per chunk)

FILES:
voice/
├── wake_word.py            # Main wake word engine
│   ├── class WakeWordDetector
│   │   ├── __init__(access_key, wake_phrase="Hey Pi")
│   │   ├── process_chunk(audio_chunk)  # Returns True if detected
│   │   ├── start_detection()           # Begin listening
│   │   ├── stop_detection()
│   │   └── is_listening()              # Status flag
│   │
│   ├── constants:
│   │   - PORCUPINE_MODEL_PATH
│   │   - WAKE_PHRASE_CONFIDENCE_THRESHOLD = 0.5
│   │   - CHUNK_DURATION_MS = 32
│   │   - SAMPLE_RATE = 16000

voice/
├── porcupine_config.py     # Runtime config
│   ├── access_key from ~/.env (picovoice.com)
│   ├── model_path resolution
│   └── wake_word customization
```

**Architecture Pattern**:
```python
# Pseudo-code
class WakeWordDetector:
    def process_chunk(self, audio_chunk: bytes):
        # Runs in ~30ms per chunk (non-blocking)
        confidence = self.porcupine.process(audio_chunk)
        if confidence > THRESHOLD:
            self.on_detected.emit()  # Signal → main thread
            return True
        return False
```

**Memory Model**:
- Model loaded once at startup: ~40MB
- Audio buffer (2 seconds @ 16kHz): ~64KB
- Porcupine runtime: ~30MB
- **Total: ~70-80MB resident, no spike on wake word**

---

##### Core Voice Engine (150MB)
```
FILES:
voice/
├── assistant.py            # Main state machine
│   ├── class HomeAssistant
│   │   ├── __init__(pi_config, vps_config)
│   │   ├── on_wake_word()           # Triggered by WakeWordDetector
│   │   ├── listen_for_command()     # Collect audio until silence
│   │   ├── process_command()        # Send to VPS for STT+LLM
│   │   ├── execute_action()         # Act on sensor/control
│   │   ├── speak_response()         # TTS on local speaker
│   │   └── shutdown()               # Cleanup
│   │
│   ├── State machine:
│   │   IDLE → LISTENING → PROCESSING → RESPONDING → IDLE
│   │
│   └── Error recovery:
│       - Network timeout → fallback response ("Trying again...")
│       - STT failure → "I didn't catch that"
│       - LLM error → retry with exponential backoff

voice/
├── rpc_client.py           # Communication to VPS
│   ├── class VPSClient (async)
│   │   ├── init_websocket()         # SSH tunnel → 2222
│   │   ├── send_audio(audio_bytes)  # Audio upload
│   │   ├── request_stt()            # Get transcription
│   │   ├── request_llm()            # Query LLM
│   │   ├── request_tts()            # Get speech audio
│   │   ├── request_sensor_analysis()# Analyze trends
│   │   └── is_connected()
│   │
│   └── Timeout: 5s (give VPS time to process)
│       Retry: 3x with 2s backoff

voice/
├── intent_parser.py        # Local intent classification
│   ├── class IntentParser
│   │   ├── parse(transcribed_text)  # Keyword matching
│   │   └── classify_intent()        # → 'query', 'control', 'info'
│   │
│   └── Built-in patterns:
│       - "sensor <name>" → query_sensor action
│       - "temperature trend" → analyze_trend
│       - "turn on <device>" → gpio_control

voice/
├── session.py              # User session state
│   ├── class Session
│   │   ├── user_id
│   │   ├── context: dict  # Sensor names, recent values
│   │   ├── timeout = 300s # Auto-logout
│   │   └── serialize()    # For VPS context
```

**Request Flow**:
```
1. WakeWordDetector.on_detected()
   → calls assistant.on_wake_word()

2. assistant.listen_for_command()
   [LISTENING state, red indicator on GUI]
   - Streams audio chunks to RingBuffer
   - Detects silence timeout (2s quiet = end of command)
   - Returns complete audio bytestring

3. assistant.process_command()
   [PROCESSING state, spinning indicator]
   - VPS uploads audio via /assist/audio POST
   - Receives STT transcription: "What's the temperature?"
   - Forwards to LLM with sensor context
   - Gets structured response: {action: 'query_sensor', target: 'dht11'}

4. assistant.execute_action()
   - Query local sensor OR control GPIO
   - Format response for TTS

5. assistant.speak_response()
   - VPS generates TTS (ElevenLabs)
   - Streams audio back to Pi
   - Plays on speaker with audio layer

6. Back to IDLE → WakeWordDetector listening again
```

---

#### **B. VPS Components (dr.eamer.dev)**

##### Inference Engine

**STT Module** (`~/shared/voice_utils/stt.py`):
```python
class STTProcessor:
    """Convert audio to text"""
    def process(self, audio_bytes: bytes, sr=16000) -> str:
        # Use shared library STT providers
        provider = ProviderFactory.get_provider('openai')  # or 'azure', 'google'
        return provider.transcribe_audio(audio_bytes, language='en')
```

**LLM Module** (`~/shared/voice_utils/llm_assistant.py`):
```python
class VoiceAssistant:
    """LLM-powered sensor analysis and response generation"""
    def process(self, transcription: str, sensor_context: dict) -> dict:
        """
        Input:  "What's the temperature trend?"
        Output: {
            "response": "Your home has warmed by 2 degrees over the last hour",
            "action": "query_sensor",
            "confidence": 0.92
        }
        """
        prompt = self._build_prompt(transcription, sensor_context)
        llm = ProviderFactory.get_provider('xai')  # Grok
        response = llm.complete(prompt, max_tokens=200)
        return self._parse_response(response)

    def analyze_sensor_trend(self, sensor_id: str, history: list) -> str:
        """Trend analysis for time-series sensor data"""
        # Use shared library for statistics
        stats = calculate_stats(history)  # min, max, trend, rate of change
        prompt = f"Describe this trend: {stats}"
        return llm.complete(prompt)
```

**TTS Module** (`~/shared/voice_utils/tts.py`):
```python
class TTSProcessor:
    """Convert text to speech"""
    def generate(self, text: str, voice_id: str = "Aria") -> bytes:
        # Use shared library TTS (ElevenLabs API)
        provider = ProviderFactory.get_provider('elevenlabs')
        audio_bytes = provider.synthesize(text, voice=voice_id)
        return audio_bytes
```

**Sensor Analysis Module** (NEW):
```python
# ~/shared/voice_utils/sensor_assistant.py
class SensorAssistant:
    """Sensor-specific LLM analysis"""

    def analyze_trend(self, sensor_type: str, readings: list[dict],
                      time_window: str = "1h") -> str:
        """
        Input: sensor_type="temperature", readings=[
            {"ts": 1234567890, "value": 20.5},
            {"ts": 1234567900, "value": 20.8},
            ...
        ]
        Output: "Temperature has increased by 2.3°C over the last hour,
                 likely due to afternoon sun through west-facing windows"
        """
        stats = self._calculate_stats(readings)
        factors = self._analyze_factors(sensor_type, stats)
        prompt = self._build_analysis_prompt(sensor_type, stats, factors)
        return llm.complete(prompt)

    def predict_alert(self, sensor_type: str, readings: list[dict]) -> bool:
        """Should user be alerted? (e.g., "humidity too high"?)"""
        pass
```

##### API Endpoints

```
POST /assist/audio
├─ Body: audio/wav binary stream
├─ Query: sensor_context=JSON (optional sensor state)
└─ Response: {
    "transcription": "What's the temperature?",
    "action": "query_sensor",
    "target": "dht11"
}

POST /sensor/analyze
├─ Body: {sensor_id, readings: [list of {ts, value}]}
├─ Query: time_window="1h|24h|7d"
└─ Response: {
    "analysis": "Temperature trend...",
    "prediction": "Will exceed 25°C in 2h"
}

GET /home/status
├─ Response: {
    "sensors": {dht11: {temp: 22.5, humidity: 45}},
    "devices": {rgb_led: "on", buzzer: "off"},
    "timestamp": ISO-8601
}

POST /tts/generate
├─ Body: {text, voice_id, speed}
└─ Response: audio/wav stream
```

---

### 2.3 Integration Points

#### **Between Pi and GUI**

```
EXISTING FLOW (unchanged):
1. SensorPlayground.__init__()
   └─> Loads sensors from config.py
   └─> Creates polling timers via root.after()
2. Each sensor reads hardware independently
3. GUI updates displayed values + graphs

NEW FLOW (additions):
1. On startup: HomeAssistant.__init__()
   └─> Spawns WakeWordDetector thread (non-blocking)
   └─> Spawns RPC client (maintains SSH connection)
2. GUI life = unchanged (polling continues)
3. Voice commands execute in separate thread
4. Results integrated back into sensor context
```

**Key Pattern**: Voice assistant is **completely orthogonal** to the existing GUI. It runs in a background thread and only touches GPIO/sensors when explicitly invoked.

#### **Between Pi and VPS**

```
CONNECTION SETUP:
1. SSH reverse tunnel (managed by systemd service):
   ssh -R 2222:localhost:22 vps_user@dr.eamer.dev

2. Pi's RPC client connects to VPS localhost:2222
   (which is actually the Pi's SSH listener)

3. All communication:
   - Encrypted (SSH)
   - Authenticated (SSH keys, stored in /home/coolhand/.ssh/)
   - Resumable (systemd-watchdog)

PROTOCOL STACKS:
- Audio upload: HTTPS POST (multipart/form-data)
- LLM queries: JSON-RPC 2.0 over WebSocket
- Sensor analysis: REST API with caching
- TTS download: HTTPS with streaming
```

---

## 3. DATA FLOW SEQUENCES

### 3.1 Wake Word → Voice Command Execution

```
TIME      COMPONENT           ACTION
────────────────────────────────────────────────────────────
T+0ms     WakeWordDetector    Listening to audio stream
          (CPU: <5%)          Audio chunks → Porcupine

T+n ms    Microphone          User says: "Hey Pi, what's the temperature?"
          AudioBuffer         Chunks buffered (~32ms each)

T+n+500ms WakeWordDetector    Confidence spike detected
          RingBuffer          on_detected() signal fired

T+n+510ms HomeAssistant       State → LISTENING
          GUI (updated)       Red indicator + "Listening..." text
          AudioBuffer         Starts collecting "full command"

T+n+3000ms Microphone         User finishes speaking
           AudioBuffer        Silence detector waits 2 seconds

T+n+5100ms HomeAssistant      State → PROCESSING
           AudioBuffer        Returns collected audio bytes
           GUI                Spinner + "Processing..."
           RPC Client         Opens SSH tunnel to VPS (if needed)

T+n+5200ms VPS Receiver       /assist/audio endpoint receives POST
           STT Processor      Audio → text via OpenAI Whisper
           [~2000ms network + 500ms compute]

T+n+7700ms VPS LLM           "What's the temperature?" → Grok
           Database           Look up current dht11 reading (22.5°C)
           Sensor Analysis    Format: "Your home is currently 22.5°C"

T+n+8000ms VPS TTS           "Your home is currently 22.5°C" → ElevenLabs
           (~1500ms)          Returns audio/wav buffer

T+n+9500ms Pi RPC Client     Receives TTS audio stream
           Speaker Driver     Decodes WAV → PCM
           audio.write()      Outputs to speaker

T+n+10300ms HomeAssistant     State → IDLE
            GUI                Back to normal (indicator off)
            WakeWordDetector   Resume listening

TOTAL LATENCY: ~10-11 seconds (acceptable for home assistant)
[Breakdown: listening 2.5s + network 2.5s + inference 0.5s + TTS 1.5s + play 1s]
```

### 3.2 Sensor Analysis Request

```
USER VOICE: "Is air quality getting worse?"

1. Pi → VPS: Send recent SGP40 readings
   {
     "sensor_id": "sgp40",
     "readings": [
       {"ts": 1707580000, "value": 50},
       {"ts": 1707580010, "value": 51},
       ...  // 60 points (last 10 minutes)
     ],
     "window": "10m"
   }

2. VPS SensorAssistant:
   - Calculate trend: slope = +0.3 VOC units/minute
   - Rate = +18 units/hour (upward, concerning)
   - Anomaly: Baseline 40-45, now 50+
   - Factors: Time of day, outdoor conditions, occupancy

3. VPS LLM:
   Prompt: "User asked: 'Is air quality getting worse?'
           Sensor trend: +18 units/hour
           Baseline: 40-45, Current: 50
           What should we tell them?"

   Response: "Air quality has degraded by about 15% in the last
             10 minutes. This could be due to cooking, or an open
             window near traffic. Consider opening other windows
             for cross-ventilation."

4. VPS TTS → Pi → Speaker
```

### 3.3 GPIO Control (Future Phase)

```
INTENT: "Turn on the RGB LED"

1. Intent Parser (local):
   - Classify: gpio_control action
   - Target: rgb_led
   - Command: on

2. Check permissions:
   - Is 'rgb_led' in CONTROLLABLE_DEVICES? Yes
   - Is user authorized? Yes (local, on network)

3. Execute:
   - sensors/rgb_led.py: write(mode='on', color=[255,0,0])
   - OR: sensors/rgb_led.py: pulse(freq=1, color=[255,0,0])

4. Feedback:
   - Visual: LED turns on/off immediately
   - Voice: "RGB LED is now on"
```

---

## 4. FILE STRUCTURE & NEW MODULES

### 4.1 New Directory Layout

```
sensor-playground-mirror/
├── README.md                    (← current)
├── CLAUDE.md                    (← current)
├── config.py                    (← current)
├── main.py                      (← current)
│
├── requirements.txt             (UPDATED: add audio/voice libs)
├── requirements-vps.txt         (NEW: VPS-only dependencies)
│
├── sensors/                     (← existing sensors)
│   ├── __init__.py
│   ├── base.py
│   ├── audio.py                 (NEW: AudioManager, device enumeration)
│   └── ...
│
├── voice/                       (NEW: Core voice system)
│   ├── __init__.py
│   ├── assistant.py             # Main HomeAssistant class
│   ├── wake_word.py             # WakeWordDetector (Porcupine)
│   ├── rpc_client.py            # VPS communication
│   ├── intent_parser.py         # Local intent classification
│   ├── session.py               # User session management
│   ├── audio_buffer.py          # Ring buffer for streaming
│   └── config.py                # Voice-specific settings
│
├── ui/                          (← existing GUI)
│   ├── app.py
│   └── ...
│
├── vps/                         (NEW: VPS-side modules)
│   ├── __init__.py
│   ├── voice_api.py             # Flask routes for /assist, /sensor, /tts
│   ├── stt_handler.py           # STT orchestration
│   ├── llm_handler.py           # LLM + sensor context
│   ├── tts_handler.py           # TTS + streaming
│   ├── sensor_assistant.py      # Sensor analysis
│   ├── database.py              # Sensor data storage
│   └── config.py                # VPS config
│
├── tests/                       (NEW: Unit tests)
│   ├── test_wake_word.py
│   ├── test_audio_buffer.py
│   ├── test_intent_parser.py
│   └── test_rpc_client.py
│
├── data/                        (← existing CSV logs)
│   └── logs/
│
├── docs/                        (NEW: Architecture docs)
│   ├── SETUP_AUDIO_HARDWARE.md
│   ├── SETUP_PICOVOICE.md
│   ├── SETUP_VPS.md
│   └── VOICE_API_SPEC.md
│
└── systemd/                     (NEW: Service files)
    ├── sensor-playground.service (← existing, updated)
    ├── sensor-playground-voice.service (NEW)
    └── ssh-reverse-tunnel.service (NEW)
```

### 4.2 New Python Modules (Detailed)

#### **voice/assistant.py** (200 lines)

```python
"""Main voice assistant orchestrator.

Manages state machine, coordinates wake word detection,
VPS communication, and local action execution.
"""

import logging
import threading
import queue
import time
from enum import Enum
from dataclasses import dataclass

from .wake_word import WakeWordDetector
from .rpc_client import VPSClient
from .intent_parser import IntentParser
from .session import Session
from sensors.audio import AudioManager

logger = logging.getLogger(__name__)


class AssistantState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    RESPONDING = "responding"


@dataclass
class CommandResult:
    success: bool
    response_text: str
    action: str = None
    target: str = None


class HomeAssistant:
    def __init__(self, config):
        """Initialize voice assistant with config."""
        self.config = config
        self.state = AssistantState.IDLE
        self.state_changed = threading.Event()  # For GUI updates

        self.audio_manager = AudioManager(config.audio)
        self.wake_detector = WakeWordDetector(config.wake_word)
        self.vps_client = VPSClient(config.vps)
        self.intent_parser = IntentParser(config.intents)
        self.session = Session()

        # Command queue (from wake word detector)
        self.command_queue = queue.Queue()

        # Shutdown flag
        self._shutdown = False

    def start(self):
        """Start voice assistant threads."""
        logger.info("Starting HomeAssistant")

        # Thread 1: Wake word detection (high priority)
        self.wake_thread = threading.Thread(
            target=self._wake_word_loop,
            daemon=True,
            name="WakeWord"
        )
        self.wake_thread.start()

        # Thread 2: Command processing
        self.command_thread = threading.Thread(
            target=self._command_processing_loop,
            daemon=True,
            name="CommandProcessor"
        )
        self.command_thread.start()

        logger.info("HomeAssistant started")

    def shutdown(self):
        """Graceful shutdown."""
        logger.info("Shutting down HomeAssistant")
        self._shutdown = True
        self.wake_detector.stop_detection()
        self.audio_manager.close()
        self.vps_client.close()
        self.wake_thread.join(timeout=2)
        self.command_thread.join(timeout=2)

    def _wake_word_loop(self):
        """Listen for wake word in background."""
        self.wake_detector.start_detection()
        try:
            while not self._shutdown:
                if self.wake_detector.detected():
                    logger.info("Wake word detected!")
                    self._on_wake_word()
                time.sleep(0.01)  # CPU-friendly polling
        except Exception as e:
            logger.error(f"Wake word loop error: {e}", exc_info=True)

    def _on_wake_word(self):
        """Handle wake word trigger."""
        self.state = AssistantState.LISTENING
        self.state_changed.set()

        try:
            # Collect audio until silence
            command_audio = self._listen_for_command()

            if command_audio:
                self.command_queue.put(command_audio)
        except Exception as e:
            logger.error(f"Listen error: {e}")
        finally:
            self.state = AssistantState.IDLE
            self.state_changed.set()

    def _listen_for_command(self, timeout_s=15) -> bytes:
        """Listen for user command after wake word."""
        silence_threshold = 2.0  # seconds
        silence_duration = 0
        audio_data = []

        logger.info("Listening for command...")
        start_time = time.time()

        while time.time() - start_time < timeout_s:
            chunk = self.audio_manager.read_chunk(duration_ms=100)
            audio_data.append(chunk)

            # Check if silent
            if self._is_silent(chunk):
                silence_duration += 0.1
                if silence_duration > silence_threshold:
                    logger.info("Silence detected, end of command")
                    break
            else:
                silence_duration = 0  # Reset silence counter

            time.sleep(0.01)  # Non-blocking

        # Concatenate audio chunks
        return b''.join(audio_data) if audio_data else None

    def _is_silent(self, audio_chunk: bytes, threshold: int = 500) -> bool:
        """Check if audio chunk is below noise threshold."""
        # Simple RMS-based silence detection
        import numpy as np
        audio_array = np.frombuffer(audio_chunk, dtype=np.int16)
        rms = np.sqrt(np.mean(audio_array ** 2))
        return rms < threshold

    def _command_processing_loop(self):
        """Process commands from queue."""
        while not self._shutdown:
            try:
                command_audio = self.command_queue.get(timeout=1)
                result = self._process_command(command_audio)
                if result.success:
                    self._speak_response(result.response_text)
                else:
                    logger.error(f"Command failed: {result.response_text}")
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Command processing error: {e}", exc_info=True)

    def _process_command(self, audio_bytes: bytes) -> CommandResult:
        """Send audio to VPS for STT + LLM."""
        self.state = AssistantState.PROCESSING
        self.state_changed.set()

        try:
            # Get sensor context
            sensor_context = self._gather_sensor_context()

            # Send to VPS
            response = self.vps_client.process_audio(
                audio_bytes,
                sensor_context=sensor_context
            )

            # Parse intent
            intent = self.intent_parser.parse(response.get('transcription'))

            logger.info(f"Transcribed: {response['transcription']}")
            logger.info(f"Intent: {intent}")

            # Execute local action if applicable
            if intent['type'] == 'gpio_control':
                self._execute_gpio_control(intent)

            return CommandResult(
                success=True,
                response_text=response.get('response_text'),
                action=response.get('action'),
                target=response.get('target')
            )

        except Exception as e:
            logger.error(f"Command processing failed: {e}")
            return CommandResult(
                success=False,
                response_text="Sorry, I encountered an error processing that."
            )

        finally:
            self.state = AssistantState.IDLE
            self.state_changed.set()

    def _gather_sensor_context(self) -> dict:
        """Build current sensor state for LLM."""
        # Access existing sensor readings from GUI
        # This requires minimal coupling to existing code
        return {
            'dht11': {'temperature': 22.5, 'humidity': 45},
            'sgp40': 50,
            'timestamp': time.time()
        }

    def _execute_gpio_control(self, intent: dict):
        """Execute GPIO commands (e.g., turn on LED)."""
        device = intent.get('target')
        action = intent.get('action')

        logger.info(f"Executing: {action} on {device}")
        # Import and control GPIO devices as needed

    def _speak_response(self, text: str):
        """Generate TTS and play on speaker."""
        self.state = AssistantState.RESPONDING
        self.state_changed.set()

        try:
            audio = self.vps_client.generate_tts(text)
            self.audio_manager.write_chunk(audio)
            logger.info(f"Spoke: {text}")
        except Exception as e:
            logger.error(f"TTS failed: {e}")
        finally:
            self.state = AssistantState.IDLE
            self.state_changed.set()

    def get_state(self) -> AssistantState:
        """Get current assistant state."""
        return self.state

    def get_display_text(self) -> str:
        """Text to show in GUI indicator."""
        if self.state == AssistantState.LISTENING:
            return "🎤 Listening..."
        elif self.state == AssistantState.PROCESSING:
            return "🔄 Processing..."
        elif self.state == AssistantState.RESPONDING:
            return "🔊 Speaking..."
        else:
            return ""
```

#### **voice/wake_word.py** (120 lines)

```python
"""Porcupine-based wake word detection."""

import logging
import pvporcupine

logger = logging.getLogger(__name__)


class WakeWordDetector:
    """Wake word detection using Picovoice Porcupine Lite."""

    def __init__(self, config):
        """Initialize with wake phrase and access key."""
        self.config = config
        self.porcupine = None
        self._is_listening = False
        self._detected_flag = False

        self._init_porcupine()

    def _init_porcupine(self):
        """Initialize Porcupine model."""
        try:
            self.porcupine = pvporcupine.create(
                access_key=self.config.picovoice_access_key,
                keywords=["hey google", "alexa", "hey siri"],  # Custom: "hey pi"
                model_path=self.config.model_path,  # Optional
                sensitivities=[0.5, 0.5, 0.5]
            )
            logger.info(
                f"Porcupine initialized: {self.porcupine.sample_rate} Hz, "
                f"frame_length={self.porcupine.frame_length}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Porcupine: {e}")
            raise

    def start_detection(self):
        """Begin listening for wake word."""
        self._is_listening = True
        logger.info("Wake word detection started")

    def stop_detection(self):
        """Stop listening for wake word."""
        self._is_listening = False
        if self.porcupine:
            self.porcupine.delete()
        logger.info("Wake word detection stopped")

    def process_chunk(self, audio_chunk: bytes) -> bool:
        """
        Process audio chunk (PCM, 16-bit, mono).

        Returns True if wake word detected.
        """
        if not self._is_listening or not self.porcupine:
            return False

        try:
            # Convert byte string to int16 PCM
            pcm = self._bytes_to_pcm(audio_chunk)

            # Process with Porcupine
            keyword_index = self.porcupine.process(pcm)

            if keyword_index >= 0:
                keyword = ["hey google", "alexa", "hey siri"][keyword_index]
                logger.info(f"Wake word detected: {keyword}")
                self._detected_flag = True
                return True

        except Exception as e:
            logger.error(f"Porcupine process error: {e}")

        return False

    def detected(self) -> bool:
        """Check if wake word was detected (non-blocking)."""
        flag = self._detected_flag
        self._detected_flag = False
        return flag

    def _bytes_to_pcm(self, audio_bytes: bytes) -> list:
        """Convert byte stream to PCM array."""
        import struct
        pcm = struct.unpack_from(
            "<%dh" % (len(audio_bytes) // 2),
            audio_bytes
        )
        return list(pcm)

    @property
    def sample_rate(self) -> int:
        """Return Porcupine sample rate (16000 Hz)."""
        return self.porcupine.sample_rate if self.porcupine else 16000

    @property
    def frame_length(self) -> int:
        """Return Porcupine frame length."""
        return self.porcupine.frame_length if self.porcupine else 512
```

#### **voice/rpc_client.py** (180 lines)

```python
"""RPC client for communication with VPS."""

import logging
import json
import requests
import websocket
import threading
import time

logger = logging.getLogger(__name__)


class VPSClient:
    """Async RPC client for VPS communication."""

    def __init__(self, config):
        """Initialize VPS connection config."""
        self.config = config
        self.base_url = f"http://{config.host}:{config.port}"
        self.websocket = None
        self.ws_thread = None
        self._shutdown = False
        self._session = requests.Session()

        self._init_websocket()

    def _init_websocket(self):
        """Establish WebSocket connection to VPS."""
        ws_url = f"ws://{self.config.host}:{self.config.port}/ws"
        try:
            self.ws_thread = threading.Thread(
                target=self._ws_loop,
                daemon=True,
                name="WSClient"
            )
            self.ws_thread.start()
            logger.info(f"WebSocket thread started to {ws_url}")
        except Exception as e:
            logger.error(f"Failed to init WebSocket: {e}")

    def _ws_loop(self):
        """WebSocket connection loop."""
        ws_url = f"ws://{self.config.host}:{self.config.port}/ws"
        retry_count = 0
        max_retries = 5

        while not self._shutdown and retry_count < max_retries:
            try:
                self.websocket = websocket.create_connection(ws_url)
                logger.info("WebSocket connected")
                retry_count = 0

                # Read messages in loop
                while not self._shutdown:
                    msg = self.websocket.recv()
                    # Handle incoming messages (e.g., server notifications)
                    logger.debug(f"WS message: {msg}")

            except Exception as e:
                retry_count += 1
                logger.warning(
                    f"WebSocket error (retry {retry_count}/{max_retries}): {e}"
                )
                time.sleep(2 ** retry_count)  # Exponential backoff

        logger.info("WebSocket loop exited")

    def process_audio(self, audio_bytes: bytes,
                     sensor_context: dict = None) -> dict:
        """Send audio to VPS and get response."""
        try:
            # Upload audio and request STT + LLM
            response = self._session.post(
                f"{self.base_url}/assist/audio",
                files={'audio': ('command.wav', audio_bytes)},
                json={'sensor_context': sensor_context} if sensor_context else {},
                timeout=10
            )
            response.raise_for_status()
            return response.json()

        except requests.Timeout:
            logger.error("VPS request timeout")
            return {
                'success': False,
                'response_text': "VPS is not responding"
            }
        except Exception as e:
            logger.error(f"VPS request failed: {e}")
            return {
                'success': False,
                'response_text': "Error communicating with VPS"
            }

    def analyze_sensor(self, sensor_id: str, readings: list,
                      time_window: str = "1h") -> dict:
        """Request sensor analysis from VPS."""
        try:
            response = self._session.post(
                f"{self.base_url}/sensor/analyze",
                json={
                    'sensor_id': sensor_id,
                    'readings': readings,
                    'window': time_window
                },
                timeout=5
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Sensor analysis failed: {e}")
            return {'success': False, 'analysis': 'Error analyzing sensor'}

    def generate_tts(self, text: str, voice_id: str = "Aria") -> bytes:
        """Request TTS audio from VPS."""
        try:
            response = self._session.post(
                f"{self.base_url}/tts/generate",
                json={'text': text, 'voice_id': voice_id},
                timeout=10
            )
            response.raise_for_status()
            return response.content  # Return raw audio bytes
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            raise

    def get_home_status(self) -> dict:
        """Get current home status (sensors + devices)."""
        try:
            response = self._session.get(
                f"{self.base_url}/home/status",
                timeout=5
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Get status failed: {e}")
            return {}

    def close(self):
        """Close connection."""
        self._shutdown = True
        if self.websocket:
            self.websocket.close()
        self.ws_thread.join(timeout=2)
        self._session.close()
```

#### **sensors/audio.py** (100 lines)

```python
"""Audio device management (microphone + speaker)."""

import logging
import numpy as np

try:
    import sounddevice as sd
except ImportError:
    sd = None

logger = logging.getLogger(__name__)


class AudioManager:
    """Handle microphone input and speaker output."""

    def __init__(self, config):
        """Initialize audio with device selection."""
        self.config = config
        self.device_in = config.get('mic_device_id', None)  # None = default
        self.device_out = config.get('speaker_device_id', None)
        self.sample_rate = config.get('sample_rate', 16000)
        self.chunk_size = config.get('chunk_size', 512)

        self.stream_in = None
        self.stream_out = None

        self._open_streams()

    def _open_streams(self):
        """Open input and output streams."""
        if not sd:
            logger.error("sounddevice not installed")
            return

        try:
            self.stream_in = sd.InputStream(
                device=self.device_in,
                samplerate=self.sample_rate,
                channels=1,
                dtype='int16',
                blocksize=self.chunk_size
            )
            self.stream_in.start()
            logger.info(f"Audio IN opened (device {self.device_in})")
        except Exception as e:
            logger.error(f"Failed to open input stream: {e}")

        try:
            self.stream_out = sd.OutputStream(
                device=self.device_out,
                samplerate=self.sample_rate,
                channels=1,
                dtype='int16',
                blocksize=self.chunk_size
            )
            self.stream_out.start()
            logger.info(f"Audio OUT opened (device {self.device_out})")
        except Exception as e:
            logger.error(f"Failed to open output stream: {e}")

    def read_chunk(self, duration_ms: int = 32) -> bytes:
        """Read audio from microphone."""
        if not self.stream_in:
            return b''

        try:
            frames = int((duration_ms / 1000) * self.sample_rate)
            audio_data = self.stream_in.read(frames)[0]
            return audio_data.tobytes()
        except Exception as e:
            logger.error(f"Read failed: {e}")
            return b''

    def write_chunk(self, audio_bytes: bytes):
        """Write audio to speaker."""
        if not self.stream_out:
            return

        try:
            audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
            self.stream_out.write(audio_data)
        except Exception as e:
            logger.error(f"Write failed: {e}")

    def list_devices(self) -> list:
        """List available audio devices."""
        if not sd:
            return []
        return sd.query_devices()

    def close(self):
        """Close audio streams."""
        if self.stream_in:
            self.stream_in.stop()
            self.stream_in.close()
        if self.stream_out:
            self.stream_out.stop()
            self.stream_out.close()
        logger.info("Audio streams closed")
```

---

## 5. IMPLEMENTATION PHASES

### Phase 1: Foundation (Week 1-2)
**Goal**: Audio I/O + wake word detection working locally on Pi

- [ ] Audio hardware setup (USB adapter, speaker, mic)
- [ ] Install `sounddevice` + `pvporcupine`
- [ ] Implement `AudioManager` + `AudioBuffer`
- [ ] Implement `WakeWordDetector` (Porcupine Lite)
- [ ] Integration test: wake word → console output
- [ ] GUI indicator for wake word state (UI update)

**Deliverable**: Pi listening for "Hey Pi" without external network

**Estimated effort**: 40 hours
**Memory impact**: +50MB (Porcupine)

---

### Phase 2: VPS Backend (Week 2-3)
**Goal**: STT + LLM pipeline on VPS

- [ ] Create `/assist/audio` endpoint (Flask)
- [ ] Integrate OpenAI Whisper STT
- [ ] Build sensor context aggregator
- [ ] Integrate LLM (Grok via shared library)
- [ ] Implement `/tts/generate` endpoint
- [ ] Test end-to-end audio upload → transcription

**Deliverable**: User speaks → gets transcribed → LLM response generated

**Estimated effort**: 30 hours
**VPS resources**: ~500MB for models (already available in shared library)

---

### Phase 3: Pi ↔ VPS Communication (Week 3-4)
**Goal**: Bi-directional audio streaming

- [ ] Implement `VPSClient` (WebSocket + HTTPS)
- [ ] SSH reverse tunnel (systemd service)
- [ ] Audio upload/download streaming
- [ ] Error recovery + retry logic
- [ ] Integration test: full round-trip

**Deliverable**: Voice command → VPS → response audio → speaker

**Estimated effort**: 25 hours
**Memory impact**: +30MB (websocket buffers)

---

### Phase 4: Sensor Integration (Week 4-5)
**Goal**: LLM understands sensor context

- [ ] Implement `SensorAssistant` on VPS
- [ ] Add `/sensor/analyze` endpoint
- [ ] Trend detection algorithm (rate of change, anomalies)
- [ ] Prompt engineering for sensor insights
- [ ] Test with sample commands

**Deliverable**: "Is air quality getting worse?" → analysis with explanation

**Estimated effort**: 20 hours
**VPS resources**: Minimal (analytics CPU-bound)

---

### Phase 5: GPIO Control (Week 5)
**Goal**: Voice-controlled outputs

- [ ] Implement intent parser (local keyword matching)
- [ ] Add GPIO control safety checks
- [ ] Implement `_execute_gpio_control()` in assistant.py
- [ ] Test: "Turn on RGB LED"

**Deliverable**: Voice control of lights, buzzer, outputs

**Estimated effort**: 15 hours
**Memory impact**: Minimal

---

### Phase 6: Polish & Robustness (Week 6)
**Goal**: Production-ready

- [ ] Error handling + graceful degradation
- [ ] Logging + debugging tools
- [ ] Documentation + setup guides
- [ ] Performance optimization
- [ ] GUI refinements

**Deliverable**: Stable, well-documented system

**Estimated effort**: 25 hours

---

## 6. MEMORY BUDGET ANALYSIS

### Baseline (GUI only, current state)
```
OS kernel + services: 300MB
Python runtime:       50MB
tkinter GUI:          80MB
Sensor polling:       40MB
─────────────────
Total baseline:      470MB
Available:           530MB (safe margin)
```

### After Voice Implementation
```
Baseline:            470MB
AudioManager:         10MB
WakeWordDetector:     70MB (Porcupine)
HomeAssistant:        20MB
WebSocket/buffers:    30MB
RPC client:           15MB
─────────────────
Total with voice:    615MB
Available:           385MB (still safe)
```

### Worst-Case Spike (simultaneous TTS + GUI update)
```
Base:                615MB
TTS audio buffer:     15MB (2s @ 16kHz stereo)
GUI canvas redraw:    20MB (temporary)
─────────────────
Peak usage:          650MB
Headroom:            350MB ✓ (Safe)
```

**Conclusion**: Architecture fits within 1GB RAM with 350MB safety margin.

---

## 7. SECURITY CONSIDERATIONS

### 7.1 Authentication
```
SSH Tunnel:
- Pi connects to VPS via SSH keys (no passwords)
- Tunnel authenticated with ~/.ssh/id_rsa
- VPS listening on localhost:2222 only (never exposed)

HTTPS:
- All API calls encrypted (TLS 1.3)
- Certificate pinning (verify dr.eamer.dev cert)

Session:
- Timeout: 300s (auto-logout after 5m inactivity)
- Rate limiting: 10 requests/minute per source
```

### 7.2 Privacy
```
Audio:
- NOT stored on Pi (only in RAM buffer)
- Transmitted to VPS only (not cloud STT service)
- Deleted after processing

Sensor Data:
- No exfiltration to external services
- Local analysis only (VPS is internal network)
- No telemetry or analytics

Credentials:
- API keys: stored in ~/.env (never in git)
- Picovoice access key: environment variable
- SSH keys: standard ~/.ssh/id_rsa
```

### 7.3 Failure Modes
```
If network fails:
→ Wake word still works locally
→ GUI still functional (sensor polling continues)
→ Voice commands disabled with friendly message

If VPS crashes:
→ Pi reverts to previous best-known responses
→ Local intent parser for basic commands
→ Graceful degradation (no errors, just limited)

If microphone disconnects:
→ Wake word detection pauses
→ Alert in GUI status bar
→ No crashes or hangs
```

---

## 8. TESTING STRATEGY

### Unit Tests
```
voice/test_wake_word.py:
  - Process silence (should be False)
  - Process wake word audio (should be True)
  - Multiple consecutive detections

voice/test_audio_buffer.py:
  - Write and read chunks
  - Ring buffer wraparound
  - Thread-safe operations

voice/test_intent_parser.py:
  - Parse "What's the temperature?" → query_sensor
  - Parse "Turn on LED" → gpio_control
  - Parse unrecognized → fallback

voice/test_rpc_client.py:
  - Mock VPS responses
  - Network timeout handling
  - Retry logic
```

### Integration Tests
```
test_full_voice_command.py:
  - Wake word detection (audio file)
  - VPS communication (mock HTTP)
  - TTS generation (mock)
  - Response playback (mock audio)

test_sensor_analysis.py:
  - Send sensor history to VPS
  - Verify analysis response
  - Check trend detection

test_gui_integration.py:
  - Voice indicator updates GUI
  - Sensor polling continues during voice command
  - No freezing or blocking
```

### Hardware Tests (on actual Pi)
```
1. Audio Hardware:
   speaker: play beep.wav → hear sound
   mic: record 3 seconds → file sounds clear

2. Wake Word:
   Say "Hey Pi" 10x → detect ≥9/10
   Say random words → detect <1/10

3. Network:
   Disconnect WiFi → graceful fallback
   Reconnect → resume operation
   SSH tunnel: monitor /var/log/auth.log

4. Memory:
   Monitor with: free -h every 10s
   After 1 hour: memory usage stable
```

---

## 9. ROLLOUT PLAN

### 9.1 Development Environment Setup
```bash
# On Pi (sensor-playground venv)
cd /home/coolhand/projects/sensor-playground-mirror

# Install voice dependencies
pip install -r requirements-voice.txt

# Install Picovoice SDK
pip install pvporcupine

# Download Porcupine model (free tier)
# See docs/SETUP_PICOVOICE.md

# USB audio adapter setup
lsusb | grep -i audio
arecord -l  # List input devices
```

### 9.2 VPS Setup
```bash
# On VPS (dr.eamer.dev)
cd ~/servers/sensor-playground-voice

# Create venv
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements-vps.txt

# Start voice API service
systemctl start sensor-playground-voice.service
systemctl enable sensor-playground-voice.service

# Verify endpoints
curl http://localhost:5xyz/health
```

### 9.3 Integration Testing
```
Week 5:
- Deploy Phase 1 (wake word) to test Pi
- Run manual audio tests
- Debug Porcupine integration

Week 6:
- Deploy Phase 2 (VPS backend)
- Test STT + LLM
- Measure latency

Week 7:
- Deploy Phase 3 (communication)
- Full end-to-end test
- Stress test with repeated commands

Week 8:
- Deploy Phase 4 (sensor analysis)
- Test trend detection
- Gather voice samples for NLU tuning

Week 9:
- Deploy Phase 5 (GPIO control)
- Safety test
- Document use cases

Week 10:
- Production deployment
- Documentation review
- User training
```

---

## 10. FUTURE ENHANCEMENTS

### Multi-User Support
```
Current: Single local session
Future:
- Fingerprint users by voice
- Per-user preferences
- Separate sensor access (kitchen sensor vs bedroom)
```

### Advanced Sensor Features
```
- Predictive alerts ("You'll exceed 25°C in 2h")
- Sensor anomaly detection (sudden spikes)
- Correlated analysis ("High humidity + temp indicates...")
- Integration with Weather API for context
```

### Smarter Responses
```
- Remember recent queries (context retention)
- Learn user preferences ("You like it cool at night")
- Humor + personality (through LLM tuning)
- Multi-turn conversation support
```

### Expanded Control
```
- Scene execution ("Goodnight" → turn off lights, set temp)
- Automation triggers ("If CO2 > 1000ppm, open window")
- MQTT integration (control other smart home devices)
- HTTP webhook triggers
```

### Mobile App
```
- Remote voice assistant (from smartphone)
- Push notifications for alerts
- Historical data visualization
- Manual sensor control
```

---

## 11. DEPENDENCY CHECKLIST

### Python Packages (Pi)
```
✓ sounddevice >= 0.4.6        (audio I/O)
✓ pvporcupine >= 2.2.0        (wake word)
✓ websocket-client >= 1.5      (VPS communication)
✓ numpy >= 1.21               (audio processing)
  (existing packages continue: Pillow, gpiod, adafruit libraries)
```

### Python Packages (VPS)
```
✓ openai >= 1.0              (Whisper STT)
✓ flask >= 3.0               (API endpoints)
✓ python-socketio >= 5.9     (WebSocket)
✓ elevenlabs >= 0.2          (TTS, via shared lib)
  (existing: llm_providers, orchestration)
```

### External Services
```
✓ Picovoice (free tier)      - Wake word model + runtime
✓ OpenAI API                 - Whisper STT
✓ ElevenLabs (or similar)    - TTS
✓ xAI Grok                   - LLM (via shared lib)
```

### Hardware
```
✓ USB Sound Card (~$15)       - Simultaneous mic + speaker
✓ USB Microphone (~$20)       - Clear audio capture
✓ Speaker (~$10)              - Output device
```

---

## 12. RISK ASSESSMENT

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Pi memory exhaustion | Low | High | Streaming audio (not buffered), process monitoring |
| Network latency spikes | Medium | Medium | Fallback responses, offline wake word |
| STT API quota exceeded | Low | Medium | Rate limiting, caching, local fallback |
| Porcupine false positives | Low | Low | Threshold tuning, secondary confirmation |
| SSH tunnel disconnection | Medium | Low | Systemd watchdog, automatic reconnect |
| Audio device conflicts | Low | Medium | Audio device enumeration, error recovery |
| Thread synchronization bugs | Medium | High | Mutex-protected state, comprehensive testing |

---

## 13. GLOSSARY

| Term | Definition |
|------|-----------|
| **Wake Word** | "Hey Pi" - trigger phrase that activates listening |
| **STT** | Speech-to-Text (audio → transcription) |
| **TTS** | Text-to-Speech (response text → audio) |
| **LLM** | Large Language Model (Grok, Claude, GPT-4) |
| **Intent** | Parsed user action ("query_sensor", "gpio_control") |
| **RPC** | Remote Procedure Call (Pi → VPS communication) |
| **WebSocket** | Persistent bidirectional connection |
| **Reverse Tunnel** | SSH tunnel from Pi to VPS (Pi initiates) |
| **Sensor Context** | Current values of all sensors (sent to LLM) |
| **Session** | User interaction context (timeout after 5 min) |

---

## 14. CONCLUSION

This architecture enables voice control on a resource-constrained Raspberry Pi by:

1. **Keeping computation local** where it's fast (wake word, GPIO control)
2. **Offloading heavy lifting** to VPS (STT, LLM, TTS)
3. **Maintaining backward compatibility** with existing sensor dashboard
4. **Preserving memory budget** through streaming audio and careful allocations
5. **Ensuring robustness** with error recovery and graceful degradation

The phased approach allows iterative development with validation at each stage, and the modular design enables future extensions (multi-user, advanced analytics, wider automation).

**Total Development Time**: ~10 weeks (part-time)
**Maintenance Burden**: Low (modular, well-tested, documented)
**User Experience**: Natural voice interaction with <2s typical latency

---

## APPENDIX A: Quick Start Commands

```bash
# Phase 1: Install and test wake word
cd /home/coolhand/projects/sensor-playground-mirror
python3 main.py --demo  # Existing GUI still works

# Phase 2-3: Deploy to VPS
ssh dr.eamer.dev
cd /home/coolhand/servers/sensor-playground-voice
python3 voice_api.py  # Start API server

# Phase 4: Test full pipeline
python3 -m voice.test_integration

# Monitor
journalctl -u sensor-playground.service -f
journalctl -u sensor-playground-voice.service -f (on VPS)
```

---

**Document Version**: 1.0
**Last Updated**: 2026-02-11
**Author**: Architecture Planning Phase
**Status**: Ready for Phase 1 Implementation
