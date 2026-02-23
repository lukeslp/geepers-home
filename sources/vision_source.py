"""Vision analysis source.

Periodically grabs the latest camera frame (via CameraSource class
attribute) and POSTs it to a VPS endpoint for LLM scene description.
Publishes the description text for VisionCard to display.

Config example:
    sources:
      - id: "camera.vision"
        type: "vision"
        endpoint: "http://localhost:5030/api/analyze"
        api_key: ""
        interval: 60
"""

import logging
import time
from typing import Any, Dict, Optional

from core.data_source import DataSource
from core.registry import register_source

logger = logging.getLogger(__name__)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


@register_source("vision")
class VisionSource(DataSource):
    """Sends camera frames to VPS for LLM scene description."""

    def __init__(self, source_id: str, bus, config: Dict):
        config.setdefault("interval", 60.0)
        super().__init__(source_id, bus, config)
        self._endpoint = config.get(
            "endpoint", "https://dr.eamer.dev/pivision/api/analyze"
        )
        self._api_key = config.get("api_key", "")
        self._provider = config.get("provider", "xai")
        self._detail = config.get("detail", "brief")
        self._timeout = config.get("timeout", 30)
        self._last_description = ""
        self._demo = config.get("demo", False)

    def fetch(self) -> Optional[Dict[str, Any]]:
        if self._demo:
            return self._generate_demo()

        if not HAS_REQUESTS:
            logger.error("requests library not available for vision source")
            return None

        # Get latest JPEG from CameraSource class attribute
        from sources.camera_source import CameraSource
        jpeg = CameraSource.latest_jpeg
        if jpeg is None:
            logger.debug("No camera frame available yet")
            return None

        try:
            headers = {}
            if self._api_key:
                headers["X-API-Key"] = self._api_key
            resp = requests.post(
                self._endpoint,
                files={"image": ("frame.jpg", jpeg, "image/jpeg")},
                params={"provider": self._provider, "detail": self._detail},
                headers=headers,
                timeout=self._timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    self._last_description = data.get("description", "")
                    return {
                        "description": self._last_description,
                        "provider": data.get("provider", ""),
                        "model": data.get("model", ""),
                        "cached": data.get("cached", False),
                        "timestamp": time.strftime("%H:%M:%S"),
                    }
                else:
                    logger.warning("Vision API error: %s", data.get("error"))
                    return None
            elif resp.status_code == 429:
                logger.debug("Vision API rate limited, will retry next interval")
                return None
            else:
                logger.warning("Vision API returned %d: %s",
                               resp.status_code, resp.text[:200])
                return None
        except requests.ConnectionError:
            logger.debug("Vision API not reachable")
            return None
        except Exception as exc:
            logger.error("Vision API error: %s", exc)
            return None

    def _generate_demo(self):
        """Return synthetic descriptions for demo mode."""
        descriptions = [
            "Living room, natural light from window. No movement detected.",
            "Indoor scene, moderate lighting. Desk area visible.",
            "Room appears empty. Ambient light from overhead fixture.",
            "Indoor environment, stable conditions. Some items on table.",
        ]
        idx = int(time.time() / 60) % len(descriptions)
        return {
            "description": descriptions[idx],
            "timestamp": time.strftime("%H:%M:%S"),
        }

    def set_demo(self, demo: bool):
        """Toggle demo mode at runtime."""
        self._demo = demo

    def close(self):
        """Clean shutdown."""
        super().close()
