"""Core framework for the extensible Home Station dashboard.

Provides the building blocks for adding any data source (sensors, APIs,
system stats) and any card type (metrics, clocks, charts) to the dashboard.

Architecture:
    DataSource  -- fetches data in a background thread, publishes to EventBus
    EventBus    -- thread-safe message bus, delivers payloads to subscribers on main thread
    BaseCard    -- tkinter Frame that subscribes to a topic and renders data
    Registry    -- discovers and registers card types + data source types
    PageManager -- organizes cards into swipeable/tappable pages
"""

from core.event_bus import EventBus
from core.data_source import DataSource
from core.base_card import BaseCard
from core.registry import CARD_REGISTRY, SOURCE_REGISTRY, register_card, register_source
from core.page_manager import PageManager

__all__ = [
    "EventBus",
    "DataSource",
    "BaseCard",
    "CARD_REGISTRY",
    "SOURCE_REGISTRY",
    "register_card",
    "register_source",
    "PageManager",
]
