"""ICM20948 9-DOF IMU sensor (I2C).

9-axis motion tracking: 3-axis accelerometer, gyroscope, magnetometer.
Used for orientation, motion detection, and magnetic field sensing.

I2C Address: 0x68 (can be 0x69 with jumper)
"""

import random
import logging
import math
from typing import Any, Dict, Optional

from sensors.base import BaseSensor

logger = logging.getLogger(__name__)

try:
    import board
    import busio
    import adafruit_icm20x
    _lib_available = True
except ImportError:
    _lib_available = False


class ICM20948Sensor(BaseSensor):
    def _init_hardware(self) -> None:
        self._sensor = None
        if not _lib_available:
            logger.info('ICM20948: adafruit_icm20x library not installed')
            return

        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self._sensor = adafruit_icm20x.ICM20948(i2c, address=0x68)
            self._hw_available = True
            logger.info('ICM20948: ready on I2C 0x68')
        except Exception as e:
            logger.info(f'ICM20948: init failed - {e}')

    def _read_hardware(self) -> Optional[Dict[str, Any]]:
        try:
            acc = self._sensor.acceleration
            gyro = self._sensor.gyro
            mag = self._sensor.magnetic

            # Calculate orientation (simplified - just tilt)
            accel_magnitude = math.sqrt(acc[0]**2 + acc[1]**2 + acc[2]**2)
            tilt = math.degrees(math.acos(abs(acc[2]) / accel_magnitude)) if accel_magnitude > 0 else 0

            return {
                'accel_x': round(acc[0], 2),
                'accel_y': round(acc[1], 2),
                'accel_z': round(acc[2], 2),
                'gyro_x': round(gyro[0], 2),
                'gyro_y': round(gyro[1], 2),
                'gyro_z': round(gyro[2], 2),
                'mag_x': round(mag[0], 2),
                'mag_y': round(mag[1], 2),
                'mag_z': round(mag[2], 2),
                'tilt': round(tilt, 1)
            }
        except Exception as e:
            logger.debug(f'ICM20948 read error: {e}')
            return None

    def _simulate(self) -> Dict[str, Any]:
        return {
            'accel_x': round(random.uniform(-2, 2), 2),
            'accel_y': round(random.uniform(-2, 2), 2),
            'accel_z': round(random.uniform(8, 11), 2),
            'gyro_x': round(random.uniform(-0.1, 0.1), 2),
            'gyro_y': round(random.uniform(-0.1, 0.1), 2),
            'gyro_z': round(random.uniform(-0.1, 0.1), 2),
            'mag_x': round(random.uniform(-50, 50), 2),
            'mag_y': round(random.uniform(-50, 50), 2),
            'mag_z': round(random.uniform(-50, 50), 2),
            'tilt': round(random.uniform(0, 30), 1)
        }

    def close(self) -> None:
        self._sensor = None
