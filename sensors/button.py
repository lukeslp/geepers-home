"""Push button module.

How it works:
  Simple momentary push button with a pull-up resistor on the module.
  When pressed, the circuit closes and output goes LOW.
  We invert the logic so True = button pressed.

Hardware: Digital output, inverted — pressed = LOW on pin.
"""

from gpiod.line import Bias
from sensors.digital import DigitalSensor


class ButtonSensor(DigitalSensor):
    FIELD_NAME = "pressed"
    INVERT = True
    SIM_PROB = 0.03
    BIAS = Bias.PULL_UP
