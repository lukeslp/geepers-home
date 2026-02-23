"""Hall effect sensor (magnetic field detector).

How it works:
  Uses the Hall effect — when a magnetic field passes through the sensor,
  it generates a voltage proportional to the field strength.
  The onboard comparator converts this to a digital signal.
  Module output goes LOW when a magnetic field is detected.
  We invert the logic so True = magnet detected.

Hardware: Digital output, inverted — magnet = LOW on pin.
"""

from sensors.digital import DigitalSensor


class HallSensor(DigitalSensor):
    FIELD_NAME = "magnetic"
    INVERT = True
    SIM_PROB = 0.03
