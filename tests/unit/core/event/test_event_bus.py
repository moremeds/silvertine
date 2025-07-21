"""
Unit tests for the asyncio event bus.
"""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from silvertine.core.event.event_bus import EventBus
from silvertine.core.event.event_bus import EventHandler
from silvertine.core.event.event_bus import HandlerPriority
from silvertine.core.event.events import EventType
from silvertine.core.event.events import MarketDataEvent
from silvertine.core.event.events import OrderEvent
from silvertine.core.event.events import OrderSide


class TestEventBus:
    """Test the EventBus class."""

    @pytest.fixture
    def event_bus(self):
        """Create an EventBus instance."""
        return EventBus(max_queue_size=100)

    @pytest.fixture
    def market_data_event(self):
        """Create a test market data event."""
        return MarketDataEvent(
            symbol="BTCUSDT", price=Decimal("50000.00"), volume=Decimal("1.5")
        )

    @pytest.fixture
    def order_event(self):
        """Create a test order event."""
        return OrderEvent(
            order_id="order_123",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            order_type="MARKET",
        )

    async def test_event_bus_creation(self, event_bus):
        """Test creating an event bus."""
        assert event_bus.max_queue_size == 100
        assert not event_bus.is_running
        assert len(event_bus._handlers) == 0

    async def test_handler_registration(self, event_bus):
        """Test registering event handlers."""
        handler = AsyncMock()

        event_bus.subscribe(EventType.MARKET_DATA, handler)

        assert EventType.MARKET_DATA in event_bus._handlers
        assert len(event_bus._handlers[EventType.MARKET_DATA]) == 1

    async def test_handler_registration_with_priority(self, event_bus):
        """Test registering handlers with different priorities."""
        high_priority_handler = AsyncMock()
        low_priority_handler = AsyncMock()

        event_bus.subscribe(
            EventType.MARKET_DATA, high_priority_handler, HandlerPriority.HIGH
        )
        event_bus.subscribe(
            EventType.MARKET_DATA, low_priority_handler, HandlerPriority.LOW
        )

        handlers = event_bus._handlers[EventType.MARKET_DATA]
        assert len(handlers) == 2

        # Higher priority handlers should come first
        assert handlers[0].priority == HandlerPriority.HIGH
        assert handlers[1].priority == HandlerPriority.LOW

    async def test_handler_unsubscription(self, event_bus):
        """Test unsubscribing event handlers."""
        handler = AsyncMock()

        event_bus.subscribe(EventType.MARKET_DATA, handler)
        assert len(event_bus._handlers[EventType.MARKET_DATA]) == 1

        event_bus.unsubscribe(EventType.MARKET_DATA, handler)
        assert len(event_bus._handlers[EventType.MARKET_DATA]) == 0

    async def test_event_publishing_without_handlers(
        self, event_bus, market_data_event
    ):
        """Test publishing events when no handlers are registered."""
        await event_bus.start()

        # Should not raise exception
        await event_bus.publish(market_data_event)

        await event_bus.stop()

    async def test_event_publishing_with_handlers(self, event_bus, market_data_event):
        """Test publishing events to registered handlers."""
        handler = AsyncMock()
        event_bus.subscribe(EventType.MARKET_DATA, handler)

        await event_bus.start()
        await event_bus.publish(market_data_event)

        # Give event time to be processed
        await asyncio.sleep(0.01)

        handler.assert_called_once_with(market_data_event)

        await event_bus.stop()

    async def test_multiple_handlers_same_event_type(
        self, event_bus, market_data_event
    ):
        """Test multiple handlers for the same event type."""
        handler1 = AsyncMock()
        handler2 = AsyncMock()

        event_bus.subscribe(EventType.MARKET_DATA, handler1)
        event_bus.subscribe(EventType.MARKET_DATA, handler2)

        await event_bus.start()
        await event_bus.publish(market_data_event)

        # Give events time to be processed
        await asyncio.sleep(0.01)

        handler1.assert_called_once_with(market_data_event)
        handler2.assert_called_once_with(market_data_event)

        await event_bus.stop()

    async def test_handler_priority_ordering(self, event_bus, market_data_event):
        """Test that handlers are called in priority order."""
        call_order = []

        async def high_priority_handler(_event):
            call_order.append("high")

        async def low_priority_handler(_event):
            call_order.append("low")

        async def normal_priority_handler(_event):
            call_order.append("normal")

        event_bus.subscribe(
            EventType.MARKET_DATA, low_priority_handler, HandlerPriority.LOW
        )
        event_bus.subscribe(
            EventType.MARKET_DATA, high_priority_handler, HandlerPriority.HIGH
        )
        event_bus.subscribe(
            EventType.MARKET_DATA, normal_priority_handler, HandlerPriority.NORMAL
        )

        await event_bus.start()
        await event_bus.publish(market_data_event)

        # Give events time to be processed
        await asyncio.sleep(0.01)

        assert call_order == ["high", "normal", "low"]

        await event_bus.stop()

    async def test_different_event_types(
        self, event_bus, market_data_event, order_event
    ):
        """Test handling different event types."""
        market_handler = AsyncMock()
        order_handler = AsyncMock()

        event_bus.subscribe(EventType.MARKET_DATA, market_handler)
        event_bus.subscribe(EventType.ORDER, order_handler)

        await event_bus.start()

        await event_bus.publish(market_data_event)
        await event_bus.publish(order_event)

        # Give events time to be processed
        await asyncio.sleep(0.01)

        market_handler.assert_called_once_with(market_data_event)
        order_handler.assert_called_once_with(order_event)

        await event_bus.stop()

    async def test_idempotency(self, event_bus, market_data_event):
        """Test that duplicate events are handled idempotently."""
        handler = AsyncMock()
        event_bus.subscribe(EventType.MARKET_DATA, handler)

        await event_bus.start()

        # Publish the same event twice
        await event_bus.publish(market_data_event)
        await event_bus.publish(market_data_event)

        # Give events time to be processed
        await asyncio.sleep(0.01)

        # Handler should only be called once due to idempotency
        handler.assert_called_once_with(market_data_event)

        await event_bus.stop()

    async def test_handler_exception_handling(self, event_bus, market_data_event):
        """Test that handler exceptions don't crash the event bus."""
        failing_handler = AsyncMock(side_effect=Exception("Handler failed"))
        working_handler = AsyncMock()

        event_bus.subscribe(EventType.MARKET_DATA, failing_handler)
        event_bus.subscribe(EventType.MARKET_DATA, working_handler)

        await event_bus.start()
        await event_bus.publish(market_data_event)

        # Give events time to be processed
        await asyncio.sleep(0.01)

        # Working handler should still be called despite the failing one
        working_handler.assert_called_once_with(market_data_event)

        await event_bus.stop()

    async def test_queue_overflow_handling(self, event_bus, market_data_event):
        """Test handling of queue overflow."""
        # Create a bus with very small queue
        small_bus = EventBus(max_queue_size=1)

        # Add a slow handler to create backpressure
        slow_handler = AsyncMock()
        slow_handler.side_effect = lambda event: asyncio.sleep(1)
        small_bus.subscribe(EventType.MARKET_DATA, slow_handler)

        await small_bus.start()

        # Try to publish more events than queue can handle
        await small_bus.publish(market_data_event)

        # This should handle gracefully without blocking
        with pytest.raises(asyncio.QueueFull):
            for _ in range(10):
                small_bus._queues[EventType.MARKET_DATA].put_nowait(market_data_event)

        await small_bus.stop()

    async def test_metrics_collection(self, event_bus, market_data_event):
        """Test that event metrics are collected."""
        handler = AsyncMock()
        event_bus.subscribe(EventType.MARKET_DATA, handler)

        await event_bus.start()
        await event_bus.publish(market_data_event)

        # Give events time to be processed
        await asyncio.sleep(0.01)

        metrics = event_bus.get_metrics()
        assert EventType.MARKET_DATA in metrics
        assert metrics[EventType.MARKET_DATA]["events_published"] >= 1
        assert metrics[EventType.MARKET_DATA]["events_processed"] >= 1

        await event_bus.stop()

    async def test_start_stop_lifecycle(self, event_bus):
        """Test event bus start/stop lifecycle."""
        assert not event_bus.is_running

        await event_bus.start()
        assert event_bus.is_running

        await event_bus.stop()
        assert not event_bus.is_running

    async def test_multiple_start_stop_calls(self, event_bus):
        """Test that multiple start/stop calls are handled gracefully."""
        # Multiple starts should be idempotent
        await event_bus.start()
        await event_bus.start()
        assert event_bus.is_running

        # Multiple stops should be idempotent
        await event_bus.stop()
        await event_bus.stop()
        assert not event_bus.is_running


class TestEventHandler:
    """Test the EventHandler class."""

    def test_event_handler_creation(self):
        """Test creating an EventHandler."""
        handler_func = AsyncMock()
        handler = EventHandler(handler_func, HandlerPriority.HIGH)

        assert handler.handler == handler_func
        assert handler.priority == HandlerPriority.HIGH

    def test_event_handler_comparison(self):
        """Test EventHandler comparison for sorting."""
        high_handler = EventHandler(AsyncMock(), HandlerPriority.HIGH)
        normal_handler = EventHandler(AsyncMock(), HandlerPriority.NORMAL)
        low_handler = EventHandler(AsyncMock(), HandlerPriority.LOW)

        handlers = [low_handler, high_handler, normal_handler]
        sorted_handlers = sorted(handlers)

        assert sorted_handlers[0].priority == HandlerPriority.HIGH
        assert sorted_handlers[1].priority == HandlerPriority.NORMAL
        assert sorted_handlers[2].priority == HandlerPriority.LOW


class TestHandlerPriority:
    """Test the HandlerPriority enum."""

    def test_priority_values(self):
        """Test priority enum values."""
        assert HandlerPriority.HIGH.value == 1
        assert HandlerPriority.NORMAL.value == 2
        assert HandlerPriority.LOW.value == 3

    def test_priority_ordering(self):
        """Test that priorities can be compared."""
        assert HandlerPriority.HIGH.value < HandlerPriority.NORMAL.value
        assert HandlerPriority.NORMAL.value < HandlerPriority.LOW.value
        assert HandlerPriority.HIGH.value < HandlerPriority.LOW.value
