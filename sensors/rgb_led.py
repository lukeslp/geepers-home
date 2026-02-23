"""RGB LED module (common cathode, 3-pin digital control).

How it works:
  Three separate LEDs (red, green, blue) in one package with a common
  ground. Each color is controlled by a separate GPIO pin — HIGH to
  turn on, LOW to turn off.

  With digital control (no PWM), we get 8 possible color combinations:
    000=off, 100=red, 010=green, 001=blue,
    110=yellow, 101=magenta, 011=cyan, 111=white

  This is an output device — it doesn't produce sensor data, but the
  read() method returns the current LED state for display in the UI.

Hardware: 3 GPIO output pins for R, G, B channels.
"""

import time
import logging
from typing import Any, Dict, Optional

from sensors.base import BaseSensor
from sensors.gpio_utils import request_output_lines, write_line

logger = logging.getLogger(__name__)

# Color cycle for demo / display
COLORS = [
    ("Red",     (True,  False, False)),
    ("Green",   (False, True,  False)),
    ("Blue",    (False, False, True)),
    ("Yellow",  (True,  True,  False)),
    ("Magenta", (True,  False, True)),
    ("Cyan",    (False, True,  True)),
    ("White",   (True,  True,  True)),
    ("Off",     (False, False, False)),
]


class RGBLEDSensor(BaseSensor):

    def _init_hardware(self) -> None:
        extra = self._cfg.get("extra_pins", [])
        self._pins = [self.pin] + list(extra)  # [R, G, B]
        self._request = None
        self._color_idx = 0
        self._last_change = time.time()
        self._sim_counter = 0

        if len(self._pins) == 3:
            self._request = request_output_lines(self._pins)
            self._hw_available = self._request is not None

        if self._hw_available:
            logger.info("RGB LED: ready on GPIO %s", self._pins)
        else:
            logger.info("RGB LED: GPIO %s unavailable", self._pins)

    def _read_hardware(self) -> Optional[Dict[str, Any]]:
        # Cycle colors every 2 seconds
        now = time.time()
        if now - self._last_change >= 2.0:
            self._color_idx = (self._color_idx + 1) % len(COLORS)
            self._last_change = now
            name, (r, g, b) = COLORS[self._color_idx]
            write_line(self._request, self._pins[0], r)
            write_line(self._request, self._pins[1], g)
            write_line(self._request, self._pins[2], b)

        return {"color": COLORS[self._color_idx][0]}

    def _simulate(self) -> Dict[str, Any]:
        self._sim_counter += 1
        if self._sim_counter % 4 == 0:
            self._color_idx = (self._color_idx + 1) % len(COLORS)
        return {"color": COLORS[self._color_idx][0]}

    def close(self) -> None:
        if self._request:
            for pin in self._pins:
                write_line(self._request, pin, False)
            self._request.release()
            self._request = None
