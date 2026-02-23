"""Web-compatible event bus for Home Station.

Replaces the tkinter-coupled EventBus with a thread-safe version
that supports SSE streaming to web clients. Data sources publish
via publish() from background threads. Web clients consume via
SSE generator.
"""

import logging
import threading
import time
from queue import Queue, Empty, Full
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class WebEventBus:
    """Event bus for Flask/web mode. No tkinter dependency."""

    def __init__(self):
        self._latest: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._sse_clients: List[Queue] = []
        self._subscribers: Dict[str, List[Callable]] = {}

    def publish(self, topic: str, payload: Any):
        """Push data from any thread. Thread-safe."""
        with self._lock:
            self._latest[topic] = payload

        # Notify SSE clients (non-blocking)
        dead = []
        for q in self._sse_clients:
            try:
                q.put_nowait((topic, payload))
            except Full:
                dead.append(q)
        for q in dead:
            try:
                self._sse_clients.remove(q)
            except ValueError:
                pass

        # Direct subscribers (called from publisher thread)
        for cb in self._subscribers.get(topic, []):
            try:
                cb(payload)
            except Exception as exc:
                logger.error("WebEventBus callback error [%s]: %s", topic, exc)

    def subscribe(self, topic: str, callback: Callable):
        """Register a callback for a topic."""
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(callback)

    def get_latest(self, topic: Optional[str] = None) -> Any:
        """Get latest payload for a topic, or all topics."""
        with self._lock:
            if topic:
                return self._latest.get(topic)
            return dict(self._latest)

    def sse_stream(self):
        """Generator for SSE clients. Yields (topic, payload) tuples.

        Usage in Flask:
            def stream():
                for topic, payload in bus.sse_stream():
                    yield f"event: {topic}\\ndata: {json.dumps(payload)}\\n\\n"
        """
        q = Queue(maxsize=100)
        self._sse_clients.append(q)
        try:
            while True:
                try:
                    topic, payload = q.get(timeout=30)
                    yield topic, payload
                except Empty:
                    # Send keepalive
                    yield "keepalive", None
        finally:
            try:
                self._sse_clients.remove(q)
            except ValueError:
                pass
