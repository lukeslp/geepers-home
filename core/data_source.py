"""Data source abstraction for Home Station.

A DataSource fetches data (from sensors, APIs, /proc, etc.) in a
background thread and publishes it to the EventBus. The dashboard
doesn't care where data comes from -- it just subscribes to topics.
"""

import logging
import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from core.event_bus import EventBus

logger = logging.getLogger(__name__)


class DataSource(ABC):
    """Base class for all data providers.

    Subclasses implement fetch() which runs in a background thread.
    Data is published to the EventBus under self.topic.
    """

    def __init__(self, source_id: str, bus: EventBus, config: Dict):
        self.source_id = source_id
        self.bus = bus
        self.config = config
        self.topic = source_id  # subscribers use this to listen
        self.interval = config.get("interval", 5.0)  # seconds
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start the background polling thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name=f"src-{self.source_id}"
        )
        self._thread.start()
        logger.info("DataSource %s started (%.1fs interval)", self.source_id, self.interval)

    def stop(self):
        """Signal the background thread to stop."""
        self._stop.set()

    def _run(self):
        """Poll loop -- fetch data and publish, sleep in small chunks."""
        while not self._stop.is_set():
            try:
                data = self.fetch()
                if data is not None:
                    self.bus.publish(self.topic, data)
            except Exception as exc:
                logger.error("DataSource %s fetch error: %s", self.source_id, exc)

            # Sleep in 0.1s chunks so stop() is responsive
            chunks = int(self.interval * 10)
            for _ in range(max(chunks, 1)):
                if self._stop.is_set():
                    break
                time.sleep(0.1)

    @abstractmethod
    def fetch(self) -> Optional[Dict[str, Any]]:
        """Fetch data. Runs in background thread.

        Returns:
            Dict of field->value, or None to skip this cycle.
        """
        ...

    def close(self):
        """Release resources. Override if needed."""
        self.stop()
