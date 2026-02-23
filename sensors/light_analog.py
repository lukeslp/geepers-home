"""Analog light level sensor (via ADS1115 ADC).

How it works:
  Same LDR + comparator module as the digital light sensor,
  but we read the analog output (AO) through the ADS1115 ADC.
  This gives a continuous light level (0-100%) instead of just
  a dark/bright threshold.

Hardware: AO pin connected to ADS1115 channel A1.
"""

import random
import logging
from typing import Any, Dict, Optional

from sensors.base import BaseSensor
from sensors.adc import ADCManager

logger = logging.getLogger(__name__)


class LightAnalogSensor(BaseSensor):

    def _init_hardware(self) -> None:
        self._adc_channel = self._cfg.get("adc_channel", 1)
        self._adc = ADCManager.get_instance()
        self._hw_available = self._adc.available
        self._sim_level = 65.0

        if self._hw_available:
            logger.info("Light (analog): ready on ADC channel A%d", self._adc_channel)
        else:
            logger.info("Light (analog): ADC unavailable")

    def _read_hardware(self) -> Optional[Dict[str, Any]]:
        voltage = self._adc.read_channel(self._adc_channel)
        if voltage is None:
            return None
        level = max(0.0, min(100.0, (voltage / 3.3) * 100.0))
        return {"light_level": round(level, 1)}

    def _simulate(self) -> Dict[str, Any]:
        self._sim_level += random.gauss(0, 1.5)
        self._sim_level = self._sim_level * 0.97 + 65.0 * 0.03
        self._sim_level = max(0, min(100, self._sim_level))
        return {"light_level": round(self._sim_level, 1)}
