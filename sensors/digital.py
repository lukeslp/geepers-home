"""Generic digital GPIO sensor base class.

Many sensors in the 37-in-1 kit are simple digital threshold sensors:
they output HIGH or LOW based on whether a reading exceeds a
potentiometer-set threshold. This base class handles the common
pattern so individual sensor modules only need to specify their
field name, label, and simulation behaviour.

Subclasses should set the class attributes:
    FIELD_NAME   — key used in the readings dict (e.g. "motion")
    INVERT       — True if LOW = triggered (some sensors are active-LOW)
    SIM_PROB     — probability of a simulated trigger per read cycle
"""

import random
import logging
from typing import Any, Dict, Optional

from sensors.base import BaseSensor
from sensors.gpio_utils import request_input_line, read_line
from gpiod.line import Bias

logger = logging.getLogger(__name__)


class DigitalSensor(BaseSensor):
    """Base class for simple digital HIGH/LOW GPIO sensors."""

    FIELD_NAME: str = "value"
    INVERT: bool = False
    SIM_PROB: float = 0.05
    BIAS: Bias = Bias.PULL_DOWN

    def _init_hardware(self) -> None:
        self._request = None
        if self.pin < 0:
            return

        self._request = request_input_line(self.pin, bias=self.BIAS)
        if self._request:
            self._hw_available = True
            logger.info(
                "%s: ready on GPIO %d", self.__class__.__name__, self.pin
            )
        else:
            logger.info(
                "%s: GPIO %d unavailable", self.__class__.__name__, self.pin
            )

    def _read_hardware(self) -> Optional[Dict[str, Any]]:
        if not self._request:
            return None
        raw = read_line(self._request, self.pin)
        triggered = (not raw) if self.INVERT else raw
        return {self.FIELD_NAME: triggered}

    def _simulate(self) -> Dict[str, Any]:
        return {self.FIELD_NAME: random.random() < self.SIM_PROB}

    def close(self) -> None:
        if self._request:
            self._request.release()
            self._request = None
