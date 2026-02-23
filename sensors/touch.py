"""Capacitive touch sensor (TTP223 module).

How it works:
  The TTP223 IC detects changes in capacitance when a finger touches
  the sensor pad. Output goes HIGH when touched (active-high).
  Very responsive — typical response time is 60ms.

Hardware: Digital output, active-high — touch = HIGH on pin.
"""

from sensors.digital import DigitalSensor


class TouchSensor(DigitalSensor):
    FIELD_NAME = "touched"
    INVERT = False
    SIM_PROB = 0.04
