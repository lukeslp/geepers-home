#!/bin/bash
# Sensor Playground - Setup Script
# Run once to install all dependencies and configure the Pi.
#
# Usage:  bash setup.sh

set -e

echo "=== Sensor Playground Setup ==="
echo ""

# --- System packages ---
echo "[1/6] Installing system packages..."
sudo apt update -qq
sudo apt install -y \
    python3-pip python3-pil python3-pil.imagetk \
    libgpiod-dev i2c-tools python3-tk \
    python3-numpy python3-yaml python3-requests \
    ffmpeg

# --- Python packages ---
echo ""
echo "[2/6] Installing Python sensor libraries..."
sudo pip3 install --break-system-packages \
    adafruit-blinka \
    adafruit-circuitpython-dht \
    adafruit-circuitpython-ssd1306 \
    adafruit-circuitpython-ads1x15 \
    adafruit-circuitpython-bme280 \
    adafruit-circuitpython-tsl2591 \
    adafruit-circuitpython-ltr390 \
    adafruit-circuitpython-sgp40 \
    adafruit-circuitpython-icm20x \
    pyyaml \
    requests

# --- Enable I2C and SPI (for OLED, ADC, future sensors) ---
echo ""
echo "[3/6] Enabling I2C and SPI interfaces..."
sudo raspi-config nonint do_i2c 0   # 0 = enable
sudo raspi-config nonint do_spi 0

# --- Enable 1-Wire for DS18B20 temperature sensor ---
echo ""
echo "[4/6] Enabling 1-Wire interface for DS18B20..."
CONFIG="/boot/config.txt"
# Also check /boot/firmware/config.txt (newer Pi OS)
if [ -f "/boot/firmware/config.txt" ]; then
    CONFIG="/boot/firmware/config.txt"
fi
if ! grep -q "dtoverlay=w1-gpio,gpiopin=12" "$CONFIG" 2>/dev/null; then
    echo "dtoverlay=w1-gpio,gpiopin=12" | sudo tee -a "$CONFIG" > /dev/null
    echo "  Added 1-Wire overlay to $CONFIG (reboot required)"
else
    echo "  1-Wire overlay already configured in $CONFIG"
fi

# --- Check camera device ---
echo ""
echo "[5/6] Checking camera..."
if [ -e /dev/video0 ]; then
    echo "  Camera found at /dev/video0"
    # Test a quick capture
    if ffmpeg -f v4l2 -i /dev/video0 -frames:v 1 -f null - 2>/dev/null; then
        echo "  Camera capture test: OK"
    else
        echo "  Camera capture test: FAILED (may need different input_format)"
    fi
else
    echo "  No camera at /dev/video0 (camera features will be disabled)"
fi

# --- Create directories ---
echo ""
echo "[6/6] Creating data directories..."
mkdir -p data snapshots

echo ""
echo "=== Setup complete ==="
echo ""
echo "To run:  python3 main.py"
echo "Demo:    python3 main.py --demo"
echo ""
echo "GPIO scanner:  python3 tools/gpio_scanner.py"
echo "GPIO watch:    python3 tools/gpio_scanner.py --watch"
echo ""
echo "NOTE: If you added a DS18B20, reboot for 1-Wire to activate."
echo "See the INFO tab in the app for wiring diagrams."
