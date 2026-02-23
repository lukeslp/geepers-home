"""Reed switch sensor (magnetic door/window sensor).

How it works:
  A reed switch contains two ferromagnetic contacts sealed in a glass tube.
  When a magnet is brought near, the contacts close, completing the circuit.
  Module output is normally HIGH; goes LOW when magnet is detected.
  We invert the logic so True = magnet present (closed).

Hardware: Digital output, inverted — magnet near = LOW on pin.
"""

from gpiod.line import Bias
from sensors.digital import DigitalSensor


class ReedSensor(DigitalSensor):
    FIELD_NAME = "magnet"
    INVERT = True
    SIM_PROB = 0.02
    BIAS = Bias.PULL_UP
