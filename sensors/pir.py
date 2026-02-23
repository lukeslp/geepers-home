"""PIR (Passive Infrared) motion sensor (HC-SR501).

How it works:
  The sensor has two IR-sensitive slots. When a warm body (person, animal)
  moves across its field of view, one slot sees more IR than the other,
  creating a voltage difference that triggers the digital output HIGH.

Module features:
  - Two potentiometers: sensitivity (range) and hold-time (how long HIGH stays)
  - Jumper for single-trigger vs repeatable-trigger mode
  - Wide detection angle (~120 degrees)
  - Needs 5V supply but outputs 3.3V-safe HIGH signal

Hardware: Digital output pin goes HIGH on motion.
"""

from sensors.digital import DigitalSensor


class PIRSensor(DigitalSensor):
    FIELD_NAME = "motion"
    INVERT = False
    SIM_PROB = 0.08
