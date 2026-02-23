"""Sensor data source -- wraps existing BaseSensor classes.

Bridges the existing sensor/ package into the new DataSource framework.
Each SensorSource wraps one BaseSensor instance and publishes its
readings to the EventBus.
"""

import logging
from typing import Any, Dict, Optional

from core.data_source import DataSource
from core.registry import register_source
from sensors import SENSOR_CLASSES
from config import SENSORS

logger = logging.getLogger(__name__)


@register_source("sensor")
class SensorSource(DataSource):
    """Wraps a BaseSensor and publishes readings via EventBus."""

    def __init__(self, source_id: str, bus, config: Dict):
        # Convert interval_ms from sensor config to seconds
        sensor_key = config.get("sensor_key", source_id)
        sensor_cfg = SENSORS.get(sensor_key, {})
        interval_s = sensor_cfg.get("interval_ms", 2000) / 1000.0
        config.setdefault("interval", interval_s)
        super().__init__(source_id, bus, config)

        self.sensor_key = sensor_key
        self.demo_mode = config.get("demo", False)
        self._sensor = None

        # Initialize the hardware sensor
        cls = SENSOR_CLASSES.get(sensor_key)
        if cls and sensor_cfg:
            try:
                pin = sensor_cfg.get("pin", -1)
                self._sensor = cls(pin, sensor_cfg)
                logger.info("SensorSource %s initialized (%s)", source_id, cls.__name__)
            except Exception as exc:
                logger.warning("SensorSource %s init failed: %s", source_id, exc)

    def fetch(self) -> Optional[Dict[str, Any]]:
        if self._sensor is None:
            return None
        result = self._sensor.read(demo=self.demo_mode)
        if result is not None:
            # Add metadata
            result["_source"] = self.source_id
            result["_sensor_key"] = self.sensor_key
            result["_simulated"] = self._sensor.simulated
        return result

    def set_demo(self, enabled: bool):
        """Toggle demo mode for this sensor."""
        self.demo_mode = enabled

    def close(self):
        super().close()
        if self._sensor:
            self._sensor.close()
