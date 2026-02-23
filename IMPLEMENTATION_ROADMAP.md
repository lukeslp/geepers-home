# Implementation Roadmap
## Sensor Playground Home Assistant Platform

**Timeline**: 10 weeks (part-time, ~150 hours)
**Start Date**: Ready to begin
**Target Release**: Production-ready by week 10

---

## PHASE 1: Audio Foundation (Weeks 1-2)
### Goal: Capture user voice and detect wake words locally

#### Week 1.1: Audio Hardware Setup (20 hours)

**Tasks**:
1. **Purchase & connect USB sound card**
   - Recommended: Sabrent USB Audio Card or HiFi Berry DAC
   - Check GPIO/pinout doesn't conflict
   - Mount on Pi using USB hub if needed

2. **Install audio drivers & libraries**
   ```bash
   sudo apt install alsa-utils python3-dev
   pip install sounddevice numpy pyaudio

   # Test devices
   arecord -l  # List input devices
   aplay -l    # List output devices
   ```

3. **Test audio capture**
   - Record 3-second test: `arecord -f S16_LE -r 16000 test.wav`
   - Playback test: `aplay test.wav`
   - Verify quality and levels

4. **Implement `sensors/audio.py`** (AudioManager class)
   - Device enumeration
   - Stream initialization (16kHz, 16-bit, mono)
   - Read/write chunks with sounddevice
   - Graceful error handling

5. **Create `voice/audio_buffer.py`** (RingBuffer class)
   - Circular buffer for streaming
   - Thread-safe write/read operations
   - 2-second window for wake word processing

**Deliverables**:
- [ ] Microphone input captured at 16kHz
- [ ] Speaker output plays audio clearly
- [ ] AudioManager handles device selection
- [ ] RingBuffer streams data without blocking
- [ ] Test script: `python3 test_audio.py --record 3 --playback`

**Validation**:
```bash
# Test recording quality
arecord -f S16_LE -r 16000 -d 3 test.wav
aplay test.wav
# Should hear clear voice without distortion

# Test Python audio manager
python3 -c "from sensors.audio import AudioManager; a = AudioManager({'sample_rate': 16000}); print('Audio OK')"
```

---

#### Week 1.2: Picovoice Integration (15 hours)

**Tasks**:
1. **Sign up for Picovoice (free tier)**
   - Go to picovoice.ai
   - Create account
   - Generate access key (free tier: 2000 inferences/month)
   - Download Porcupine Lite model (~10MB)

2. **Install Picovoice SDK**
   ```bash
   pip install pvporcupine

   # Verify installation
   python3 -c "import pvporcupine; print(pvporcupine.__version__)"
   ```

3. **Implement `voice/wake_word.py`** (WakeWordDetector class)
   - Initialize Porcupine with access key
   - Process audio chunks (detect wake word)
   - Thread-safe state tracking
   - Basic logging

4. **Test with audio samples**
   - Record yourself saying "Hey Pi" (10x)
   - Record background noise (10x)
   - Measure detection rate + false positive rate
   - Goal: >90% detection, <5% false positives

5. **Optimize Porcupine parameters**
   - Sensitivity threshold tuning (0.0-1.0)
   - Test different phrases if needed

**Deliverables**:
- [ ] Porcupine installed and access key configured
- [ ] WakeWordDetector processes 512-sample chunks
- [ ] Test accuracy: 9/10 for wake word, <1/10 for noise
- [ ] CPU usage < 3% during listening
- [ ] Memory footprint stable (<80MB for detector)

**Validation**:
```bash
# Test wake word detector
python3 -c "
from voice.wake_word import WakeWordDetector
detector = WakeWordDetector({'picovoice_access_key': 'YOUR_KEY'})
print('Wake word detector initialized')
# Run in loop and say 'Hey Pi'
"

# Measure CPU/memory
ps aux | grep python
free -h
```

---

#### Week 2.1: Threaded Wake Word Loop (15 hours)

**Tasks**:
1. **Implement `voice/assistant.py`** (HomeAssistant class skeleton)
   - State machine (IDLE, LISTENING, PROCESSING, RESPONDING)
   - Wake word thread (daemon, non-blocking)
   - Command queue (from wake word to processor)

2. **Create wake word listening loop**
   - Continuous audio streaming from AudioManager
   - Feed chunks to WakeWordDetector
   - Flag set when wake word detected
   - CPU-friendly polling (sleep 10ms between checks)

3. **Integrate with existing GUI** (no breaking changes)
   - Add voice indicator (e.g., "🎤" icon) to status bar
   - Update indicator when state changes
   - Thread-safe queue for state updates to GUI
   - GUI remains responsive (voice runs in background)

4. **Test thread isolation**
   - Launch GUI and voice thread together
   - Verify GUI doesn't freeze during voice processing
   - Sensor polling continues normally
   - No race conditions or crashes

**Deliverables**:
- [ ] HomeAssistant class initialized in `main.py`
- [ ] Wake word thread runs as daemon
- [ ] Voice indicator in GUI shows current state
- [ ] Continuous listening for ~1 hour without CPU/memory issues
- [ ] GUI remains responsive (>30fps)

**Validation**:
```bash
# Run full app with voice
python3 main.py --demo

# In another terminal, monitor
watch -n 1 "ps aux | grep python; free -h"

# Say "Hey Pi" and observe GUI indicator change
```

---

#### Week 2.2: Audio Collection & Silence Detection (10 hours)

**Tasks**:
1. **Implement command audio collection** in `HomeAssistant`
   - When wake word detected → LISTENING state
   - Collect audio chunks until silence
   - Simple RMS-based silence detection
   - Timeout fallback (max 15 seconds)

2. **Create silence detector**
   - RMS threshold: ~500 (empirically tuned)
   - Silence duration: 2 seconds before end-of-command
   - Handle speech pauses gracefully

3. **Test audio collection**
   - Record "What's the temperature?" (2-8 seconds)
   - Verify silence detection triggers at end
   - Save collected audio to file for later debugging

4. **Add UI feedback**
   - Show "Listening..." text in GUI
   - Progress indicator (visual feedback)
   - Confidence meter (optional)

**Deliverables**:
- [ ] Audio collection works (tested with voice)
- [ ] Silence detection reliable (tested with pauses)
- [ ] Collected audio saved to `/tmp/` for debugging
- [ ] GUI shows listening state and duration
- [ ] No audio loss or buffer overruns

**Validation**:
```bash
# Test silence detection
python3 -c "
from voice.assistant import HomeAssistant
from voice.config import default_config

app = HomeAssistant(default_config)
app.start()

# Say 'Hey Pi, what's the temperature?'
# Listen for saved audio: ls -la /tmp/command_audio_*.wav
"
```

---

## PHASE 2: VPS Backend (Weeks 2-3)
### Goal: Process speech on VPS (STT + LLM)

#### Week 2.3: VPS Project Setup (10 hours)

**Tasks**:
1. **Create VPS service structure**
   ```bash
   mkdir -p /home/coolhand/servers/sensor-playground-voice
   cd /home/coolhand/servers/sensor-playground-voice

   python3.11 -m venv venv
   source venv/bin/activate

   mkdir -p {vps,tests,data,logs}
   touch voice_api.py requirements.txt
   ```

2. **Create requirements.txt** (VPS-specific)
   ```
   flask>=3.0
   flask-cors>=4.0
   openai>=1.0
   elevenlabs>=0.2
   python-socketio>=5.9
   numpy>=1.21
   ```

3. **Set up logging**
   - /var/log/voice-api.log
   - Rotating file handler (10MB per file, 5 backups)
   - Log all API calls + errors

4. **Create health check endpoint**
   - GET /health → {status: "ok", uptime: "..."}
   - Verify dependencies loaded (OpenAI, ElevenLabs)

**Deliverables**:
- [ ] VPS venv created with dependencies installed
- [ ] Health endpoint responds with 200 OK
- [ ] Logging system operational
- [ ] Ready for endpoint implementation

---

#### Week 3.1: STT + LLM Integration (20 hours)

**Tasks**:
1. **Implement STT handler**
   ```python
   # vps/stt_handler.py
   from openai import OpenAI

   class STTProcessor:
       def __init__(self, api_key):
           self.client = OpenAI(api_key=api_key)

       def transcribe(self, audio_bytes):
           # Convert bytes → WAV file
           # Call Whisper API
           # Return transcription
   ```

2. **Implement LLM handler**
   ```python
   # vps/llm_handler.py
   import sys
   sys.path.insert(0, '/home/coolhand/shared')
   from llm_providers import ProviderFactory

   class LLMHandler:
       def __init__(self):
           self.llm = ProviderFactory.get_provider('xai')  # Grok

       def process(self, transcription, sensor_context):
           prompt = self._build_prompt(transcription, sensor_context)
           response = self.llm.complete(prompt)
           return response
   ```

3. **Build sensor context system**
   - Accept sensor data from Pi
   - Format for LLM prompt
   - Handle missing sensors gracefully

4. **Create `/assist/audio` endpoint**
   ```python
   @app.route('/assist/audio', methods=['POST'])
   def assist_audio():
       audio_file = request.files['audio']
       sensor_context = request.json.get('sensor_context', {})

       # STT
       transcription = stt_processor.transcribe(audio_file)

       # LLM
       response = llm_handler.process(transcription, sensor_context)

       # TTS (next)

       return jsonify({
           'transcription': transcription,
           'response': response
       })
   ```

5. **Test with mock audio**
   - Record audio samples on Pi
   - Upload to VPS endpoint
   - Verify STT output
   - Verify LLM response

**Deliverables**:
- [ ] STT working (Whisper API integrated)
- [ ] LLM working (Grok queries returning responses)
- [ ] `/assist/audio` endpoint receives audio + context
- [ ] Returns JSON with transcription + response
- [ ] Latency < 3 seconds for STT+LLM (acceptable)

**Test Script**:
```bash
# On VPS
cd /home/coolhand/servers/sensor-playground-voice
source venv/bin/activate
python3 voice_api.py &

# On Pi (or test machine)
curl -X POST http://dr.eamer.dev:5xyz/assist/audio \
  -F "audio=@command.wav" \
  -H "Content-Type: multipart/form-data"

# Expected response:
# {"transcription": "What's the temperature?",
#  "response": "..."}
```

---

#### Week 3.2: TTS Implementation (15 hours)

**Tasks**:
1. **Implement TTS handler**
   ```python
   # vps/tts_handler.py
   import sys
   sys.path.insert(0, '/home/coolhand/shared')
   from llm_providers import ProviderFactory

   class TTSProcessor:
       def __init__(self):
           self.tts = ProviderFactory.get_provider('elevenlabs')

       def synthesize(self, text, voice_id='Aria'):
           audio_bytes = self.tts.synthesize(text, voice=voice_id)
           return audio_bytes  # MP3 or WAV
   ```

2. **Create `/tts/generate` endpoint**
   ```python
   @app.route('/tts/generate', methods=['POST'])
   def tts_generate():
       data = request.json
       text = data.get('text')
       voice_id = data.get('voice_id', 'Aria')

       audio_bytes = tts_processor.synthesize(text, voice_id)

       return send_file(
           BytesIO(audio_bytes),
           mimetype='audio/mp3',
           as_attachment=True,
           download_name='response.mp3'
       )
   ```

3. **Integrate with `/assist/audio` endpoint**
   - Combine STT → LLM → TTS in single request
   - Stream TTS audio back to Pi
   - OR return just text + separate TTS endpoint

4. **Test TTS output quality**
   - Download audio from endpoint
   - Play on speaker
   - Verify clarity and naturalness

**Deliverables**:
- [ ] TTS endpoint working
- [ ] Audio quality acceptable (clear voice)
- [ ] Latency < 3 seconds
- [ ] Multiple voice options available

---

## PHASE 3: Pi ↔ VPS Communication (Weeks 3-4)
### Goal: Bi-directional reliable communication

#### Week 3.3: SSH Reverse Tunnel Setup (12 hours)

**Tasks**:
1. **Generate SSH key pair on Pi**
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/id_rsa -N ""
   cat ~/.ssh/id_rsa.pub
   ```

2. **Add public key to VPS**
   ```bash
   # On VPS
   mkdir -p ~/.ssh
   echo "$(cat pi_public_key)" >> ~/.ssh/authorized_keys
   chmod 700 ~/.ssh
   chmod 600 ~/.ssh/authorized_keys
   ```

3. **Test SSH connection**
   ```bash
   # From Pi
   ssh -v user@dr.eamer.dev
   # Should connect without password
   ```

4. **Create reverse tunnel manually**
   ```bash
   ssh -R 2222:localhost:22 user@dr.eamer.dev
   # From another terminal on VPS:
   ssh pi@localhost -p 2222
   # Should connect to Pi
   ```

5. **Create systemd service** (`ssh-reverse-tunnel.service`)
   ```ini
   [Unit]
   Description=SSH Reverse Tunnel to VPS
   After=network.target

   [Service]
   Type=simple
   User=pi
   ExecStart=/usr/bin/ssh -N -R 2222:localhost:22 \
       -o ServerAliveInterval=60 \
       -o ServerAliveCountMax=3 \
       -i /home/pi/.ssh/id_rsa \
       user@dr.eamer.dev
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

6. **Enable and test service**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable ssh-reverse-tunnel
   sudo systemctl start ssh-reverse-tunnel

   # Monitor
   journalctl -u ssh-reverse-tunnel -f
   ```

**Deliverables**:
- [ ] SSH key pair created (no password)
- [ ] Reverse tunnel established and persistent
- [ ] systemd service auto-starts on boot
- [ ] Auto-reconnects on network interruption
- [ ] Can SSH from VPS to Pi via localhost:2222

---

#### Week 4.1: RPC Client Implementation (15 hours)

**Tasks**:
1. **Implement `voice/rpc_client.py`** (VPSClient class)
   ```python
   class VPSClient:
       def __init__(self, host, port):
           self.base_url = f"http://{host}:{port}"
           self.session = requests.Session()

       def process_audio(self, audio_bytes, sensor_context=None):
           # Upload audio via HTTPS POST
           # Return transcription + response
           pass

       def generate_tts(self, text, voice_id='Aria'):
           # Request TTS generation
           # Stream audio back
           pass
   ```

2. **Handle network errors gracefully**
   - Timeout: 10 seconds (reasonable for STT+LLM)
   - Retry: exponential backoff (2s, 4s, 8s)
   - Fallback: offline responses ("Network error...")

3. **Implement streaming TTS download**
   - Pipe audio directly to speaker (don't buffer full file)
   - Ring buffer for low-latency playback

4. **Test RPC communication**
   - Pi sends audio to VPS
   - VPS returns transcription + response
   - Full round-trip < 5 seconds

**Deliverables**:
- [ ] RPC client connects to VPS via localhost:2222
- [ ] Audio upload successful (multipart/form-data)
- [ ] Response parsing working (JSON)
- [ ] Timeouts and retries functioning
- [ ] No memory leaks (test for 1 hour continuous use)

---

#### Week 4.2: Integration & Latency Tuning (12 hours)

**Tasks**:
1. **Full integration test**
   - Pi: wake word detection
   - Pi: listen for command
   - Pi → VPS: upload audio
   - VPS: STT + LLM + TTS
   - VPS → Pi: download audio
   - Pi: play on speaker

2. **Measure end-to-end latency**
   - Target: < 15 seconds (acceptable for home assistant)
   - Breakdown:
     - Listen: 2-5s (variable)
     - Upload: 1-2s
     - STT: 0.5-2s
     - LLM: 0.2-0.8s
     - TTS: 1-3s
     - Download: 0.1-0.5s
     - Playback: 2-4s (audio duration)

3. **Optimize slow paths**
   - If STT too slow: reduce audio quality (8kHz) or use faster API
   - If LLM too slow: use faster model or cache common queries
   - If TTS too slow: pre-generate some responses

4. **Test under load**
   - 10 rapid commands in 2 minutes
   - Monitor memory/CPU for leaks
   - Verify recovery after network interruption

**Deliverables**:
- [ ] Full voice command pipeline working end-to-end
- [ ] Latency acceptable (8-15s)
- [ ] No memory leaks under sustained load
- [ ] Network resilience verified (survives WiFi dropout)
- [ ] Logs show all steps clearly

---

## PHASE 4: Sensor Integration (Weeks 4-5)
### Goal: LLM understands and analyzes sensor data

#### Week 4.3: Sensor Analysis Engine (12 hours)

**Tasks**:
1. **Create `vps/sensor_assistant.py`**
   ```python
   class SensorAssistant:
       def analyze_trend(self, sensor_id, readings, time_window='1h'):
           """Analyze sensor trend and provide insight"""
           # Calculate statistics
           # Detect anomalies
           # Format for LLM
           # Generate analysis

       def predict_alert(self, sensor_id, readings):
           """Should we alert user?"""
           # Check against thresholds
           # Predict future values
           pass
   ```

2. **Implement trend calculation**
   - Min/max/avg over time window
   - Rate of change (slope)
   - Anomaly detection (standard deviation)

3. **Build LLM prompts for sensor analysis**
   ```
   "User asked: 'Is air quality getting worse?'

    Sensor: SGP40 (Air Quality / VOC Index)
    - Current value: 52
    - Baseline range: 40-45
    - Trend: +0.4 units/min (+24 units/hour)
    - Time window: Last 10 minutes
    - Prediction: Will exceed 60 in 20 minutes

    Provide a natural explanation of this trend and recommendations."
   ```

4. **Create `/sensor/analyze` endpoint**
   ```python
   @app.route('/sensor/analyze', methods=['POST'])
   def sensor_analyze():
       data = request.json
       sensor_id = data['sensor_id']
       readings = data['readings']  # [{ts, value}, ...]

       analysis = sensor_assistant.analyze_trend(
           sensor_id, readings
       )

       return jsonify(analysis)
   ```

**Deliverables**:
- [ ] Trend analysis working (min/max/avg/slope)
- [ ] Anomaly detection implemented
- [ ] `/sensor/analyze` endpoint functional
- [ ] LLM provides insightful analysis
- [ ] Test: send 10 min temperature history, get analysis

---

#### Week 5.1: Test Sensor Insights (10 hours)

**Tasks**:
1. **Test data collection on Pi**
   - Log sensor values every 10 seconds for 1 hour
   - Export to JSON format
   - Send to VPS for analysis

2. **Test common queries**
   - "What's the temperature trend?"
   - "Is air quality getting worse?"
   - "Has humidity changed much?"
   - "Are there any sensor anomalies?"

3. **Verify LLM accuracy**
   - Manual check: Does analysis match the data?
   - Reasonable conclusions drawn?
   - Appropriate recommendations?

4. **Optimize prompts**
   - Adjust for clarity and detail
   - Test different LLM models (Grok vs Claude vs GPT-4)
   - Compare latency vs quality tradeoff

**Deliverables**:
- [ ] Sensor analysis accurate and useful
- [ ] LLM provides actionable insights
- [ ] Prompts refined based on testing
- [ ] Latency acceptable (< 2 seconds)

---

## PHASE 5: GPIO Control (Week 5)
### Goal: Voice commands can control local hardware

#### Week 5.2: Intent Parser & Control System (15 hours)

**Tasks**:
1. **Implement `voice/intent_parser.py`**
   ```python
   class IntentParser:
       def parse(self, transcription):
           """Parse natural language to intent"""
           # Keyword matching
           # Return: {type, action, target, confidence}
           pass

   # Examples:
   # "Turn on the RGB LED" → {type: 'gpio_control', action: 'on', target: 'rgb_led'}
   # "What's the temperature?" → {type: 'query_sensor', target: 'dht11'}
   ```

2. **Define controllable devices**
   - RGB LED (on/off, color selection)
   - Buzzer (on/off, frequency/duration)
   - Future: relays, fans, lights

3. **Implement GPIO control in assistant**
   ```python
   def _execute_gpio_control(self, intent):
       device = intent.get('target')
       action = intent.get('action')

       # Import sensor module dynamically
       # Execute control
       # Return confirmation
   ```

4. **Add safety checks**
   - Only allow whitelisted devices
   - Duration limits for outputs (e.g., max 1 min buzzer)
   - Require confirmation for dangerous actions (if any)

5. **Test voice control**
   - "Turn on the RGB LED"
   - "Beep the buzzer"
   - Verify actions execute correctly
   - Provide voice feedback

**Deliverables**:
- [ ] Intent parser recognizes GPIO commands
- [ ] Safety checks prevent misuse
- [ ] Voice control executes actions reliably
- [ ] Feedback (voice + GUI) confirms action
- [ ] Test: 10 GPIO commands, all execute correctly

---

## PHASE 6: Polish & Production (Week 6)
### Goal: Production-ready, well-documented system

#### Week 6.1-6.2: Testing & Debugging (20 hours)

**Tasks**:
1. **Comprehensive unit tests**
   ```bash
   pytest voice/tests/
   pytest vps/tests/
   # Aim for >80% code coverage
   ```

2. **Integration tests**
   - Full end-to-end voice command
   - Network failure recovery
   - Memory leak detection (run 1 hour, check /proc/meminfo)
   - CPU usage profiling

3. **Hardware stress tests**
   - 100 rapid voice commands
   - Mixed: voice commands + sensor polling + GUI updates
   - Network dropout + recovery

4. **Error message quality**
   - User-friendly, not cryptic
   - Helpful suggestions for fixing issues
   - Logged details for debugging

**Deliverables**:
- [ ] Unit test suite passing (pytest)
- [ ] Integration tests passing
- [ ] No memory leaks detected
- [ ] CPU usage < 50% peak
- [ ] Error messages helpful

---

#### Week 6.3: Documentation & Deployment (15 hours)

**Tasks**:
1. **Write setup guides**
   - SETUP_AUDIO_HARDWARE.md (hardware connection)
   - SETUP_PICOVOICE.md (wake word configuration)
   - SETUP_VPS.md (VPS backend setup)
   - SETUP_SSH_TUNNEL.md (reverse tunnel)
   - VOICE_API_SPEC.md (API reference)
   - TROUBLESHOOTING.md (common issues + fixes)

2. **Create deployment scripts**
   - Auto-install dependencies
   - Configure systemd services
   - Validate setup (health checks)

3. **Write user documentation**
   - Voice commands examples
   - Limitations + known issues
   - Tips for best results

4. **Create monitoring dashboard** (optional)
   - systemctl status overview
   - journalctl follow for logs
   - CPU/memory/network graphs

**Deliverables**:
- [ ] All documentation complete and tested
- [ ] Deployment script automated
- [ ] User can follow guide and get working system
- [ ] Troubleshooting guide covers 90% of issues

---

#### Week 6.4: Rollout & Monitoring (10 hours)

**Tasks**:
1. **Staging deployment**
   - Deploy to test VPS environment
   - Run 24-hour smoke test
   - Verify all alerts working

2. **Production deployment**
   - Enable services on VPS + Pi
   - Monitor logs for 1 hour
   - Run sanity tests

3. **Performance baseline**
   - Document typical latency (8-12s)
   - Document memory usage (~615MB)
   - Document network throughput (avg 1 kbps idle)

4. **Set up monitoring**
   - CPU/memory alerts (>80%)
   - Network latency alerts (>20s)
   - Error rate tracking
   - Weekly log rotation

**Deliverables**:
- [ ] System deployed and running
- [ ] Monitoring active and alerting correctly
- [ ] Performance baseline established
- [ ] Documentation reflects actual behavior
- [ ] Team trained on operation

---

## PHASE 7: Future Enhancements (Week 7+)

### Multi-Turn Conversations
```
Phase 7.1: Context persistence (2 weeks)
- Remember recent queries
- Support follow-up questions
- Maintain conversation history
```

### Advanced Sensor Features
```
Phase 7.2: Predictive analytics (2 weeks)
- Predict when temperature will exceed threshold
- Alert on anomalies (sensor malfunction detection)
- Correlate sensor data (humidity + temperature)
```

### Expanded Control
```
Phase 7.3: Automation & scenes (3 weeks)
- Define scenes ("Goodnight" → turn off lights, close windows, set temp)
- Time-based automation ("7am → increase heat")
- Integration with smart devices (if available)
```

### Mobile App
```
Phase 7.4: Remote access (4 weeks)
- Smartphone app for voice commands
- Remote sensor monitoring
- Notifications for alerts
- Historical data visualization
```

---

## RISK MITIGATION

| Risk | Mitigation Strategy |
|------|-------------------|
| Porcupine false positives | Sensitivity tuning + secondary confirmation |
| Network latency spikes | Adaptive timeout + fallback responses |
| STT API quota exceeded | Rate limiting + local fallback + caching |
| Memory exhaustion | Streaming audio (not buffering) + process monitoring |
| SSH tunnel dropout | Systemd auto-restart + keepalive timeout |
| Thread synchronization bugs | Mutex-protected state + comprehensive testing |
| Hardware compatibility issues | Test on actual Pi 3B+ before production |
| Audio quality issues | USB adapter troubleshooting guide |

---

## SUCCESS CRITERIA (By End of Week 6)

- [ ] **Accuracy**: Wake word detected 9/10 times, <1% false positives
- [ ] **Latency**: Full voice command processed in 8-15 seconds
- [ ] **Reliability**: 99.9% uptime over 7-day test (no crashes)
- [ ] **Memory**: Stable at 615MB, no leaks over 24 hours
- [ ] **Network**: Works with typical home WiFi (>5 Mbps)
- [ ] **GUI**: Sensor dashboard fully functional alongside voice
- [ ] **User Experience**: Clear feedback for every action
- [ ] **Documentation**: User can deploy without expert help
- [ ] **Testing**: Unit + integration tests passing (>80% coverage)
- [ ] **Monitoring**: Automated alerts for critical issues

---

## CHECKPOINT MILESTONES

**End of Phase 1 (Week 2)**:
- Pi listening for wake word
- Audio input/output working
- No breaking changes to GUI

**End of Phase 2 (Week 3)**:
- VPS processing audio (STT + LLM + TTS)
- HTTP endpoints functional
- Response latency acceptable

**End of Phase 3 (Week 4)**:
- Full voice pipeline end-to-end
- SSH tunnel stable
- RPC client robust (handles errors)

**End of Phase 4 (Week 5)**:
- Sensor analysis working
- LLM provides useful insights
- GPIO control functional

**End of Phase 6 (Week 6)**:
- Production deployment complete
- All documentation written
- Monitoring operational
- User training done

---

## TIME ESTIMATES

| Phase | Duration | Hours | Key Deliverable |
|-------|----------|-------|-----------------|
| 1: Audio | Weeks 1-2 | 60h | Wake word detection |
| 2: VPS | Weeks 2-3 | 50h | STT + LLM + TTS |
| 3: Comm | Weeks 3-4 | 40h | Pi ↔ VPS stable |
| 4: Sensors | Weeks 4-5 | 35h | LLM sensor analysis |
| 5: GPIO | Week 5 | 15h | Voice control |
| 6: Polish | Week 6 | 45h | Production-ready |
| **TOTAL** | **6 weeks** | **245h** | **Deployable system** |

*(Part-time: ~40h/week = 6-8 weeks calendar time)*

---

## CONTACT & SUPPORT

**Documentation Location**: `/home/coolhand/projects/sensor-playground-mirror/`
- `HOME_ASSISTANT_ARCHITECTURE.md` — Full architecture
- `ARCHITECTURE_DIAGRAMS.md` — Visual reference
- `IMPLEMENTATION_ROADMAP.md` — This document

**Issues & Questions**:
1. Check TROUBLESHOOTING.md first
2. Review relevant architecture doc section
3. Check logs: `journalctl -u sensor-playground -f`
4. Verify hardware: `arecord -l`, `aplay -l`, `free -h`

---

**Status**: Ready to begin Phase 1
**Last Updated**: 2026-02-11
**Version**: 1.0
