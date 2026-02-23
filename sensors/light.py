"""Light threshold sensor (LDR + LM393 comparator module).

How it works:
  A photoresistor (LDR) changes resistance with light intensity.
  The LM393 comparator compares this to a threshold set by the
  onboard potentiometer. When ambient light drops below the
  threshold, the digital output goes HIGH ("dark" detected).

Hardware: DO pin goes HIGH when it's dark (light below threshold).
"""

from sensors.digital import DigitalSensor


class LightSensor(DigitalSensor):
    FIELD_NAME = "dark"
    INVERT = False
    SIM_PROB = 0.02
