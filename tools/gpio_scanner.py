#!/usr/bin/env python3
"""GPIO Scanner - Visualise Raspberry Pi header pin usage.

Static mode (default):
    python3 tools/gpio_scanner.py
    Prints the 40-pin header with color coding:
      green  = in use by a sensor
      red    = reserved (I2C/SPI/UART)
      yellow = free GPIO
      gray   = power / ground

Watch mode:
    python3 tools/gpio_scanner.py --watch
    Polls all non-reserved GPIO pins at ~50ms and prints state changes.
"""

import sys
import os
import time

# Allow imports from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import SENSORS

# ---------------------------------------------------------------------------
# ANSI colors
# ---------------------------------------------------------------------------
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
GRAY = "\033[90m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# ---------------------------------------------------------------------------
# Pin definitions
# ---------------------------------------------------------------------------
# Physical pin -> function mapping for the 40-pin header
# None means the pin is a GPIO (BCM number filled in below)
POWER_PINS = {1: "3.3V", 2: "5V", 4: "5V", 6: "GND", 9: "GND", 14: "GND",
              17: "3.3V", 20: "GND", 25: "GND", 30: "GND", 34: "GND",
              39: "GND"}

# Physical pin -> BCM GPIO number
PHYS_TO_BCM = {
    3: 2, 5: 3, 7: 4, 8: 14, 10: 15, 11: 17, 12: 18, 13: 27, 15: 22,
    16: 23, 18: 24, 19: 10, 21: 9, 22: 25, 23: 11, 24: 8, 26: 7,
    27: 0, 28: 1, 29: 5, 31: 6, 32: 12, 33: 13, 35: 19, 36: 16,
    37: 26, 38: 20, 40: 21,
}

# Reserved BCM pins (buses we should never touch)
RESERVED_BCM = {2, 3, 7, 8, 9, 10, 11, 14, 15}  # I2C, SPI, UART


def _build_used_pins():
    """Read config.py and return {bcm_pin: sensor_label}."""
    used = {}
    for key, cfg in SENSORS.items():
        pin = cfg.get("pin", -1)
        if pin >= 0:
            used[pin] = cfg["label"]
        for ep in cfg.get("extra_pins", []):
            used[ep] = cfg["label"]
    return used


def _pin_label(phys):
    """Return (display_string, ansi_color) for a physical pin."""
    used = _build_used_pins()

    if phys in POWER_PINS:
        return POWER_PINS[phys], GRAY

    bcm = PHYS_TO_BCM.get(phys)
    if bcm is None:
        return f"Pin {phys}", GRAY

    if bcm in used:
        return f"GPIO {bcm:>2} ({used[bcm]})", GREEN
    if bcm in RESERVED_BCM:
        name = {2: "SDA", 3: "SCL", 7: "CE1", 8: "CE0", 9: "MISO",
                10: "MOSI", 11: "SCLK", 14: "TXD", 15: "RXD"}.get(bcm, "RSV")
        return f"GPIO {bcm:>2} [{name}]", RED
    return f"GPIO {bcm:>2}", YELLOW


def static_mode():
    """Print the 40-pin header with color coding."""
    used = _build_used_pins()

    print(f"\n{BOLD}Raspberry Pi 40-Pin Header{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}")
    print()
    print(f"  {GREEN}GREEN{RESET}=in use  {RED}RED{RESET}=reserved  "
          f"{YELLOW}YELLOW{RESET}=free  {GRAY}GRAY{RESET}=power/gnd")
    print()

    # Header pins are numbered: odd on left, even on right
    for row in range(1, 40, 2):
        left_phys = row
        right_phys = row + 1

        left_text, left_color = _pin_label(left_phys)
        right_text, right_color = _pin_label(right_phys)

        print(f"  {left_color}{left_text:>25}{RESET}"
              f"  [{left_phys:>2}|{right_phys:<2}]  "
              f"{right_color}{right_text}{RESET}")

    print()
    print(f"  {BOLD}Used:{RESET} {len(used)} pins   "
          f"{BOLD}Reserved:{RESET} {len(RESERVED_BCM)}   "
          f"{BOLD}Free:{RESET} {len(PHYS_TO_BCM) - len(used) - len(RESERVED_BCM)}")
    print()


def watch_mode():
    """Poll all non-reserved GPIO pins and report state changes."""
    try:
        import gpiod
        from gpiod.line import Direction, Bias
    except ImportError:
        print("Error: gpiod not available. Install libgpiod-dev.")
        sys.exit(1)

    used = _build_used_pins()
    # Watch free AND used pins (useful for debugging)
    watch_pins = sorted(
        bcm for bcm in PHYS_TO_BCM.values()
        if bcm not in RESERVED_BCM
    )

    # Find GPIO chip
    chip_path = "/dev/gpiochip0"
    for path in ["/dev/gpiochip0", "/dev/gpiochip4"]:
        try:
            with gpiod.Chip(path) as chip:
                if chip.get_info().num_lines >= 28:
                    chip_path = path
                    break
        except (OSError, PermissionError):
            continue

    # Request all lines as input
    config = {}
    for pin in watch_pins:
        config[pin] = gpiod.LineSettings(
            direction=Direction.INPUT,
            bias=Bias.PULL_DOWN,
        )

    try:
        req = gpiod.request_lines(chip_path, consumer="gpio-scanner", config=config)
    except Exception as e:
        print(f"Error requesting GPIO lines: {e}")
        print("Some pins may be in use by other processes. Try with sudo.")
        sys.exit(1)

    # Initial state
    prev = {}
    for pin in watch_pins:
        prev[pin] = req.get_value(pin)

    print(f"\n{BOLD}GPIO Watch Mode{RESET} — polling {len(watch_pins)} pins")
    print(f"Press Ctrl+C to stop.\n")
    print(f"{'Time':>12}  {'GPIO':>6}  {'State':>6}  {'Sensor'}")
    print("-" * 45)

    try:
        while True:
            for pin in watch_pins:
                val = req.get_value(pin)
                if val != prev[pin]:
                    ts = time.strftime("%H:%M:%S") + f".{int(time.time()*1000)%1000:03d}"
                    state = f"{GREEN}HIGH{RESET}" if val.value else f"{GRAY}LOW {RESET}"
                    label = used.get(pin, "")
                    print(f"  {ts}  GPIO {pin:>2}  {state}  {label}")
                    prev[pin] = val
            time.sleep(0.05)  # 50ms poll interval
    except KeyboardInterrupt:
        print(f"\n{BOLD}Stopped.{RESET}")
    finally:
        req.release()


if __name__ == "__main__":
    if "--watch" in sys.argv:
        watch_mode()
    else:
        static_mode()
