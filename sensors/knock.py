"""Knock / vibration sensor (SW-420).

How it works:
  The SW-420 is a spring-based vibration switch with an LM393 comparator.
  When vibration exceeds the threshold set by the onboard potentiometer,
  the digital output goes HIGH.

  Sensitive enough to detect knocks on a table, footsteps, or tapping.

Hardware: DO pin goes HIGH on vibration/knock.
"""

from sensors.digital import DigitalSensor


class KnockSensor(DigitalSensor):
    FIELD_NAME = "vibration"
    INVERT = False
    SIM_PROB = 0.06
