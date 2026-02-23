"""SSD1306 OLED display output (128x64, I2C address 0x3C).

Shows the currently selected sensor's readings on a small OLED screen.
Uses adafruit-circuitpython-ssd1306 + PIL for rendering.

The display updates whenever the visible sensor tab polls new data.
"""

_oled_available = False
try:
    import board
    import busio
    import adafruit_ssd1306
    from PIL import Image, ImageDraw, ImageFont
    _oled_available = True
except ImportError:
    pass


class OLEDDisplay:
    """Drives a 128x64 SSD1306 OLED via I2C."""

    _instance = None

    @classmethod
    def get_instance(cls):
        """Singleton — only one OLED display."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._display = None
        self._available = False
        self._image = None
        self._draw = None
        self._font = None

        if not _oled_available:
            print("  OLED: libraries not installed (run setup.sh)")
            return

        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self._display = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)
            self._display.fill(0)
            self._display.show()

            self._image = Image.new("1", (128, 64))
            self._draw = ImageDraw.Draw(self._image)

            # Try to load a small font; fall back to default
            try:
                self._font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 10)
                self._font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 16)
            except (IOError, OSError):
                self._font = ImageFont.load_default()
                self._font_large = self._font

            self._available = True
            print("  OLED: ready on I2C 0x3C")
        except Exception as e:
            print(f"  OLED: init failed - {e}")

    @property
    def available(self):
        return self._available

    def update(self, sensor_label, readings):
        """Render sensor readings on the OLED.

        Args:
            sensor_label: Display name (e.g. "DHT11")
            readings: dict of field -> value from sensor.read()
        """
        if not self._available or not readings:
            return

        try:
            self._draw.rectangle((0, 0, 127, 63), fill=0)

            # Header
            self._draw.text((0, 0), sensor_label, font=self._font, fill=1)
            self._draw.line((0, 12, 127, 12), fill=1)

            # Values
            y = 16
            for field, value in readings.items():
                if isinstance(value, bool):
                    text = f"{field}: {'YES' if value else 'NO'}"
                elif isinstance(value, float):
                    text = f"{field}: {value:.1f}"
                else:
                    text = f"{field}: {value}"

                if len(readings) == 1:
                    # Single value — show large
                    val_text = text.split(": ", 1)[1] if ": " in text else str(value)
                    self._draw.text((0, y), field + ":", font=self._font, fill=1)
                    self._draw.text((0, y + 14), val_text, font=self._font_large, fill=1)
                else:
                    self._draw.text((0, y), text, font=self._font, fill=1)
                    y += 14

            self._display.image(self._image)
            self._display.show()
        except Exception:
            pass  # OLED errors shouldn't crash the main app

    def clear(self):
        """Clear the display."""
        if self._available:
            try:
                self._display.fill(0)
                self._display.show()
            except Exception:
                pass

    def close(self):
        """Clean up."""
        self.clear()
