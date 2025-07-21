"""
Unit tests for the Paper Trading Broker implementation.

Tests realistic order execution, slippage models, and P&L calculation
following TDD principles.
"""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from silvertine.core.event.events import MarketDataEvent
from silvertine.core.event.events import OrderEvent
from silvertine.core.event.events import OrderSide
from silvertine.core.event.events import OrderType
from silvertine.exchanges.paper.paper_broker import PaperTradingBroker
from silvertine.exchanges.paper.paper_broker import PaperTradingConfig
from silvertine.exchanges.paper.paper_broker import SlippageModel


class TestPaperTradingConfig:
    """Test paper trading configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = PaperTradingConfig()

        assert config.initial_balance == Decimal("100000.0")
        assert config.base_currency == "USD"
        assert config.latency_ms == 50
        assert config.slippage_model == SlippageModel.PERCENTAGE
        assert config.slippage_value == Decimal("0.0005")
        assert config.commission_rate == Decimal("0.001")

    def test_custom_config(self):
        """Test custom configuration values."""
        config = PaperTradingConfig(
            initial_balance=Decimal("50000.0"),
            base_currency="EUR",
            latency_ms=100,
            slippage_model=SlippageModel.FIXED,
            slippage_value=Decimal("0.01"),
        )

        assert config.initial_balance == Decimal("50000.0")
        assert config.base_currency == "EUR"
        assert config.latency_ms == 100
        assert config.slippage_model == SlippageModel.FIXED


class TestPaperTradingBroker:
    """Test paper trading broker functionality."""

    @pytest.fixture
    async def broker_setup(self):
        """Setup broker with event bus for testing."""
        event_bus = AsyncMock()
        config = PaperTradingConfig(
            initial_balance=Decimal("100000.0"),
            latency_ms=10,  # Fast for testing
            commission_rate=Decimal("0.001"),
        )
        broker = PaperTradingBroker(event_bus, config)
        await broker.initialize()
        return broker, event_bus

    @pytest.mark.asyncio
    async def test_broker_initialization(self, broker_setup):
        """Test broker initializes with correct state."""
        broker, event_bus = broker_setup

        assert broker.broker_id == "paper_trading"
        assert broker.is_connected
        assert broker._balances["USD"].total == Decimal("100000.0")
        assert broker._balances["USD"].available == Decimal("100000.0")

    @pytest.mark.asyncio
    async def test_market_order_execution(self, broker_setup):
        """Test market order immediate execution."""
        broker, event_bus = broker_setup

        # Set up market price
        broker._last_prices["BTC/USD"] = Decimal("40000.0")

        order = OrderEvent(
            order_id="test_order",
            symbol="BTC/USD",
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            order_type=OrderType.MARKET,
        )

        # Execute order
        broker_order_id = await broker.place_order(order)
        await asyncio.sleep(0.1)  # Wait for execution

        assert broker_order_id == "PAPER_test_order"
        # Check fill event was published
        event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_limit_order_execution(self, broker_setup):
        """Test limit order waits for price."""
        broker, event_bus = broker_setup

        # Set initial price above limit
        broker._last_prices["BTC/USD"] = Decimal("41000.0")

        order = OrderEvent(
            order_id="test_order",
            symbol="BTC/USD",
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            order_type=OrderType.LIMIT,
            price=Decimal("40000.0"),
        )

        # Place order - should not execute immediately
        await broker.place_order(order)
        await asyncio.sleep(0.05)

        # Order should be pending
        assert "test_order" in broker._execution_tasks

        # Update price to trigger execution
        broker._last_prices["BTC/USD"] = Decimal("39500.0")  # Below limit price
        await asyncio.sleep(0.2)  # Wait for execution

        # Check execution occurred
        event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_order_cancellation(self, broker_setup):
        """Test order cancellation."""
        broker, event_bus = broker_setup

        # Place limit order that won't execute
        broker._last_prices["BTC/USD"] = Decimal("41000.0")

        order = OrderEvent(
            order_id="test_order",
            symbol="BTC/USD",
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            order_type=OrderType.LIMIT,
            price=Decimal("40000.0"),
        )

        await broker.place_order(order)

        # Cancel order
        result = await broker.cancel_order("test_order")

        assert result is True
        assert "test_order" not in broker._execution_tasks
        assert "test_order" not in broker._active_orders

    @pytest.mark.asyncio
    async def test_slippage_models(self, broker_setup):
        """Test different slippage models."""
        broker, event_bus = broker_setup

        base_price = Decimal("40000.0")
        quantity = Decimal("1.0")

        # Test fixed slippage
        slipped_price = broker._apply_slippage(
            base_price, OrderSide.BUY, quantity, SlippageModel.FIXED, Decimal("10.0")
        )
        assert slipped_price == Decimal("40010.0")  # Buy adds slippage

        # Test percentage slippage
        slipped_price = broker._apply_slippage(
            base_price, OrderSide.SELL, quantity, SlippageModel.PERCENTAGE, Decimal("0.001")
        )
        expected = base_price - (base_price * Decimal("0.001"))
        assert slipped_price == expected

        # Test market impact slippage
        large_quantity = Decimal("100.0")
        slipped_price = broker._apply_slippage(
            base_price, OrderSide.BUY, large_quantity, SlippageModel.MARKET_IMPACT, Decimal("0.0001")
        )
        # Larger orders have more impact
        assert slipped_price > base_price

    @pytest.mark.asyncio
    async def test_position_tracking(self, broker_setup):
        """Test position creation and updates."""
        broker, event_bus = broker_setup

        # Set market price
        broker._last_prices["BTC/USD"] = Decimal("40000.0")

        # Execute buy order
        await broker._process_fill(
            symbol="BTC/USD",
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            price=Decimal("40000.0"),
            commission=Decimal("40.0"),
        )

        # Check position was created
        positions = await broker.get_positions()
        assert "BTC/USD" in positions

        position = positions["BTC/USD"]
        assert position.quantity == Decimal("1.0")
        assert position.average_price == Decimal("40000.0")
        assert position.is_long is True

    @pytest.mark.asyncio
    async def test_balance_updates(self, broker_setup):
        """Test balance updates from trades."""
        broker, event_bus = broker_setup

        initial_balance = broker._balances["USD"].available

        # Execute buy order
        await broker._process_fill(
            symbol="BTC/USD",
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            price=Decimal("40000.0"),
            commission=Decimal("40.0"),
        )

        # Check balance decreased
        new_balance = broker._balances["USD"].available
        cost = Decimal("40000.0") + Decimal("40.0")  # Price + commission
        assert new_balance == initial_balance - cost

    @pytest.mark.asyncio
    async def test_pnl_calculation(self, broker_setup):
        """Test P&L calculation with price changes."""
        broker, event_bus = broker_setup

        # Execute buy order
        await broker._process_fill(
            symbol="BTC/USD",
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            price=Decimal("40000.0"),
            commission=Decimal("40.0"),
        )

        # Update market price
        broker._last_prices["BTC/USD"] = Decimal("42000.0")

        # Get updated positions
        positions = await broker.get_positions()
        position = positions["BTC/USD"]

        # Check unrealized P&L
        expected_pnl = Decimal("1.0") * (Decimal("42000.0") - Decimal("40000.0"))
        assert position.unrealized_pnl == expected_pnl  # $2000 profit

    @pytest.mark.asyncio
    async def test_order_validation(self, broker_setup):
        """Test order validation for insufficient funds."""
        broker, event_bus = broker_setup

        # Disable random rejections for this test
        broker.sim_config.rejection_probability = Decimal("0.0")

        # Try to buy more than available balance
        broker._last_prices["BTC/USD"] = Decimal("40000.0")

        order = OrderEvent(
            order_id="large_order",
            symbol="BTC/USD",
            side=OrderSide.BUY,
            quantity=Decimal("10.0"),  # $400K order with only $100K balance
            order_type=OrderType.MARKET,
        )

        # Should raise exception due to insufficient funds
        with pytest.raises(Exception, match="insufficient funds"):
            await broker.place_order(order)

    @pytest.mark.asyncio
    async def test_commission_calculation(self, broker_setup):
        """Test commission calculation and tracking."""
        broker, event_bus = broker_setup

        broker._last_prices["BTC/USD"] = Decimal("40000.0")

        # Execute order
        await broker._process_fill(
            symbol="BTC/USD",
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            price=Decimal("40000.0"),
            commission=Decimal("40.0"),  # 0.1% commission
        )

        # Check commission was deducted from balance
        expected_cost = Decimal("40000.0") + Decimal("40.0")
        balance_change = Decimal("100000.0") - broker._balances["USD"].available
        assert balance_change == expected_cost

    @pytest.mark.asyncio
    async def test_market_data_integration(self, broker_setup):
        """Test integration with market data events."""
        broker, event_bus = broker_setup

        # Create market data event
        market_event = MarketDataEvent(
            symbol="BTC/USD",
            price=Decimal("40000.0"),
            volume=Decimal("100.0"),
            bid=Decimal("39990.0"),
            ask=Decimal("40010.0"),
        )

        # Process market data
        await broker._handle_market_data(market_event)

        # Check price was updated
        assert broker._last_prices["BTC/USD"] == Decimal("40000.0")
        assert broker._order_books["BTC/USD"]["bid"] == Decimal("39990.0")
        assert broker._order_books["BTC/USD"]["ask"] == Decimal("40010.0")

    @pytest.mark.asyncio
    async def test_account_info(self, broker_setup):
        """Test account information retrieval."""
        broker, event_bus = broker_setup

        # Execute some trades to create positions
        broker._last_prices["BTC/USD"] = Decimal("40000.0")
        await broker._process_fill(
            symbol="BTC/USD",
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            price=Decimal("40000.0"),
            commission=Decimal("40.0"),
        )

        # Get account info
        account_info = await broker.get_account_info()

        assert account_info.account_id == "PAPER_TRADING"
        assert account_info.broker_name == "Paper Trading Simulator"
        assert account_info.base_currency == "USD"
        assert "USD" in account_info.balances
        assert "BTC/USD" in account_info.positions
