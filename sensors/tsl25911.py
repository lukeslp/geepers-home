"""TSL25911 light and IR sensor (I2C).

Adafruit TSL2591 High Dynamic Range Digital Light Sensor.
Measures both infrared and full-spectrum (visible + IR) light.
Combines readings to calculate visible-only and lux values.

I2C Address: 0x29 (fixed)
"""

import random
import logging
from typing import Any, Dict, Optional

from sensors.base import BaseSensor

logger = logging.getLogger(__name__)

try:
    import board
    import busio
    from adafruit_tsl2591 import TSL2591
    _lib_available = True
except ImportError:
    _lib_available = False


class TSL25911Sensor(BaseSensor):
    def _init_hardware(self) -> None:
        self._sensor = None
        if not _lib_available:
            logger.info('TSL25911: adafruit_tsl2591 library not installed')
            return

        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self._sensor = TSL2591(i2c)
            self._hw_available = True
            logger.info('TSL25911: ready on I2C 0x29')
        except Exception as e:
            logger.info(f'TSL25911: init failed - {e}')

    def _read_hardware(self) -> Optional[Dict[str, Any]]:
        try:
            lux = self._sensor.lux
            visible = self._sensor.visible
            infrared = self._sensor.infrared

            return {
                'lux': round(lux, 2) if lux is not None else 0,
                'visible': visible,
                'infrared': infrared
            }
        except Exception as e:
            logger.debug(f'TSL25911 read error: {e}')
            return None

    def _simulate(self) -> Dict[str, Any]:
        return {
            'lux': random.uniform(50, 500),
            'visible': random.randint(100, 1000),
            'infrared': random.randint(50, 500)
        }

    def close(self) -> None:
        self._sensor = None
