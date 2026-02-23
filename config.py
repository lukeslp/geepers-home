"""Sensor Playground - Configuration

Pin numbers use BCM (Broadcom) numbering scheme.
Physical pin numbers noted in comments for cross-reference.

BCM-to-Physical pin mapping for pins we use:
  BCM 4  = Physical Pin 7   (DHT11 data)
  BCM 5  = Physical Pin 29  (Knock/vibration)
  BCM 6  = Physical Pin 31  (Light threshold)
  BCM 12 = Physical Pin 32  (DS18B20 1-Wire)
  BCM 13 = Physical Pin 33  (RGB LED red)
  BCM 16 = Physical Pin 36  (Reed switch)
  BCM 17 = Physical Pin 11  (PIR output)
  BCM 18 = Physical Pin 12  (Joystick button)
  BCM 19 = Physical Pin 35  (RGB LED green)
  BCM 20 = Physical Pin 38  (Hall effect)
  BCM 21 = Physical Pin 40  (RGB LED blue)
  BCM 22 = Physical Pin 15  (Sound digital out)
  BCM 23 = Physical Pin 16  (Buzzer)
  BCM 24 = Physical Pin 18  (Flame sensor)
  BCM 25 = Physical Pin 22  (Touch sensor)
  BCM 26 = Physical Pin 37  (Button)
  BCM 27 = Physical Pin 13  (Tilt signal)

Pins to AVOID (reserved for buses):
  BCM 2/3   = I2C (SDA/SCL) - Physical 3/5
  BCM 7-11  = SPI            - Physical 26/24/21/19/23
  BCM 14/15 = UART (TX/RX)  - Physical 8/10

Free GPIOs after full expansion: BCM 0, 1 (2 pins)
"""

# ---------------------------------------------------------------------------
# Categories — groups sensors into navigable sections
# ---------------------------------------------------------------------------
CATEGORIES = {
    "environment": {
        "label": "Environment",
        "color": "#00b894",
    },
    "motion": {
        "label": "Motion",
        "color": "#fdcb6e",
    },
    "light_ir": {
        "label": "Light & IR",
        "color": "#ffeaa7",
    },
    "sound_vibration": {
        "label": "Sound",
        "color": "#a29bfe",
    },
    "output": {
        "label": "Output",
        "color": "#e17055",
    },
    "analog": {
        "label": "Analog",
        "color": "#74b9ff",
    },
}

# ---------------------------------------------------------------------------
# Sensor definitions
# ---------------------------------------------------------------------------
SENSORS = {
    # === ENVIRONMENT ===
    "dht11": {
        "label": "DHT11",
        "description": "Temperature & Humidity",
        "category": "environment",
        "pin": 4,               # BCM 4 = Physical Pin 7
        "interval_ms": 2500,    # DHT11 needs >= 1s between reads; 2.5s is safe
        "fields": {
            "temperature": {
                "label": "Temperature",
                "unit": "\u00b0C",
                "color": "#ff6b6b",
                "graph_mode": "line",
            },
            "humidity": {
                "label": "Humidity",
                "unit": "%",
                "color": "#4ecdc4",
                "graph_mode": "line",
            },
        },
        "wiring": [
            "VCC  \u2192  Pin 1  (3.3V)",
            "DATA \u2192  Pin 7  (GPIO 4)",
            "GND  \u2192  Pin 9  (Ground)",
        ],
        "notes": "Uses 3 female-to-female jumper wires. Module has built-in pull-up resistor.",
    },
    "ds18b20": {
        "label": "DS18B20",
        "description": "External Temperature",
        "category": "environment",
        "pin": 12,              # BCM 12 = Physical Pin 32 (1-Wire data)
        "interval_ms": 1000,
        "fields": {
            "ext_temperature": {
                "label": "Temperature",
                "unit": "\u00b0C",
                "color": "#e17055",
                "graph_mode": "line",
            },
        },
        "wiring": [
            "VCC  \u2192  Pin 1  (3.3V)",
            "DATA \u2192  Pin 32 (GPIO 12)",
            "GND  \u2192  Pin 34 (Ground)",
        ],
        "notes": "Needs dtoverlay=w1-gpio,gpiopin=12 in /boot/config.txt + reboot. 4.7k pull-up on DATA to 3.3V.",
    },
    "soil_moisture": {
        "label": "Soil",
        "description": "Soil Moisture",
        "category": "environment",
        "pin": -1,
        "adc_channel": 2,
        "interval_ms": 2000,
        "fields": {
            "moisture": {
                "label": "Moisture",
                "unit": "%",
                "color": "#55a630",
                "graph_mode": "line",
            },
        },
        "wiring": [
            "VCC \u2192  ADS1115 VDD (3.3V)",
            "AO  \u2192  ADS1115 A2",
            "GND \u2192  ADS1115 GND",
        ],
        "notes": "Capacitive sensor. Lower voltage = wetter soil. Requires ADS1115 ADC.",
    },

    # === MOTION ===
    "pir": {
        "label": "PIR",
        "description": "Motion Detection",
        "category": "motion",
        "pin": 17,              # BCM 17 = Physical Pin 11
        "interval_ms": 200,
        "fields": {
            "motion": {
                "label": "Motion",
                "unit": "",
                "color": "#ffd93d",
                "graph_mode": "step",
            },
        },
        "wiring": [
            "VCC \u2192  Pin 2  (5V)",
            "OUT \u2192  Pin 11 (GPIO 17)",
            "GND \u2192  Pin 14 (Ground)",
        ],
        "notes": "Needs 5V. Two pots on board: sensitivity (left) and hold time (right).",
    },
    "tilt": {
        "label": "Tilt",
        "description": "Tilt Switch",
        "category": "motion",
        "pin": 27,              # BCM 27 = Physical Pin 13
        "interval_ms": 200,
        "fields": {
            "tilted": {
                "label": "Tilted",
                "unit": "",
                "color": "#6c5ce7",
                "graph_mode": "step",
            },
        },
        "wiring": [
            "S (Signal) \u2192  Pin 13 (GPIO 27)",
            "+  (VCC)   \u2192  Pin 17 (3.3V)",
            "-  (GND)   \u2192  Pin 20 (Ground)",
        ],
        "notes": "Contains a metal ball that rolls to make/break contact.",
    },
    "reed": {
        "label": "Reed",
        "description": "Magnetic Switch",
        "category": "motion",
        "pin": 16,              # BCM 16 = Physical Pin 36
        "interval_ms": 200,
        "fields": {
            "magnet": {
                "label": "Magnet",
                "unit": "",
                "color": "#fd79a8",
                "graph_mode": "step",
            },
        },
        "wiring": [
            "S (Signal) \u2192  Pin 36 (GPIO 16)",
            "+  (VCC)   \u2192  Pin 17 (3.3V)",
            "-  (GND)   \u2192  Pin 39 (Ground)",
        ],
        "notes": "Glass tube with ferromagnetic contacts. Magnet closes the switch.",
    },
    "hall": {
        "label": "Hall",
        "description": "Hall Effect",
        "category": "motion",
        "pin": 20,              # BCM 20 = Physical Pin 38
        "interval_ms": 200,
        "fields": {
            "magnetic": {
                "label": "Magnetic",
                "unit": "",
                "color": "#00cec9",
                "graph_mode": "step",
            },
        },
        "wiring": [
            "S (Signal) \u2192  Pin 38 (GPIO 20)",
            "+  (VCC)   \u2192  Pin 17 (3.3V)",
            "-  (GND)   \u2192  Pin 20 (Ground)",
        ],
        "notes": "Detects magnetic field. Module goes LOW when magnet is near.",
    },
    "touch": {
        "label": "Touch",
        "description": "Capacitive Touch",
        "category": "motion",
        "pin": 25,              # BCM 25 = Physical Pin 22
        "interval_ms": 100,
        "fields": {
            "touched": {
                "label": "Touched",
                "unit": "",
                "color": "#e84393",
                "graph_mode": "step",
            },
        },
        "wiring": [
            "SIG \u2192  Pin 22 (GPIO 25)",
            "VCC \u2192  Pin 17 (3.3V)",
            "GND \u2192  Pin 25 (Ground)",
        ],
        "notes": "TTP223 touch sensor. Active-high output. ~60ms response time.",
    },
    "button": {
        "label": "Button",
        "description": "Push Button",
        "category": "motion",
        "pin": 26,              # BCM 26 = Physical Pin 37
        "interval_ms": 50,
        "fields": {
            "pressed": {
                "label": "Pressed",
                "unit": "",
                "color": "#636e72",
                "graph_mode": "step",
            },
        },
        "wiring": [
            "S (Signal) \u2192  Pin 37 (GPIO 26)",
            "+  (VCC)   \u2192  Pin 17 (3.3V)",
            "-  (GND)   \u2192  Pin 30 (Ground)",
        ],
        "notes": "Momentary push button. Built-in pull-up and debounce cap.",
    },

    # === LIGHT & IR ===
    "light": {
        "label": "Light",
        "description": "Light Threshold",
        "category": "light_ir",
        "pin": 6,               # BCM 6 = Physical Pin 31
        "interval_ms": 300,
        "fields": {
            "dark": {
                "label": "Dark",
                "unit": "",
                "color": "#ffeaa7",
                "graph_mode": "step",
            },
        },
        "wiring": [
            "DO (Digital Out) \u2192  Pin 31 (GPIO 6)",
            "+  (VCC)         \u2192  Pin 2  (5V)",
            "G  (GND)         \u2192  Pin 9  (Ground)",
        ],
        "notes": "LDR + LM393 comparator. Adjust pot to set dark/light threshold.",
    },
    "flame": {
        "label": "Flame",
        "description": "Flame Detection",
        "category": "light_ir",
        "pin": 24,              # BCM 24 = Physical Pin 18
        "interval_ms": 100,
        "fields": {
            "flame": {
                "label": "Flame",
                "unit": "",
                "color": "#e17055",
                "graph_mode": "step",
            },
        },
        "wiring": [
            "DO (Digital Out) \u2192  Pin 18 (GPIO 24)",
            "+  (VCC)         \u2192  Pin 17 (3.3V)",
            "G  (GND)         \u2192  Pin 14 (Ground)",
        ],
        "notes": "IR flame detector. Module goes LOW on flame (inverted in code). ~80cm range.",
    },
    "light_analog": {
        "label": "Light Lvl",
        "description": "Light Level (Analog)",
        "category": "light_ir",
        "pin": -1,
        "adc_channel": 1,
        "interval_ms": 300,
        "fields": {
            "light_level": {
                "label": "Light Level",
                "unit": "%",
                "color": "#feca57",
                "graph_mode": "line",
            },
        },
        "wiring": [
            "AO  \u2192  ADS1115 A1",
            "VCC \u2192  ADS1115 VDD (3.3V)",
            "GND \u2192  ADS1115 GND",
        ],
        "notes": "Continuous light level via ADC. Requires ADS1115.",
    },

    # === SOUND & VIBRATION ===
    "sound": {
        "label": "Sound",
        "description": "Sound Detection",
        "category": "sound_vibration",
        "pin": 22,              # BCM 22 = Physical Pin 15
        "interval_ms": 100,
        "fields": {
            "sound": {
                "label": "Sound",
                "unit": "",
                "color": "#a29bfe",
                "graph_mode": "step",
            },
        },
        "wiring": [
            "DO (Digital Out) \u2192  Pin 15 (GPIO 22)",
            "+  (VCC)         \u2192  Pin 4  (5V)",
            "G  (GND)         \u2192  Pin 6  (Ground)",
        ],
        "notes": "Adjust blue pot to set threshold. DO goes HIGH when sound exceeds threshold.",
    },
    "knock": {
        "label": "Knock",
        "description": "Vibration Detection",
        "category": "sound_vibration",
        "pin": 5,               # BCM 5 = Physical Pin 29
        "interval_ms": 100,
        "fields": {
            "vibration": {
                "label": "Vibration",
                "unit": "",
                "color": "#fd79a8",
                "graph_mode": "step",
            },
        },
        "wiring": [
            "DO (Digital Out) \u2192  Pin 29 (GPIO 5)",
            "+  (VCC)         \u2192  Pin 4  (5V)",
            "G  (GND)         \u2192  Pin 25 (Ground)",
        ],
        "notes": "SW-420 vibration switch. Adjust pot for sensitivity. Detects knocks, taps, footsteps.",
    },
    "sound_analog": {
        "label": "Sound Lvl",
        "description": "Sound Level (Analog)",
        "category": "sound_vibration",
        "pin": -1,
        "adc_channel": 0,
        "interval_ms": 100,
        "fields": {
            "sound_level": {
                "label": "Sound Level",
                "unit": "%",
                "color": "#6c5ce7",
                "graph_mode": "line",
            },
        },
        "wiring": [
            "AO  \u2192  ADS1115 A0",
            "VCC \u2192  ADS1115 VDD (5V)",
            "GND \u2192  ADS1115 GND",
        ],
        "notes": "Continuous sound level via ADC. Requires ADS1115.",
    },

    # === OUTPUT DEVICES ===
    "rgb_led": {
        "label": "RGB LED",
        "description": "RGB LED Control",
        "category": "output",
        "pin": 13,              # BCM 13 = Physical Pin 33 (Red)
        "extra_pins": [19, 21], # Green = BCM 19 (Pin 35), Blue = BCM 21 (Pin 40)
        "interval_ms": 500,
        "fields": {
            "color": {
                "label": "Color",
                "unit": "",
                "color": "#e17055",
                "graph_mode": "step",
            },
        },
        "wiring": [
            "R \u2192  Pin 33 (GPIO 13)",
            "G \u2192  Pin 35 (GPIO 19)",
            "B \u2192  Pin 40 (GPIO 21)",
            "- \u2192  Pin 34 (Ground)",
        ],
        "notes": "Common cathode RGB LED. Each pin controls one color. 220\u03a9 resistor per channel.",
    },
    "buzzer": {
        "label": "Buzzer",
        "description": "Active Buzzer",
        "category": "output",
        "pin": 23,              # BCM 23 = Physical Pin 16
        "interval_ms": 500,
        "fields": {
            "buzzing": {
                "label": "Buzzing",
                "unit": "",
                "color": "#fdcb6e",
                "graph_mode": "step",
            },
        },
        "wiring": [
            "S (Signal) \u2192  Pin 16 (GPIO 23)",
            "+  (VCC)   \u2192  Pin 2  (5V)",
            "-  (GND)   \u2192  Pin 6  (Ground)",
        ],
        "notes": "Active buzzer — has built-in oscillator. HIGH = on, LOW = off.",
    },

    # === ANALOG (requires ADS1115 ADC) ===
    "joystick": {
        "label": "Joystick",
        "description": "Analog Joystick",
        "category": "analog",
        "pin": -1,
        "adc_channel": 3,
        "extra_pins": [18],     # Button on BCM 18 = Physical Pin 12
        "interval_ms": 100,
        "fields": {
            "joy_x": {
                "label": "X Position",
                "unit": "%",
                "color": "#74b9ff",
                "graph_mode": "line",
            },
            "joy_button": {
                "label": "Button",
                "unit": "",
                "color": "#636e72",
                "graph_mode": "step",
            },
        },
        "wiring": [
            "VRx \u2192  ADS1115 A3",
            "SW  \u2192  Pin 12 (GPIO 18)",
            "+5V \u2192  Pin 2  (5V)",
            "GND \u2192  Pin 6  (Ground)",
        ],
        "notes": "X-axis via ADC, button via GPIO. Push stick down to press button. Requires ADS1115.",
    },

    # === WAVESHARE ENVIRONMENT HAT (I2C) ===
    "tsl25911": {
        "label": "Light",
        "description": "TSL25911 Light & IR",
        "category": "light_ir",
        "pin": 29,
        "interval_ms": 1000,
        "fields": {
            "lux": {"label": "Lux", "unit": "lux", "color": "#f1c40f", "graph_mode": "line"},
        },
    },
    "bme280": {
        "label": "BME280",
        "description": "Temp/Humidity/Pressure",
        "category": "environment",
        "pin": 76,
        "interval_ms": 2000,
        "fields": {
            "temperature": {"label": "Temperature", "unit": "°C", "color": "#e74c3c", "graph_mode": "line"},
            "humidity": {"label": "Humidity", "unit": "%", "color": "#3498db", "graph_mode": "line"},
            "pressure": {"label": "Pressure", "unit": "hPa", "color": "#95a5a6", "graph_mode": "line"},
        },
    },
    "sgp40": {
        "label": "Air Quality",
        "description": "SGP40 VOC",
        "category": "environment",
        "pin": 59,
        "interval_ms": 3000,
        "fields": {
            "voc_raw": {"label": "VOC", "unit": "", "color": "#27ae60", "graph_mode": "line"},
        },
    },
    "ltr390": {
        "label": "UV Sensor",
        "description": "LTR390 UV Light",
        "category": "light_ir",
        "pin": 53,
        "interval_ms": 2000,
        "fields": {
            "uvs": {"label": "UV Raw", "unit": "", "color": "#9b59b6", "graph_mode": "line"},
            "uvi": {"label": "UV Index", "unit": "", "color": "#8e44ad", "graph_mode": "line"},
        },
    },
    "icm20948": {
        "label": "9-DOF IMU",
        "description": "ICM20948 Motion",
        "category": "motion",
        "pin": 68,
        "interval_ms": 100,
        "fields": {
            "accel_x": {"label": "Accel X", "unit": "m/s²", "color": "#e74c3c", "graph_mode": "line"},
            "accel_y": {"label": "Accel Y", "unit": "m/s²", "color": "#3498db", "graph_mode": "line"},
            "accel_z": {"label": "Accel Z", "unit": "m/s²", "color": "#2ecc71", "graph_mode": "line"},
            "tilt": {"label": "Tilt", "unit": "°", "color": "#f39c12", "graph_mode": "line"},
        },
    },
}

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
MAX_HISTORY = 200       # Max data points kept in memory per field
LOG_DIR = "data"        # CSV logs written here

# ---------------------------------------------------------------------------
# UI Theme - dark mode for 800x480 touchscreen
# ---------------------------------------------------------------------------
THEME = {
    "bg": "#1a1a2e",
    "card_bg": "#16213e",
    "graph_bg": "#0d1117",
    "accent": "#0f3460",
    "text": "#e0e0e0",
    "text_dim": "#666666",
    "success": "#00c853",
    "warning": "#ffd600",
    "error": "#ff1744",
}

# ---------------------------------------------------------------------------
# Dashboard cards — 3x2 grid for the environment dashboard
# Each entry maps a sensor field to one card position.
# ---------------------------------------------------------------------------
DASHBOARD_CARDS = [
    {
        "sensor": "bme280",
        "field": "temperature",
        "label": "Temperature",
        "format": "{:.1f}",
        "color": "#e74c3c",
        # Color thresholds: [(max_value, color), ...] checked in order
        "thresholds": [
            (15, "#40a0ff"),   # Cold — blue
            (22, "#00d084"),   # Comfortable — green
            (28, "#ffa726"),   # Warm — orange
            (99, "#ff5252"),   # Hot — red
        ],
    },
    {
        "sensor": "bme280",
        "field": "humidity",
        "label": "Humidity",
        "format": "{:.0f}",
        "color": "#3498db",
        "thresholds": [
            (30, "#40a0ff"),   # Dry — blue
            (50, "#00d084"),   # Comfortable — green
            (70, "#ffa726"),   # Humid — orange
            (100, "#ff5252"),  # Very humid — red
        ],
    },
    {
        "sensor": "bme280",
        "field": "pressure",
        "label": "Pressure",
        "format": "{:.0f}",
        "color": "#95a5a6",
        # No thresholds — pressure is always neutral
    },
    {
        "sensor": "tsl25911",
        "field": "lux",
        "label": "Light",
        "format": "{:.0f}",
        "color": "#f1c40f",
        "thresholds": [
            (10, "#707070"),    # Dark
            (200, "#a0a0a0"),   # Dim
            (500, "#f1c40f"),   # Good
            (99999, "#ffa726"), # Bright
        ],
    },
    {
        "sensor": "ltr390",
        "field": "uvi",
        "label": "UV Index",
        "format": "{:.1f}",
        "color": "#8e44ad",
        "thresholds": [
            (2, "#00d084"),    # Low — green
            (5, "#ffa726"),    # Moderate — orange
            (7, "#ff9100"),    # High — deep orange
            (99, "#ff5252"),   # Very high — red
        ],
    },
    {
        "sensor": "sgp40",
        "field": "voc_raw",
        "label": "Air Quality",
        "format": "{:,.0f}",
        "color": "#27ae60",
        "thresholds": [
            (20000, "#ff5252"),   # Poor — red (low raw = bad for SGP40)
            (25000, "#ffa726"),   # Fair — orange
            (30000, "#f1c40f"),   # Moderate — yellow
            (99999, "#00d084"),   # Good — green
        ],
    },
]
