"""LTR390 UV sensor (I2C).

UV light sensor with ambient light rejection.
Measures UVS (UV sensor raw value) and calculates UV Index.

I2C Address: 0x53 (fixed)
"""

import random
import logging
from typing import Any, Dict, Optional

from sensors.base import BaseSensor

logger = logging.getLogger(__name__)

try:
    import board
    import busio
    import adafruit_ltr390
    _lib_available = True
except ImportError:
    _lib_available = False


class LTR390Sensor(BaseSensor):
    def _init_hardware(self) -> None:
        self._sensor = None
        if not _lib_available:
            logger.info('LTR390: adafruit_ltr390 library not installed')
            return

        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self._sensor = adafruit_ltr390.LTR390(i2c)
            self._hw_available = True
            logger.info('LTR390: ready on I2C 0x53')
        except Exception as e:
            logger.info(f'LTR390: init failed - {e}')

    def _read_hardware(self) -> Optional[Dict[str, Any]]:
        try:
            uvs = self._sensor.uvs
            uvi = self._sensor.uvi

            return {
                'uvs': uvs,
                'uvi': round(uvi, 2)
            }
        except Exception as e:
            logger.debug(f'LTR390 read error: {e}')
            return None

    def _simulate(self) -> Dict[str, Any]:
        return {
            'uvs': random.randint(0, 1000),
            'uvi': round(random.uniform(0, 11), 2)
        }

    def close(self) -> None:
        self._sensor = None
