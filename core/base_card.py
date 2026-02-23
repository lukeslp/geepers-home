"""Base card widget for Home Station.

A BaseCard is a tkinter Frame that subscribes to an EventBus topic
and re-renders when new data arrives. All card types inherit from this.

Cards are cheap to update (configure existing widgets) and expensive
to create (build widget tree). setup_ui() runs once; on_data() runs often.
"""

import tkinter as tk
import logging
from abc import ABC, abstractmethod
from collections import deque
from typing import Any, Dict, Optional

from core.event_bus import EventBus

logger = logging.getLogger(__name__)


class BaseCard(tk.Frame, ABC):
    """Abstract card widget. Subclasses define how data is displayed."""

    # Default card size (grid cells). Cards can override.
    COLS = 1  # width in grid columns
    ROWS = 1  # height in grid rows

    def __init__(self, parent, bus: EventBus, config: Dict):
        bg = config.get("bg", "#16213e")
        super().__init__(
            parent,
            bg=bg,
            highlightbackground="#0f3460",
            highlightthickness=1,
        )
        self.bus = bus
        self.card_config = config
        self.topic = config.get("source_id", "")
        self._history: deque = deque(maxlen=config.get("history_len", 200))
        self._last_data: Optional[Dict] = None

        # Build the card UI (runs once)
        self.setup_ui()

        # Subscribe to data updates
        if self.topic:
            self.bus.subscribe(self.topic, self._on_data_wrapper)

    def _on_data_wrapper(self, payload: Any):
        """Store data and call subclass handler."""
        self._last_data = payload
        try:
            self.on_data(payload)
        except Exception as exc:
            logger.error("Card %s update error: %s", self.__class__.__name__, exc)

    @abstractmethod
    def setup_ui(self):
        """Create the card's tkinter widgets. Runs once at init."""
        ...

    @abstractmethod
    def on_data(self, payload: Dict):
        """Handle new data from the EventBus. Runs on main thread."""
        ...

    def on_tap(self) -> Optional[tk.Frame]:
        """Return a detail overlay Frame, or None for no-op.

        Override in subclasses that support tap-to-expand.
        The returned Frame will be placed fullscreen over the dashboard.
        """
        return None

    def get_display_name(self) -> str:
        """Card title for headers and overlays."""
        return self.card_config.get("label", self.__class__.__name__)
