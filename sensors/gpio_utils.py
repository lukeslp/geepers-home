"""GPIO utilities for the Sensor Playground.

Raspberry Pi GPIO pins are accessed through the gpiod library, which talks
to the kernel's GPIO character device (/dev/gpiochipN).

Each Pi model has one or more GPIO chips:
  Pi 3B/3B+/4  ->  /dev/gpiochip0  (BCM2835/BCM2711, 54 lines)
  Pi 5         ->  /dev/gpiochip4  (RP1, 54 lines)

We auto-detect the correct chip so the code works across Pi models.
"""

import gpiod
from gpiod.line import Direction, Bias, Value

# Cached chip path - detected once at first use
_chip_path = None


def get_chip_path():
    """Find the main Broadcom GPIO chip (the one with 54 lines)."""
    global _chip_path
    if _chip_path is not None:
        return _chip_path

    # Try common paths; pick the first chip with >= 28 GPIO lines
    for path in ["/dev/gpiochip0", "/dev/gpiochip4"]:
        try:
            with gpiod.Chip(path) as chip:
                if chip.get_info().num_lines >= 28:
                    _chip_path = path
                    return path
        except (OSError, PermissionError):
            continue

    # Fallback
    _chip_path = "/dev/gpiochip0"
    return _chip_path


def request_input_line(pin, bias=Bias.PULL_DOWN):
    """Request a single GPIO line configured as input.

    Args:
        pin:  BCM GPIO number (e.g. 4, 17, 22)
        bias: Internal pull resistor setting

    Returns:
        gpiod.LineRequest on success, None on failure.
    """
    try:
        req = gpiod.request_lines(
            get_chip_path(),
            consumer="sensor-playground",
            config={
                pin: gpiod.LineSettings(
                    direction=Direction.INPUT,
                    bias=bias,
                ),
            },
        )
        return req
    except Exception as e:
        print(f"  GPIO {pin}: request failed - {e}")
        return None


def read_line(request, pin):
    """Read a digital value from a GPIO line.

    Returns True for HIGH / ACTIVE, False for LOW / INACTIVE.
    """
    return request.get_value(pin) == Value.ACTIVE


def request_output_line(pin):
    """Request a single GPIO line configured as output.

    Args:
        pin:  BCM GPIO number

    Returns:
        gpiod.LineRequest on success, None on failure.
    """
    try:
        req = gpiod.request_lines(
            get_chip_path(),
            consumer="sensor-playground",
            config={
                pin: gpiod.LineSettings(
                    direction=Direction.OUTPUT,
                ),
            },
        )
        return req
    except Exception as e:
        print(f"  GPIO {pin}: output request failed - {e}")
        return None


def request_output_lines(pins):
    """Request multiple GPIO lines configured as output.

    Args:
        pins: list of BCM GPIO numbers

    Returns:
        gpiod.LineRequest on success, None on failure.
    """
    try:
        config = {
            pin: gpiod.LineSettings(direction=Direction.OUTPUT)
            for pin in pins
        }
        req = gpiod.request_lines(
            get_chip_path(),
            consumer="sensor-playground",
            config=config,
        )
        return req
    except Exception as e:
        print(f"  GPIO {pins}: output request failed - {e}")
        return None


def write_line(request, pin, value):
    """Set a digital output on a GPIO line.

    Args:
        request: gpiod.LineRequest from request_output_line()
        pin:     BCM GPIO number
        value:   True for HIGH, False for LOW
    """
    request.set_value(pin, Value.ACTIVE if value else Value.INACTIVE)
