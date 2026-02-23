"""Soil moisture sensor (capacitive, via ADS1115 ADC).

How it works:
  A capacitive soil moisture sensor measures the dielectric permittivity
  of the soil. The output voltage is INVERSELY proportional to moisture:
    Dry soil  -> higher voltage (~2.5-3.0V)
    Wet soil  -> lower voltage  (~1.0-1.5V)

  We invert and scale to 0-100% where 100% = saturated wet.

Hardware: Analog output connected to ADS1115 channel A2.
"""

import random
import logging
from typing import Any, Dict, Optional

from sensors.base import BaseSensor
from sensors.adc import ADCManager

logger = logging.getLogger(__name__)


class SoilMoistureSensor(BaseSensor):

    def _init_hardware(self) -> None:
        self._adc_channel = self._cfg.get("adc_channel", 2)
        self._adc = ADCManager.get_instance()
        self._hw_available = self._adc.available
        self._sim_moisture = 45.0

        if self._hw_available:
            logger.info("Soil Moisture: ready on ADC channel A%d", self._adc_channel)
        else:
            logger.info("Soil Moisture: ADC unavailable")

    def _read_hardware(self) -> Optional[Dict[str, Any]]:
        voltage = self._adc.read_channel(self._adc_channel)
        if voltage is None:
            return None
        moisture = max(0.0, min(100.0, (3.0 - voltage) / 2.0 * 100.0))
        return {"moisture": round(moisture, 1)}

    def _simulate(self) -> Dict[str, Any]:
        self._sim_moisture += random.gauss(0, 0.5)
        self._sim_moisture = self._sim_moisture * 0.99 + 45.0 * 0.01
        self._sim_moisture = max(0, min(100, self._sim_moisture))
        return {"moisture": round(self._sim_moisture, 1)}
