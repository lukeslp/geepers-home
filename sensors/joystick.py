"""Joystick module (analog X-axis + digital button).

How it works:
  The joystick module has two potentiometers (X and Y axes) and a
  push button (press the stick down). Each potentiometer outputs
  0-3.3V proportional to the stick position.

  We read the X-axis via ADS1115 ADC channel A3, and the button
  via a digital GPIO pin.

  Center position reads ~1.65V (50%). Full left = 0V, full right = 3.3V.
  The button is active-LOW (pressed = LOW).

Hardware: VRx (X-axis) to ADS1115 A3, SW (button) to GPIO 18.
"""

import random
import logging
from typing import Any, Dict, Optional

from sensors.base import BaseSensor
from sensors.adc import ADCManager
from sensors.gpio_utils import request_input_line, read_line
from gpiod.line import Bias

logger = logging.getLogger(__name__)


class JoystickSensor(BaseSensor):

    def _init_hardware(self) -> None:
        self._adc_channel = self._cfg.get("adc_channel", 3)
        self._adc = ADCManager.get_instance()

        extra = self._cfg.get("extra_pins", [18])
        self._btn_pin = extra[0] if extra else 18
        self._btn_request = request_input_line(self._btn_pin, bias=Bias.PULL_UP)

        self._hw_available = self._adc.available
        self._sim_x = 50.0
        self._sim_btn = False

        if self._hw_available:
            btn_status = "ready" if self._btn_request else "unavailable"
            logger.info(
                "Joystick: ADC A%d + button GPIO %d (%s)",
                self._adc_channel, self._btn_pin, btn_status,
            )
        else:
            logger.info("Joystick: ADC unavailable")

    def _read_hardware(self) -> Optional[Dict[str, Any]]:
        voltage = self._adc.read_channel(self._adc_channel)
        if voltage is None:
            return None

        x_pct = max(0.0, min(100.0, (voltage / 3.3) * 100.0))

        btn = False
        if self._btn_request:
            btn = not read_line(self._btn_request, self._btn_pin)

        return {"joy_x": round(x_pct, 1), "joy_button": btn}

    def _simulate(self) -> Dict[str, Any]:
        self._sim_x += random.gauss(0, 3)
        self._sim_x = self._sim_x * 0.9 + 50.0 * 0.1
        self._sim_x = max(0, min(100, self._sim_x))

        if random.random() < 0.03:
            self._sim_btn = not self._sim_btn

        return {"joy_x": round(self._sim_x, 1), "joy_button": self._sim_btn}

    def close(self) -> None:
        if self._btn_request:
            self._btn_request.release()
            self._btn_request = None
