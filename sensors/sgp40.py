"""SGP40 VOC (Volatile Organic Compounds) sensor (I2C).

Measures air quality via VOC detection using Sensirion's VOC Index
Algorithm, which converts raw resistance into a 0-500 index with
automatic 24-hour adaptive baseline calibration.

VOC Index interpretation:
  0-100:  Normal / clean air (100 = average baseline)
  100-150: Slight increase in VOCs
  150-250: Moderate — ventilate if sustained
  250-400: High — open windows, check sources
  400-500: Very high — take action immediately

I2C Address: 0x59 (fixed)
"""

import random
import logging
from typing import Any, Dict, Optional

from sensors.base import BaseSensor

logger = logging.getLogger(__name__)

try:
    import board
    import busio
    import adafruit_sgp40
    _lib_available = True
except ImportError:
    _lib_available = False

# Sensirion VOC Index Algorithm — converts raw ticks to 0-500 index
# with 24-hour adaptive baseline learning
try:
    from sensirion_gas_index_algorithm.voc_algorithm import VocAlgorithm
    _voc_algo_available = True
except ImportError:
    _voc_algo_available = False
    logger.info('SGP40: sensirion-gas-index-algorithm not installed, '
                'falling back to raw values')


def _classify_voc_index(index: int) -> str:
    """Classify VOC Index (0-500) into human-readable quality."""
    if index <= 100:
        return 'excellent'
    elif index <= 150:
        return 'good'
    elif index <= 250:
        return 'moderate'
    elif index <= 400:
        return 'poor'
    else:
        return 'hazardous'


class SGP40Sensor(BaseSensor):
    def _init_hardware(self) -> None:
        self._sensor = None
        self._voc_algo = None
        if not _lib_available:
            logger.info('SGP40: adafruit_sgp40 library not installed')
            return

        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self._sensor = adafruit_sgp40.SGP40(i2c)
            self._hw_available = True
            logger.info('SGP40: ready on I2C 0x59')

            # Initialize Sensirion VOC Index Algorithm
            if _voc_algo_available:
                self._voc_algo = VocAlgorithm()
                logger.info('SGP40: VOC Index Algorithm active '
                            '(24h adaptive baseline)')
            else:
                logger.info('SGP40: using raw resistance values '
                            '(install sensirion-gas-index-algorithm '
                            'for VOC Index)')
        except Exception as e:
            logger.info(f'SGP40: init failed - {e}')

    def _read_hardware(self) -> Optional[Dict[str, Any]]:
        try:
            raw = self._sensor.raw

            result = {'voc_raw': raw}

            # Convert raw to VOC Index via Sensirion algorithm
            if self._voc_algo is not None:
                voc_index = self._voc_algo.process(raw)
                result['voc_index'] = voc_index
                result['quality'] = _classify_voc_index(voc_index)
            else:
                # Fallback: estimate voc_index from raw ticks
                # SGP40 raw ranges roughly 0-65535, baseline ~28000-32000
                # Map to 0-500 scale: low raw = clean air (index ~80-100),
                # high raw = poor air (index 200+)
                if raw < 20000:
                    voc_index = max(0, int(60 + (raw / 20000) * 40))
                elif raw < 30000:
                    voc_index = int(100 + ((raw - 20000) / 10000) * 50)
                elif raw < 40000:
                    voc_index = int(150 + ((raw - 30000) / 10000) * 100)
                else:
                    voc_index = min(500, int(250 + ((raw - 40000) / 25000) * 250))
                result['voc_index'] = voc_index
                result['quality'] = _classify_voc_index(voc_index)

            return result
        except Exception as e:
            logger.debug(f'SGP40 read error: {e}')
            return None

    def _simulate(self) -> Dict[str, Any]:
        # Simulate VOC Index centered around 100 (normal baseline)
        # with occasional spikes
        voc_index = random.choices(
            population=[random.randint(50, 120),   # normal
                        random.randint(120, 200),  # slightly elevated
                        random.randint(200, 350)], # elevated
            weights=[0.7, 0.2, 0.1],
            k=1
        )[0]
        return {
            'voc_index': voc_index,
            'voc_raw': random.randint(15000, 35000),
            'quality': _classify_voc_index(voc_index),
        }

    def close(self) -> None:
        self._sensor = None
        self._voc_algo = None
