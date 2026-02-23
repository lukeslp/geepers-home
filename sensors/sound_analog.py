"""Analog sound level sensor (via ADS1115 ADC).

How it works:
  Same electret microphone module as the digital sound sensor,
  but we read the analog output (AO) through the ADS1115 ADC.
  This gives a continuous sound level (0-100%) instead of just
  a threshold trigger.

Hardware: AO pin connected to ADS1115 channel A0.
"""

import random
import logging
from typing import Any, Dict, Optional

from sensors.base import BaseSensor
from sensors.adc import ADCManager

logger = logging.getLogger(__name__)


class SoundAnalogSensor(BaseSensor):

    def _init_hardware(self) -> None:
        self._adc_channel = self._cfg.get("adc_channel", 0)
        self._adc = ADCManager.get_instance()
        self._hw_available = self._adc.available
        self._sim_level = 10.0

        if self._hw_available:
            logger.info("Sound (analog): ready on ADC channel A%d", self._adc_channel)
        else:
            logger.info("Sound (analog): ADC unavailable")

    def _read_hardware(self) -> Optional[Dict[str, Any]]:
        voltage = self._adc.read_channel(self._adc_channel)
        if voltage is None:
            return None
        level = max(0.0, min(100.0, (voltage / 3.3) * 100.0))
        return {"sound_level": round(level, 1)}

    def _simulate(self) -> Dict[str, Any]:
        self._sim_level = self._sim_level * 0.85 + 10.0 * 0.15
        if random.random() < 0.08:
            self._sim_level += random.uniform(20, 60)
        self._sim_level = max(0, min(100, self._sim_level + random.gauss(0, 2)))
        return {"sound_level": round(self._sim_level, 1)}
