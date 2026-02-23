"""Active buzzer module.

How it works:
  An active buzzer has a built-in oscillator circuit, so it produces
  a tone when you simply apply voltage. No frequency generation needed.
  HIGH = buzzer on (beeping), LOW = buzzer off.

  This is an output device. The read() method controls the buzzer
  and returns its current state for the UI.

Hardware: Single GPIO output pin. HIGH = on, LOW = off.
"""

import random
import time
import logging
from typing import Any, Dict, Optional

from sensors.base import BaseSensor
from sensors.gpio_utils import request_output_line, write_line

logger = logging.getLogger(__name__)


class BuzzerSensor(BaseSensor):

    def _init_hardware(self) -> None:
        self._request = request_output_line(self.pin)
        self._hw_available = self._request is not None
        self._active = False
        self._last_toggle = time.time()
        self._pattern_idx = 0
        self._sim_counter = 0
        self._pattern = [(0.1, 0.9), (0.1, 0.1), (0.1, 1.5)]

        if self._hw_available:
            logger.info("Buzzer: ready on GPIO %d", self.pin)
        else:
            logger.info("Buzzer: GPIO %d unavailable", self.pin)

    def _read_hardware(self) -> Optional[Dict[str, Any]]:
        now = time.time()
        on_time, off_time = self._pattern[self._pattern_idx % len(self._pattern)]
        duration = on_time if self._active else off_time

        if now - self._last_toggle >= duration:
            if self._active:
                self._active = False
                write_line(self._request, self.pin, False)
            else:
                self._active = True
                self._pattern_idx += 1
                write_line(self._request, self.pin, True)
            self._last_toggle = now

        return {"buzzing": self._active}

    def _simulate(self) -> Dict[str, Any]:
        self._sim_counter += 1
        buzzing = random.random() < 0.05
        return {"buzzing": buzzing}

    def close(self) -> None:
        if self._request:
            write_line(self._request, self.pin, False)
            self._request.release()
            self._request = None
