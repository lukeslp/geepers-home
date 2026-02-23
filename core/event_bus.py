"""Thread-safe event bus for Home Station.

Background threads (data sources) push data via publish().
The main tkinter thread polls the queue and dispatches to subscribers.
This keeps all widget updates on the main thread (required by tkinter).
"""

import logging
from queue import Queue, Empty
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)


class EventBus:
    """Central message bus bridging background threads to the tkinter main thread."""

    def __init__(self, root):
        self._root = root
        self._queue = Queue()
        self._subscribers: Dict[str, List[Callable]] = {}
        self._poll()

    def publish(self, topic: str, payload: Any):
        """Push data from any thread. Thread-safe."""
        self._queue.put((topic, payload))

    def subscribe(self, topic: str, callback: Callable):
        """Register a callback for a topic. Called on main thread."""
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(callback)

    def unsubscribe(self, topic: str, callback: Callable):
        """Remove a callback."""
        if topic in self._subscribers:
            self._subscribers[topic] = [
                cb for cb in self._subscribers[topic] if cb is not callback
            ]

    def _poll(self):
        """Drain the queue on the main thread. Runs every 50ms."""
        try:
            for _ in range(50):  # process up to 50 messages per tick
                topic, payload = self._queue.get_nowait()
                for cb in self._subscribers.get(topic, []):
                    try:
                        cb(payload)
                    except Exception as exc:
                        logger.error("EventBus callback error [%s]: %s", topic, exc)
        except Empty:
            pass
        self._root.after(50, self._poll)
