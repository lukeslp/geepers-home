"""ADS1115 ADC manager (I2C address 0x48).

The ADS1115 is a 16-bit, 4-channel analog-to-digital converter.
It connects via I2C and converts analog voltages (0-3.3V or 0-4.096V)
to digital values that the Pi can read.

Channel plan:
  A0 = Sound level (analog)
  A1 = Light level (analog)
  A2 = Soil moisture
  A3 = Joystick X-axis

A second ADS1115 at address 0x49 can be added for more channels.

Uses adafruit-circuitpython-ads1x15 library.
"""

import logging

logger = logging.getLogger(__name__)

_adc_available = False
try:
    import board
    import busio
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn
    _adc_available = True
except ImportError:
    pass


class ADCManager:
    """Singleton manager for ADS1115 ADC access."""

    _instance = None

    @classmethod
    def get_instance(cls):
        """Get or create the singleton ADC instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._ads = None
        self._channels = {}
        self._available = False

        if not _adc_available:
            logger.info("ADC: adafruit-ads1x15 not installed (run setup.sh)")
            return

        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self._ads = ADS.ADS1115(i2c, address=0x48)
            self._ads.gain = 1  # +/-4.096V range
            self._available = True
            logger.info("ADC: ADS1115 ready on I2C 0x48")
        except Exception as exc:
            logger.info("ADC: init failed — %s", exc)

    @property
    def available(self):
        return self._available

    def read_channel(self, channel):
        """Read voltage from an ADC channel (0-3).

        Returns:
            Voltage as float (0.0 to ~3.3V), or None on failure.
        """
        if not self._available:
            return None

        try:
            if channel not in self._channels:
                # ADS channel constants: P0, P1, P2, P3
                pin = getattr(ADS, f"P{channel}")
                self._channels[channel] = AnalogIn(self._ads, pin)

            return self._channels[channel].voltage
        except Exception:
            return None

    def read_raw(self, channel):
        """Read raw 16-bit value from an ADC channel (0-3).

        Returns:
            Raw ADC value (0-32767 for single-ended), or None.
        """
        if not self._available:
            return None

        try:
            if channel not in self._channels:
                pin = getattr(ADS, f"P{channel}")
                self._channels[channel] = AnalogIn(self._ads, pin)

            return self._channels[channel].value
        except Exception:
            return None
