"""Tilt switch sensor.

How it works:
  Contains a small metal ball inside a cylinder. When the sensor is
  upright, the ball rests on two contacts and completes the circuit.
  When tilted beyond ~30 degrees, the ball rolls away and breaks contact.
  This is essentially a binary orientation detector — not an accelerometer.

Hardware: Digital output, change state on tilt.
"""

from gpiod.line import Bias
from sensors.digital import DigitalSensor


class TiltSensor(DigitalSensor):
    FIELD_NAME = "tilted"
    INVERT = False
    SIM_PROB = 0.03
    BIAS = Bias.PULL_UP
