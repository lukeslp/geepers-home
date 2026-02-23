# Raspberry Pi Sensor Playground - Software Development Continuation

## Current Project Status

### Hardware Configuration
**Core System:**
- Raspberry Pi 3B+ with Freenove 7" touchscreen (working, DSI connection)
- Running Raspberry Pi OS (recent install)
- Power supply: adequate for Pi + sensors
- Location: `~/sensor-playground/`

**Sensors Confirmed Wired:**
1. **DHT11** (temperature/humidity) - GPIO 4 - **WORKING**
2. **Unknown Sensor #1** - Has DO pin, blue potentiometer, button-like component (likely knock/tap sensor)
3. **Unknown Sensor #2** - Has DO pin, blue potentiometer, photoresistor visible (likely light threshold sensor)

**Sensors Available (37-in-1 kit, unwired):**
- PIR motion sensor (HC-SR501, dome-shaped)
- Tilt switch (metal ball switch)
- Sound sensor (microphone module, analog or digital)
- Photoresistor (light-dependent resistor, needs ADC)
- Soil moisture sensors (5x units, analog)
- Reed switch (magnetic)
- Hall effect sensor (magnetic)
- Flame sensor
- IR receiver/transmitter
- Joystick module
- Relay modules
- RGB LED module
- OLED display (0.96", I²C)
- Buzzer (active/passive)
- Button modules
- Heartbeat sensor
- Temperature sensors (analog + DS18B20)
- Many others

**Communication Hardware (for future phases):**
- RS485 CAN HAT (not installed yet)
- HC-05 Bluetooth module (not wired)
- ArduCam 5MP camera (not connected)
- Two 8Ω speakers with JST connectors

### Software Status

**GUI Application Running:**
- Multi-sensor touchscreen interface operational
- Location: `~/sensor-playground/sensor_gui.py` (assumed location)
- Full-screen tkinter application

**Visible GUI Elements (from screenshot):**
- Top bar: "SENSOR PLAYGROUND" title
- Control buttons: DEMO, LOG, EXIT
- Sensor tabs: DHT11, PIR, Tilt, Sound, INFO
- Left panel: "Temperature & Humidity" section with live readings display
- Right panel: "Readings" area (appears to be for graphs/data visualization)
- Status bar at bottom
- Color scheme: Blue/cyan UI on dark background

**Known Working Features:**
- DHT11 sensor reading (temperature/humidity display visible)
- Tab switching interface
- Touch interaction
- Real-time updates ("LIVE" indicator visible)

**Unknown Implementation Details:**
- GPIO pin assignments for mystery sensors
- Whether data logging is implemented
- Graph/visualization implementation status
- Sensor reading frequency
- Error handling robustness

### Python Dependencies Installed
```bash
# Confirmed installed:
adafruit-circuitpython-dht  # DHT11 sensor
python3-pil                  # GUI imaging
python3-pil.imagetk          # Tkinter image support
libgpiod2                    # GPIO access

# May be installed (unknown):
RPi.GPIO                     # Alternative GPIO library
adafruit-circuitpython-ssd1306  # For OLED (if planned)
```

---

## Immediate Tasks

### Phase 1: System Audit & Sensor Identification

**Task 1.1: Locate and Review Existing Code**

```bash
# Find all Python files in the project
find ~/sensor-playground -name "*.py" -type f

# Review main GUI code
cat ~/sensor-playground/sensor_gui.py

# Check for other modules
ls -la ~/sensor-playground/
```

**Needed Information:**
- Exact GPIO pin assignments in current code
- Which library is being used (RPi.GPIO vs adafruit_blinka)
- Current sensor class structure
- How tabs are implemented
- Data storage/logging implementation
- Update frequency/threading model

**Task 1.2: Identify Mystery Sensors**

Create diagnostic script to determine:
- Which GPIO pins the two unknown sensors are connected to
- What their digital output behavior is
- Which sensor is which based on physical interaction

**Diagnostic Script Template:**

```python
#!/usr/bin/env python3
"""
Sensor Identification Utility
Tests all likely GPIO pins to find connected sensors
"""

import RPi.GPIO as GPIO
import time
import sys

# Common GPIO pins to test (avoid I2C, SPI, UART, known DHT11 on GPIO4)
TEST_PINS = [17, 18, 22, 23, 24, 25, 27]

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

def test_pins():
    """Test each pin for activity"""
    print("Sensor Detection Utility")
    print("=" * 60)
    print("Watching for digital sensor activity...")
    print("Try: tap sensors, shine light, make noise, create motion")
    print("Press Ctrl+C to exit\n")

    # Setup all test pins as inputs with pull-down
    for pin in TEST_PINS:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    # Track state changes
    previous_states = {pin: GPIO.input(pin) for pin in TEST_PINS}

    try:
        while True:
            for pin in TEST_PINS:
                current_state = GPIO.input(pin)
                if current_state != previous_states[pin]:
                    timestamp = time.strftime("%H:%M:%S")
                    print(f"[{timestamp}] GPIO {pin:2d}: {previous_states[pin]} → {current_state}")
                    previous_states[pin] = current_state

            time.sleep(0.05)  # 50ms polling

    except KeyboardInterrupt:
        print("\n\nDetection complete")
        print("\nFinal pin states:")
        for pin in TEST_PINS:
            state = GPIO.input(pin)
            print(f"  GPIO {pin:2d}: {'HIGH' if state else 'LOW'}")
        GPIO.cleanup()

if __name__ == "__main__":
    test_pins()
```

**Expected Output:**
- GPIO pins that show state changes when sensors are triggered
- Mapping of physical sensors to GPIO pins

**Task 1.3: Document Current Wiring**

Create wiring map:
```
Current GPIO Allocation:
├── GPIO 4  → DHT11 (DATA pin) - Temperature/Humidity
├── GPIO ?? → Unknown Sensor 1 (DO pin) - Light or Knock?
├── GPIO ?? → Unknown Sensor 2 (DO pin) - Light or Knock?
└── GPIO 2/3 → Reserved for I²C (SDA/SCL)
```

---

### Phase 2: Code Audit & Refactoring

**Task 2.1: Analyze Existing GUI Architecture**

Questions to answer:
1. **Tab implementation**: How are sensor views switched?
2. **Sensor reading**: Threaded? main loop? Event-driven?
3. **Data structure**: How is sensor data stored/passed?
4. **Graph implementation**: Is it functional? What library?
5. **Logging**: Is LOG button functional? Where does data go?
6. **Error handling**: What happens when sensor fails?

**Task 2.2: Identify Gaps/Issues**

Common problems to look for:
- Blocking sensor reads freezing GUI
- DHT11 read failures not handled gracefully
- GPIO cleanup on exit
- Thread safety if multi-threaded
- Hardcoded values vs configurable
- No sensor abstraction layer

**Task 2.3: Propose Architecture Improvements**

Recommended structure:
```
sensor-playground/
├── sensor_gui.py          # Main GUI (existing)
├── sensors/               # NEW: Sensor modules
│   ├── __init__.py
│   ├── base.py           # Base sensor class
│   ├── dht11.py          # DHT11 wrapper
│   ├── digital.py        # Generic digital sensor
│   └── analog.py         # Future: ADC sensors
├── ui/                    # NEW: UI components
│   ├── __init__.py
│   ├── sensor_tab.py     # Reusable sensor tab
│   └── graph.py          # Graphing utilities
├── data/                  # Data storage
│   └── logs/             # CSV logs
└── config.py             # NEW: Configuration
```

---

### Phase 3: Extend Functionality

**Task 3.1: Complete Mystery Sensor Integration**

Once identified, update GUI:
1. Update tab names to match actual sensors
2. Implement proper sensor reading for each
3. Add sensitivity indicator (potentiometer position affects threshold)
4. Add appropriate visualization (boolean state, history, etc.)

**Task 3.2: Wire Additional Sensors**

Priority order (easiest to hardest):
1. **PIR Motion Sensor** (HC-SR501)
   - 3 pins: VCC (5V), GND, OUT
   - Simple HIGH/LOW digital output
   - Wire to available GPIO (suggest 17 if free)
   - Add "Motion Detected" indicator to GUI

2. **Tilt Switch**
   - 3 pins: VCC, GND, DO
   - HIGH when upright, LOW when tilted (or inverse)
   - Wire to available GPIO (suggest 22 if free)
   - Add orientation display to GUI

3. **Button/Touch Module**
   - 3 pins: VCC, GND, SIG
   - Manual trigger for testing
   - Add button press counter

4. **RGB LED Module**
   - 4 pins: R, G, B, GND (or common anode)
   - Use as visual indicator for sensor states
   - Wire to GPIOs 23, 24, 25

5. **OLED Display** (I²C, 0.96")
   - 4 pins: VCC (3.3V), GND, SCL, SDA
   - Wire to GPIO 2 (SDA), GPIO 3 (SCL)
   - Display current sensor name + value
   - Requires: `pip3 install adafruit-circuitpython-ssd1306`

**GPIO Pin Allocation Strategy:**
```
Reserved/Used:
- GPIO 2, 3: I²C (SDA, SCL) for OLED
- GPIO 4: DHT11 DATA
- GPIO 14, 15: UART (for future HC-05 Bluetooth)

Available for Digital Sensors:
- GPIO 17, 18, 22, 23, 24, 25, 27
- Total: 7 pins available

Proposed Assignment:
- GPIO 17: PIR motion sensor
- GPIO 22: Tilt switch
- GPIO 23: RGB LED - Red
- GPIO 24: RGB LED - Green
- GPIO 25: RGB LED - Blue
- GPIO 27: Button/touch module
- GPIO 18: Reserved for future sensor
```

**Task 3.3: Implement Data Visualization**

The "Readings" panel needs:
1. **Real-time line graph** (temperature/humidity trends)
2. **Digital state indicators** (boolean sensors: motion, tilt, etc.)
3. **Historical data view** (last N readings)
4. **Min/Max/Average statistics**

**Graph Implementation Options:**
- **matplotlib** (familiar, feature-rich, but slower)
- **tkinter Canvas** (lightweight, fast, already used)
- **Plotly** (interactive, but overkill for embedded)

**Recommendation**: Use tkinter Canvas for speed on Pi.

**Task 3.4: Implement Data Logging**

LOG button functionality:
1. **Start/Stop toggle** (button state changes)
2. **CSV output** format:
   ```
   Timestamp,Sensor,Value,Unit
   2026-02-09 14:23:45,DHT11_Temp,22.4,C
   2026-02-09 14:23:45,DHT11_Humidity,45,percent
   2026-02-09 14:23:47,PIR_Motion,1,boolean
   ```
3. **File naming**: `sensor_log_YYYYMMDD_HHMMSS.csv`
4. **Location**: `~/sensor-playground/data/logs/`
5. **Status indicator**: Show logging state, file size, record count

**Task 3.5: DEMO Mode**

DEMO button should:
1. **Simulate sensor data** (useful for testing GUI without hardware)
2. **Auto-cycle through sensor tabs** (kiosk mode)
3. **Generate realistic random data** within sensor ranges
4. **Visual indicator** that system is in demo mode

---

### Phase 4: Code Quality & Robustness

**Task 4.1: Error Handling**

Implement:
- **Graceful sensor failures** (DHT11 often fails, retry logic)
- **GPIO cleanup on all exit paths**
- **Display error messages on GUI** (not just console)
- **Sensor connection detection** (warn if sensor disconnected)

**Task 4.2: Configuration System**

Create `config.py`:
```python
"""
Sensor Playground Configuration
"""

# GPIO Pin Assignments
GPIO_DHT11 = 4
GPIO_PIR = 17
GPIO_TILT = 22
GPIO_SOUND = 27
GPIO_RGB_R = 23
GPIO_RGB_G = 24
GPIO_RGB_B = 25

# I2C Devices
I2C_OLED_ADDRESS = 0x3C

# Sensor Settings
DHT11_READ_INTERVAL = 2.0  # seconds
DIGITAL_POLL_INTERVAL = 0.1  # seconds

# GUI Settings
GRAPH_MAX_POINTS = 100
LOG_DIRECTORY = "data/logs"
FULLSCREEN = True

# Data Ranges (for visualization)
TEMP_MIN = 0
TEMP_MAX = 50
HUMIDITY_MIN = 0
HUMIDITY_MAX = 100
```

**Task 4.3: Code Documentation**

Add to all files:
- **Banner comment** with file purpose, functions, I/O
- **Docstrings** for all classes and functions
- **Inline comments** for complex logic
- **Type hints** where appropriate (Python 3.5+)

---

## Technical Constraints & Guidelines

### Hardware Limitations
- **Pi 3.3V GPIO logic** - never send 5V signals to GPIO input pins
- **DHT11 minimum interval** - 2 seconds between reads (sensor limitation)
- **Total GPIO current** - max 50mA across all pins
- **SD card writes** - minimize to prevent corruption (batch logging)

### Software Requirements
- **Python 3.7+** (Raspberry Pi OS default)
- **No external dependencies** unless necessary
- **Graceful degradation** - GUI works even if sensors fail
- **Touch-friendly UI** - large buttons, no tiny controls
- **Responsive interface** - never block on sensor reads

### Code Style
- **Direct, no fluff** - solution first, context second
- **Complete files** - no truncated snippets
- **Runnable examples** - include all imports, error handling
- **Verification steps** - tell user what to expect at each stage
- **Markdown formatting** - structured, clear headers

---

## Deliverables

### Immediate (Phase 1-2)
1. **Sensor identification report** - GPIO pin mapping for all connected sensors
2. **Code audit document** - current architecture, gaps, recommendations
3. **Updated sensor_gui.py** - bug fixes, proper sensor integration

### Short-term (Phase 3)
1. **Multi-sensor GUI** - 5+ sensors working with proper visualization
2. **Data logging system** - functional LOG button, CSV output
3. **Graph implementation** - real-time visualization in "Readings" panel
4. **OLED display integration** - secondary output device

### Medium-term (Phase 4)
1. **Configuration system** - centralized settings
2. **Error handling** - robust failure recovery
3. **Documentation** - comprehensive code comments, usage guide

---

## Questions for Current Agent

Before proceeding, confirm:

1. **What is the exact content of `sensor_gui.py`?** (paste full file or upload)
2. **Which GPIO pins did you wire the two mystery sensors to?** (physical pin numbers or GPIO numbers)
3. **Do you want to focus on:**
   - Identifying and fixing current sensors first? OR
   - Adding new sensors immediately? OR
   - Refactoring code architecture first?
4. **Priority: functionality or code quality?** (quick expansion vs clean architecture)
5. **Do you want the OLED display integrated soon?** (requires I²C setup)

---

## Success Criteria

By completion of immediate phases:
- ✓ All wired sensors identified and working
- ✓ GUI accurately displays all sensor data
- ✓ Data logging functional
- ✓ Real-time graphs showing trends
- ✓ Touch interface fully responsive
- ✓ 5+ sensors integrated simultaneously
- ✓ Code is maintainable and documented

Begin with sensor identification, then proceed to code audit and expansion.
