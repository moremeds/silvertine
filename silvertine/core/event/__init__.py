"""
Event system module for Silvertine trading framework.

This module provides the core event-driven architecture components including
event types, event bus, and event handling mechanisms.
"""

from .event_bus import EventBus
from .event_bus import HandlerPriority
from .events import Event
from .events import EventType
from .events import FillEvent
from .events import MarketDataEvent
from .events import OrderEvent
from .events import OrderSide
from .events import OrderStatus
from .events import OrderType
from .events import SignalEvent
from .events import SignalType

__all__ = [
    # Event Bus
    "EventBus",
    "HandlerPriority",
    # Base Event
    "Event",
    "EventType",
    # Market Data
    "MarketDataEvent",
    # Orders
    "OrderEvent",
    "OrderType",
    "OrderSide",
    "OrderStatus",
    # Fills
    "FillEvent",
    # Signals
    "SignalEvent",
    "SignalType",
]
