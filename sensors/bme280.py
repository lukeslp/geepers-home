"""BME280 environmental sensor (I2C).

Combined temperature, humidity, and barometric pressure sensor.
More capable than SHTC3 due to pressure measurement.

I2C Address: 0x76 (can be 0x77 with jumper)
"""

import random
import logging
from typing import Any, Dict, Optional

from sensors.base import BaseSensor

logger = logging.getLogger(__name__)

try:
    import board
    import busio
    from adafruit_bme280 import basic as adafruit_bme280
    _lib_available = True
except ImportError:
    _lib_available = False


class BME280Sensor(BaseSensor):
    def _init_hardware(self) -> None:
        self._sensor = None
        if not _lib_available:
            logger.info('BME280: adafruit_bme280 library not installed')
            return

        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self._sensor = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x76)
            # Set recommended settings for indoor monitoring
            self._sensor.sea_level_pressure = 1013.25
            self._hw_available = True
            logger.info('BME280: ready on I2C 0x76')
        except Exception as e:
            logger.info(f'BME280: init failed - {e}')

    def _read_hardware(self) -> Optional[Dict[str, Any]]:
        try:
            temp = self._sensor.temperature
            humidity = self._sensor.humidity
            pressure = self._sensor.pressure
            altitude = self._sensor.altitude

            return {
                'temperature': round(temp, 1),
                'humidity': round(humidity, 1),
                'pressure': round(pressure, 1),
                'altitude': round(altitude, 1)
            }
        except Exception as e:
            logger.debug(f'BME280 read error: {e}')
            return None

    def _simulate(self) -> Dict[str, Any]:
        return {
            'temperature': round(random.uniform(18, 26), 1),
            'humidity': round(random.uniform(30, 60), 1),
            'pressure': round(random.uniform(990, 1030), 1),
            'altitude': round(random.uniform(0, 100), 1)
        }

    def close(self) -> None:
        self._sensor = None
