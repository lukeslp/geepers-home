"""Data source implementations for Home Station.

Importing this package registers all built-in source types.
Hardware-dependent sources (sensor) are imported with fallback
so the dashboard still works on machines without GPIO libraries.
"""

import logging

logger = logging.getLogger(__name__)

_all = []

# Sensor source depends on GPIO hardware libraries (gpiod, adafruit-blinka)
# which are only available on the Pi. Import with fallback.
try:
    from sources.sensor_source import SensorSource
    _all.append("SensorSource")
except ImportError as exc:
    logger.warning("SensorSource unavailable: %s", exc)

from sources.system_source import SystemSource
from sources.rest_source import RESTSource
from sources.network_source import NetworkSource
from sources.camera_source import CameraSource
from sources.vision_source import VisionSource
from sources.weather_source import WeatherSource

_all.extend(["SystemSource", "RESTSource", "NetworkSource", "CameraSource", "VisionSource", "WeatherSource"])

try:
    from sources.wifi_scanner_source import WiFiScannerSource
    _all.append("WiFiScannerSource")
except ImportError as exc:
    logger.warning("WiFiScannerSource unavailable: %s", exc)

try:
    from sources.bluetooth_scanner_source import BluetoothScannerSource
    _all.append("BluetoothScannerSource")
except ImportError as exc:
    logger.warning("BluetoothScannerSource unavailable: %s", exc)

try:
    from sources.news_source import NewsSource
    _all.append("NewsSource")
except ImportError as exc:
    logger.warning("NewsSource unavailable: %s", exc)

__all__ = _all
