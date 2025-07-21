"""
Unit tests for the broker interface implementation.

Tests the AbstractBroker base class, data structures, and event integration
following TDD principles.
"""

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from silvertine.core.event.event_bus import EventBus
from silvertine.core.event.event_bus import HandlerPriority
from silvertine.core.event.events import EventType
from silvertine.core.event.events import FillEvent
from silvertine.core.event.events import OrderEvent
from silvertine.core.event.events import OrderSide
from silvertine.core.event.events import OrderStatus
from silvertine.core.event.events import OrderType
from silvertine.exchanges.iexchange import AbstractBroker
from silvertine.exchanges.iexchange import BrokerAccountInfo
from silvertine.exchanges.iexchange import BrokerBalance
from silvertine.exchanges.iexchange import BrokerPosition
from silvertine.exchanges.iexchange import ConnectionState


# Mock concrete broker for testing
class MockBroker(AbstractBroker):
    """Mock broker implementation for testing."""

    def __init__(self, event_bus: EventBus, broker_id: str = "mock_broker", config: dict[str, Any] | None = None):
        super().__init__(event_bus, broker_id, config)
        self.connected = False
        self.positions = {}
        self.balances = {}

    async def connect(self) -> None:
        self._connection_state = ConnectionState.CONNECTED
        self.connected = True

    async def disconnect(self) -> None:
        self._connection_state = ConnectionState.DISCONNECTED
        self.connected = False

    async def place_order(self, order: OrderEvent) -> str:
        return f"broker_{order.order_id}"

    async def cancel_order(self, order_id: str) -> bool:
        return True

    async def modify_order(self, order_id: str, quantity=None, price=None) -> bool:
        return True

    async def get_positions(self):
        return self.positions

    async def get_position(self, symbol: str):
        return self.positions.get(symbol)

    async def get_account_info(self):
        return BrokerAccountInfo(
            account_id="test_account",
            broker_name=self.broker_id,
            account_type="margin",
            base_currency="USD",
            balances=self.balances,
            positions=self.positions,
        )

    async def get_balance(self, currency=None):
        if currency:
            return {currency: self.balances.get(currency)}
        return self.balances


class TestBrokerDataStructures:
    """Test broker data structures."""

    def test_broker_position_creation(self):
        """Test BrokerPosition creation and properties."""
        position = BrokerPosition(
            symbol="BTC/USD",
            quantity=Decimal("2.5"),
            average_price=Decimal("40000.0"),
            current_price=Decimal("45000.0"),
        )

        assert position.symbol == "BTC/USD"
        assert position.quantity == Decimal("2.5")
        assert position.average_price == Decimal("40000.0")
        assert position.current_price == Decimal("45000.0")
        assert position.market_value == Decimal("112500.0")  # 2.5 * 45000
        assert position.cost_basis == Decimal("100000.0")  # 2.5 * 40000
        assert position.is_long is True
        assert position.is_short is False

        # Test P&L calculation
        position.update_unrealized_pnl()
        expected_pnl = Decimal("2.5") * (Decimal("45000.0") - Decimal("40000.0"))
        assert position.unrealized_pnl == expected_pnl  # 12500.0

    def test_broker_balance_creation(self):
        """Test BrokerBalance creation and properties."""
        balance = BrokerBalance(
            currency="USD",
            available=Decimal("50000.0"),
            total=Decimal("60000.0"),
            margin_used=Decimal("5000.0"),
            unrealized_pnl=Decimal("2000.0"),
        )

        assert balance.currency == "USD"
        assert balance.available == Decimal("50000.0")
        assert balance.total == Decimal("60000.0")
        assert balance.margin_available == Decimal("45000.0")  # 50000 - 5000
        assert balance.equity == Decimal("62000.0")  # 60000 + 2000

    def test_broker_account_info_creation(self):
        """Test BrokerAccountInfo creation and properties."""
        balance = BrokerBalance(currency="USD", available=Decimal("50000"), total=Decimal("60000"))
        position = BrokerPosition(
            symbol="BTC/USD",
            quantity=Decimal("1.0"),
            average_price=Decimal("40000"),
            unrealized_pnl=Decimal("5000"),
        )

        account = BrokerAccountInfo(
            account_id="test_account",
            broker_name="test_broker",
            account_type="margin",
            base_currency="USD",
            balances={"USD": balance},
            positions={"BTC/USD": position},
        )

        assert account.account_id == "test_account"
        assert account.broker_name == "test_broker"
        assert account.total_equity == Decimal("60000")  # Only balance equity
        assert account.total_unrealized_pnl == Decimal("5000")  # Position P&L


class TestAbstractBroker:
    """Test AbstractBroker base class."""

    def test_broker_initialization(self):
        """Test broker initializes correctly."""
        event_bus = MagicMock()
        broker = MockBroker(event_bus, "test_broker")

        assert broker.broker_id == "test_broker"
        assert broker.event_bus == event_bus
        assert broker.connection_state == ConnectionState.DISCONNECTED
        assert broker.is_connected is False
        assert broker.metrics.orders_placed == 0

    @pytest.mark.asyncio
    async def test_broker_event_subscription(self):
        """Test broker subscribes to order events."""
        event_bus = MagicMock()
        broker = MockBroker(event_bus, "test_broker")

        await broker.initialize()

        # Verify subscription was called
        event_bus.subscribe.assert_called_once_with(
            event_type=EventType.ORDER,
            handler=broker._handle_order_event,
            priority=HandlerPriority.HIGH,
        )

    @pytest.mark.asyncio
    async def test_broker_publishes_fill_events(self):
        """Test broker publishes fill events on execution."""
        event_bus = AsyncMock()
        broker = MockBroker(event_bus, "test_broker")

        await broker._publish_fill_event(
            order_id="test_order",
            symbol="BTC/USD",
            executed_quantity=Decimal("1.0"),
            executed_price=Decimal("40000.0"),
            commission=Decimal("10.0"),
        )

        # Verify fill event was published
        event_bus.publish.assert_called_once()
        published_event = event_bus.publish.call_args[0][0]
        assert isinstance(published_event, FillEvent)
        assert published_event.order_id == "test_order"
        assert published_event.symbol == "BTC/USD"
        assert published_event.executed_qty == Decimal("1.0")
        assert published_event.executed_price == Decimal("40000.0")
        assert published_event.commission == Decimal("10.0")

    @pytest.mark.asyncio
    async def test_broker_metrics_collection(self):
        """Test broker collects performance metrics."""
        event_bus = AsyncMock()
        broker = MockBroker(event_bus, "test_broker")

        # Simulate order handling
        order = OrderEvent(
            order_id="test_order",
            symbol="BTC/USD",
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            order_type=OrderType.MARKET,
        )

        await broker._handle_order_event(order)

        # Check metrics
        assert broker.metrics.orders_placed == 1
        assert broker.metrics.average_latency_ms >= 0
        assert broker.metrics.last_order_time is not None

    @pytest.mark.asyncio
    async def test_broker_connection_management(self):
        """Test broker connection state management."""
        event_bus = MagicMock()
        broker = MockBroker(event_bus, "test_broker")

        # Initial state
        assert broker.connection_state == ConnectionState.DISCONNECTED
        assert not broker.is_connected

        # Connect
        await broker.connect()
        assert broker.connection_state == ConnectionState.CONNECTED
        assert broker.is_connected

        # Disconnect
        await broker.disconnect()
        assert broker.connection_state == ConnectionState.DISCONNECTED
        assert not broker.is_connected

    @pytest.mark.asyncio
    async def test_broker_order_tracking(self):
        """Test broker tracks active orders."""
        event_bus = AsyncMock()
        broker = MockBroker(event_bus, "test_broker")

        order = OrderEvent(
            order_id="test_order",
            symbol="BTC/USD",
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            order_type=OrderType.MARKET,
        )

        # Handle order - should add to active orders
        await broker._handle_order_event(order)

        assert "test_order" in broker._active_orders
        assert "test_order" in broker._order_mapping
        assert broker._order_mapping["test_order"] == "broker_test_order"

        # Simulate fill - should remove from active orders
        await broker._publish_fill_event(
            order_id="test_order",
            symbol="BTC/USD",
            executed_quantity=Decimal("1.0"),  # Full fill
            executed_price=Decimal("40000.0"),
        )

        assert "test_order" not in broker._active_orders
        assert "test_order" not in broker._order_mapping

    @pytest.mark.asyncio
    async def test_broker_error_handling(self):
        """Test broker handles errors gracefully."""
        event_bus = AsyncMock()

        # Create broker that fails on order placement
        class FailingBroker(MockBroker):
            async def place_order(self, order):
                raise Exception("Connection error")

        broker = FailingBroker(event_bus, "failing_broker")

        order = OrderEvent(
            order_id="test_order",
            symbol="BTC/USD",
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            order_type=OrderType.MARKET,
        )

        # Should handle error gracefully
        await broker._handle_order_event(order)

        # Check metrics updated
        assert broker.metrics.orders_rejected == 1
        assert "test_order" not in broker._active_orders

        # Verify rejection event published
        event_bus.publish.assert_called()


class TestBrokerEventIntegration:
    """Test broker integration with event system."""

    @pytest.mark.asyncio
    async def test_order_event_handling(self):
        """Test broker handles incoming order events."""
        event_bus = AsyncMock()
        broker = MockBroker(event_bus, "test_broker")

        order = OrderEvent(
            order_id="test_order",
            symbol="BTC/USD",
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            order_type=OrderType.LIMIT,
            price=Decimal("40000.0"),
        )

        await broker._handle_order_event(order)

        # Should publish order update event
        event_bus.publish.assert_called()
        assert broker.metrics.orders_placed == 1

    @pytest.mark.asyncio
    async def test_fill_event_publishing(self):
        """Test broker publishes fill events correctly."""
        event_bus = AsyncMock()
        broker = MockBroker(event_bus, "test_broker")

        await broker._publish_fill_event(
            order_id="test_order",
            symbol="BTC/USD",
            executed_quantity=Decimal("0.5"),
            executed_price=Decimal("40000.0"),
            commission=Decimal("5.0"),
        )

        # Verify correct event published
        event_bus.publish.assert_called_once()
        fill_event = event_bus.publish.call_args[0][0]
        assert isinstance(fill_event, FillEvent)
        assert fill_event.executed_qty == Decimal("0.5")

    @pytest.mark.asyncio
    async def test_order_rejection_handling(self):
        """Test broker handles order rejections."""
        event_bus = AsyncMock()
        broker = MockBroker(event_bus, "test_broker")

        order = OrderEvent(
            order_id="test_order",
            symbol="BTC/USD",
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            order_type=OrderType.MARKET,
        )

        await broker._handle_order_rejection(order, "Insufficient funds")

        # Should publish order update with rejected status
        event_bus.publish.assert_called()
        update_event = event_bus.publish.call_args[0][0]
        assert update_event.status == OrderStatus.REJECTED
        assert update_event.update_reason == "Insufficient funds"

    @pytest.mark.asyncio
    async def test_position_update_events(self):
        """Test broker publishes position update events."""
        event_bus = AsyncMock()
        broker = MockBroker(event_bus, "test_broker")

        position = BrokerPosition(
            symbol="BTC/USD",
            quantity=Decimal("1.0"),
            average_price=Decimal("40000.0"),
            current_price=Decimal("41000.0"),
            unrealized_pnl=Decimal("1000.0"),
        )

        await broker._publish_position_update(position)

        # Verify position update event published
        event_bus.publish.assert_called_once()
        position_event = event_bus.publish.call_args[0][0]
        assert position_event.symbol == "BTC/USD"
        assert position_event.quantity == Decimal("1.0")
        assert position_event.unrealized_pnl == Decimal("1000.0")
