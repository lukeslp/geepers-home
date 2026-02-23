"""Flame sensor (IR flame detection module).

How it works:
  Uses an infrared receiver tuned to the wavelength emitted by flames
  (~760-1100nm). The LM393 comparator triggers when IR intensity
  exceeds the threshold set by the potentiometer.
  Module output goes LOW when flame is detected (active-low).
  We invert the logic so True = flame detected.

Hardware: Digital output, inverted — flame detected = LOW on pin.
"""

from sensors.digital import DigitalSensor


class FlameSensor(DigitalSensor):
    FIELD_NAME = "flame"
    INVERT = True
    SIM_PROB = 0.01
