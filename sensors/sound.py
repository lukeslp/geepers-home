"""Sound detection sensor (digital mode).

How it works:
  The module has an electret microphone and an LM393 comparator.
  Sound waves hit the microphone, generating a small voltage.
  The comparator checks if this voltage exceeds a threshold
  set by the blue potentiometer on the module.

  Digital output (DO): HIGH when sound exceeds threshold, LOW otherwise.
  Analog output (AO): Proportional to sound level — needs ADC to read.

Hardware: DO pin goes HIGH on loud sounds (clap, snap, etc).
"""

from sensors.digital import DigitalSensor


class SoundSensor(DigitalSensor):
    FIELD_NAME = "sound"
    INVERT = False
    SIM_PROB = 0.08
