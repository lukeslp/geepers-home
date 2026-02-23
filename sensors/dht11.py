"""DHT11 temperature and humidity sensor.

Protocol overview (handled by the Adafruit C extension):
  1. Pi pulls DATA line LOW for >= 18 ms (start signal)
  2. Pi releases line; DHT11 responds LOW 80 us, then HIGH 80 us
  3. DHT11 sends 40 bits:
       8-bit humidity integer
       8-bit humidity decimal (always 0 on DHT11)
       8-bit temperature integer
       8-bit temperature decimal
       8-bit checksum
  4. Each bit: LOW 50 us, then HIGH 26-28 us (0) or 70 us (1)

Specs:
  Temperature  0-50 C,   +/- 2 C accuracy
  Humidity     20-90 %,  +/- 5 % accuracy
  Min interval 1 second  (we use 2.5 s for reliability)

The timing is too tight for pure Python, so we rely on
adafruit-circuitpython-dht which uses a C extension.
"""

import random
import logging
from typing import Any, Dict, Optional

from sensors.base import BaseSensor

logger = logging.getLogger(__name__)


class DHT11Sensor(BaseSensor):
    MAX_RETRIES = 3          # DHT11 is notoriously flaky
    RETRY_DELAY = 0.3        # needs time between attempts

    def _init_hardware(self) -> None:
        self._device = None
        self._sim_temp = 22.0
        self._sim_hum = 45.0

        try:
            import board
            import adafruit_dht
            board_pin = getattr(board, f"D{self.pin}", None)
            if board_pin:
                self._device = adafruit_dht.DHT11(board_pin)
                self._hw_available = True
                logger.info("DHT11: ready on GPIO %d", self.pin)
            else:
                logger.info("DHT11: board.D%d not found", self.pin)
        except ImportError:
            logger.info("DHT11: adafruit library not installed (run setup.sh)")
        except Exception as exc:
            logger.info("DHT11: init failed — %s", exc)

    def _read_hardware(self) -> Optional[Dict[str, Any]]:
        temp = self._device.temperature
        hum = self._device.humidity
        if temp is not None and hum is not None:
            return {"temperature": round(float(temp), 1), "humidity": round(float(hum), 1)}
        return None

    def _simulate(self) -> Dict[str, Any]:
        # Random walk with mean reversion toward 22 C / 45 %
        self._sim_temp += random.gauss(0, 0.3)
        self._sim_temp = self._sim_temp * 0.97 + 22.0 * 0.03
        self._sim_temp = max(10.0, min(40.0, self._sim_temp))

        self._sim_hum += random.gauss(0, 1.0)
        self._sim_hum = self._sim_hum * 0.97 + 45.0 * 0.03
        self._sim_hum = max(20.0, min(90.0, self._sim_hum))

        return {
            "temperature": round(self._sim_temp, 1),
            "humidity": round(self._sim_hum, 1),
        }

    def close(self) -> None:
        if self._device:
            try:
                self._device.exit()
            except Exception:
                pass
            self._device = None
