"""
Unit tests for event classes.
"""

import json
import uuid
from datetime import datetime
from datetime import timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from silvertine.core.event.events import Event
from silvertine.core.event.events import EventType
from silvertine.core.event.events import FillEvent
from silvertine.core.event.events import MarketDataEvent
from silvertine.core.event.events import OrderEvent
from silvertine.core.event.events import OrderSide
from silvertine.core.event.events import OrderType
from silvertine.core.event.events import SignalEvent
from silvertine.core.event.events import SignalType


class TestEvent:
    """Test the base Event class."""

    def test_event_creation_with_defaults(self):
        """Test creating an event with default values."""
        event = Event(event_type=EventType.MARKET_DATA)

        assert event.event_type == EventType.MARKET_DATA
        assert isinstance(event.event_id, str)
        assert len(event.event_id) == 36  # UUID4 length
        assert isinstance(event.timestamp, datetime)
        assert event.timestamp.tzinfo == timezone.utc

    def test_event_creation_with_custom_values(self):
        """Test creating an event with custom values."""
        event_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)

        event = Event(
            event_type=EventType.ORDER, event_id=event_id, timestamp=timestamp
        )

        assert event.event_type == EventType.ORDER
        assert event.event_id == event_id
        assert event.timestamp == timestamp

    def test_event_immutability(self):
        """Test that events are immutable after creation."""
        event = Event(event_type=EventType.FILL)

        with pytest.raises(ValidationError):
            event.event_type = EventType.SIGNAL

    def test_event_serialization(self):
        """Test event serialization to dict."""
        event = Event(event_type=EventType.MARKET_DATA)
        data = event.to_dict()

        assert isinstance(data, dict)
        assert data["event_type"] == "MARKET_DATA"
        assert "event_id" in data
        assert "timestamp" in data

    def test_event_json_serialization(self):
        """Test event JSON serialization."""
        event = Event(event_type=EventType.ORDER)
        json_str = event.to_json()

        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert data["event_type"] == "ORDER"

    def test_event_deserialization(self):
        """Test event deserialization from dict."""
        original = Event(event_type=EventType.FILL)
        data = original.to_dict()

        reconstructed = Event.from_dict(data)

        assert reconstructed.event_type == original.event_type
        assert reconstructed.event_id == original.event_id
        assert reconstructed.timestamp == original.timestamp


class TestMarketDataEvent:
    """Test the MarketDataEvent class."""

    def test_market_data_event_creation(self):
        """Test creating a market data event."""
        event = MarketDataEvent(
            symbol="BTCUSDT",
            price=Decimal("50000.00"),
            volume=Decimal("1.5"),
            bid=Decimal("49999.50"),
            ask=Decimal("50000.50"),
        )

        assert event.event_type == EventType.MARKET_DATA
        assert event.symbol == "BTCUSDT"
        assert event.price == Decimal("50000.00")
        assert event.volume == Decimal("1.5")
        assert event.bid == Decimal("49999.50")
        assert event.ask == Decimal("50000.50")

    def test_market_data_event_validation(self):
        """Test market data event validation."""
        with pytest.raises(ValidationError):
            MarketDataEvent(
                symbol="",  # Empty symbol should fail
                price=Decimal("50000.00"),
                volume=Decimal("1.5"),
            )

        with pytest.raises(ValidationError):
            MarketDataEvent(
                symbol="BTCUSDT",
                price=Decimal("-1.00"),  # Negative price should fail
                volume=Decimal("1.5"),
            )

    def test_market_data_spread_calculation(self):
        """Test spread calculation."""
        event = MarketDataEvent(
            symbol="BTCUSDT",
            price=Decimal("50000.00"),
            volume=Decimal("1.5"),
            bid=Decimal("49999.00"),
            ask=Decimal("50001.00"),
        )

        assert event.spread == Decimal("2.00")

    def test_market_data_mid_price_calculation(self):
        """Test mid price calculation."""
        event = MarketDataEvent(
            symbol="BTCUSDT",
            price=Decimal("50000.00"),
            volume=Decimal("1.5"),
            bid=Decimal("49999.00"),
            ask=Decimal("50001.00"),
        )

        assert event.mid_price == Decimal("50000.00")


class TestOrderEvent:
    """Test the OrderEvent class."""

    def test_order_event_creation(self):
        """Test creating an order event."""
        event = OrderEvent(
            order_id="order_123",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            order_type=OrderType.MARKET,
            price=Decimal("50000.00"),
        )

        assert event.event_type == EventType.ORDER
        assert event.order_id == "order_123"
        assert event.symbol == "BTCUSDT"
        assert event.side == OrderSide.BUY
        assert event.quantity == Decimal("1.0")
        assert event.order_type == OrderType.MARKET
        assert event.price == Decimal("50000.00")

    def test_order_event_validation(self):
        """Test order event validation."""
        with pytest.raises(ValidationError):
            OrderEvent(
                order_id="order_123",
                symbol="BTCUSDT",
                side="INVALID",  # Invalid side
                quantity=Decimal("1.0"),
                order_type=OrderType.MARKET,
            )

        with pytest.raises(ValidationError):
            OrderEvent(
                order_id="order_123",
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                quantity=Decimal("0.0"),  # Zero quantity should fail
                order_type=OrderType.MARKET,
            )


class TestFillEvent:
    """Test the FillEvent class."""

    def test_fill_event_creation(self):
        """Test creating a fill event."""
        event = FillEvent(
            order_id="order_123",
            symbol="BTCUSDT",
            executed_qty=Decimal("1.0"),
            executed_price=Decimal("50000.00"),
            commission=Decimal("0.1"),
        )

        assert event.event_type == EventType.FILL
        assert event.order_id == "order_123"
        assert event.symbol == "BTCUSDT"
        assert event.executed_qty == Decimal("1.0")
        assert event.executed_price == Decimal("50000.00")
        assert event.commission == Decimal("0.1")

    def test_fill_event_validation(self):
        """Test fill event validation."""
        with pytest.raises(ValidationError):
            FillEvent(
                order_id="order_123",
                symbol="BTCUSDT",
                executed_qty=Decimal("-1.0"),  # Negative quantity should fail
                executed_price=Decimal("50000.00"),
                commission=Decimal("0.1"),
            )


class TestSignalEvent:
    """Test the SignalEvent class."""

    def test_signal_event_creation(self):
        """Test creating a signal event."""
        event = SignalEvent(
            symbol="BTCUSDT",
            signal_type=SignalType.BUY,
            strength=Decimal("0.8"),
            strategy_id="moving_average_001",
        )

        assert event.event_type == EventType.SIGNAL
        assert event.symbol == "BTCUSDT"
        assert event.signal_type == SignalType.BUY
        assert event.strength == Decimal("0.8")
        assert event.strategy_id == "moving_average_001"

    def test_signal_event_validation(self):
        """Test signal event validation."""
        with pytest.raises(ValidationError):
            SignalEvent(
                symbol="BTCUSDT",
                signal_type=SignalType.BUY,
                strength=Decimal("1.5"),  # Strength > 1.0 should fail
                strategy_id="moving_average_001",
            )

        with pytest.raises(ValidationError):
            SignalEvent(
                symbol="BTCUSDT",
                signal_type=SignalType.BUY,
                strength=Decimal("-0.1"),  # Negative strength should fail
                strategy_id="moving_average_001",
            )
