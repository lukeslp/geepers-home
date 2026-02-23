"""Card and DataSource registries for Home Station.

Register card types and data source types by name. The dashboard
loads configuration (YAML or dict) and instantiates the right classes
by looking them up here.

Usage:
    @register_card("sensor")
    class SensorCard(BaseCard):
        ...

    @register_source("sensor")
    class SensorSource(DataSource):
        ...
"""

import logging

logger = logging.getLogger(__name__)

CARD_REGISTRY = {}
SOURCE_REGISTRY = {}


def register_card(name):
    """Decorator to register a card class by type name."""
    def decorator(cls):
        CARD_REGISTRY[name] = cls
        logger.debug("Registered card type: %s -> %s", name, cls.__name__)
        return cls
    return decorator


def register_source(name):
    """Decorator to register a data source class by type name."""
    def decorator(cls):
        SOURCE_REGISTRY[name] = cls
        logger.debug("Registered source type: %s -> %s", name, cls.__name__)
        return cls
    return decorator
