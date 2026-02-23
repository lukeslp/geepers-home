"""DS18B20 digital temperature sensor (1-Wire protocol).

How it works:
  The DS18B20 uses the Dallas 1-Wire protocol — multiple devices can share
  a single data line with individual 64-bit serial addresses.

  The Linux kernel has a built-in 1-Wire driver. Once enabled via:
    dtoverlay=w1-gpio,gpiopin=12
  in /boot/config.txt (+ reboot), sensor data appears at:
    /sys/bus/w1/devices/28-*/w1_slave

  The w1_slave file contains two lines:
    Line 1: "...CRC=xx YES/NO"  (YES means valid reading)
    Line 2: "...t=NNNNN"        (temperature in millidegrees C)

Specs:
  Range: -55C to +125C
  Accuracy: +/-0.5C from -10C to +85C
  Resolution: 12-bit (0.0625C), configurable 9-12 bit
  Conversion time: ~750ms at 12-bit

  Requires a 4.7k pull-up resistor on the data line to 3.3V.

Hardware: 1-Wire protocol on GPIO 12 via kernel driver.
"""

import glob
import random
import logging
from typing import Any, Dict, Optional

from sensors.base import BaseSensor

logger = logging.getLogger(__name__)


class DS18B20Sensor(BaseSensor):

    def _init_hardware(self) -> None:
        self._device_path = None
        self._sim_temp = 21.5

        devices = glob.glob("/sys/bus/w1/devices/28-*/w1_slave")
        if devices:
            self._device_path = devices[0]
            self._hw_available = True
            dev_id = self._device_path.split("/")[-2]
            logger.info("DS18B20: found device %s", dev_id)
        else:
            logger.info(
                "DS18B20: no 1-Wire device found. "
                "Ensure dtoverlay=w1-gpio,gpiopin=%d in /boot/config.txt",
                self.pin,
            )

    def _read_hardware(self) -> Optional[Dict[str, Any]]:
        with open(self._device_path, "r") as f:
            lines = f.readlines()

        if len(lines) < 2 or "YES" not in lines[0]:
            return None

        idx = lines[1].find("t=")
        if idx == -1:
            return None

        temp_c = int(lines[1][idx + 2:]) / 1000.0
        return {"ext_temperature": round(temp_c, 1)}

    def _simulate(self) -> Dict[str, Any]:
        self._sim_temp += random.gauss(0, 0.2)
        self._sim_temp = self._sim_temp * 0.97 + 21.5 * 0.03
        self._sim_temp = max(-10.0, min(50.0, self._sim_temp))
        return {"ext_temperature": round(self._sim_temp, 1)}
