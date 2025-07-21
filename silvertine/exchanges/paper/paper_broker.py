"""
Paper Trading Broker implementation.

Provides realistic paper trading simulation with configurable slippage models,
commission structures, and order execution behavior for strategy development
and backtesting.
"""

import asyncio
import logging
import random
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from ...core.event.event_bus import HandlerPriority
from ...core.event.events import Event
from ...core.event.events import EventType
from ...core.event.events import MarketDataEvent
from ...core.event.events import OrderEvent
from ...core.event.events import OrderSide
from ...core.event.events import OrderType
from ..iexchange import AbstractBroker
from ..iexchange import BrokerAccountInfo
from ..iexchange import BrokerBalance
from ..iexchange import BrokerPosition
from ..iexchange import ConnectionState

logger = logging.getLogger(__name__)


class SlippageModel(str, Enum):
    """Slippage model enumeration."""

    FIXED = "fixed"
    PERCENTAGE = "percentage"
    MARKET_IMPACT = "market_impact"


@dataclass
class PaperTradingConfig:
    """Configuration for paper trading simulator."""

    initial_balance: Decimal = field(default=Decimal("100000.0"))
    base_currency: str = "USD"
    latency_ms: int = 50
    slippage_model: SlippageModel = SlippageModel.PERCENTAGE
    slippage_value: Decimal = field(default=Decimal("0.0005"))
    commission_rate: Decimal = field(default=Decimal("0.001"))
    partial_fill_probability: Decimal = field(default=Decimal("0.1"))
    rejection_probability: Decimal = field(default=Decimal("0.02"))
    margin_enabled: bool = True
    leverage: Decimal = field(default=Decimal("3.0"))


class PaperTradingBroker(AbstractBroker):
    """
    Realistic paper trading simulator.

    Provides comprehensive order execution simulation with:
    - Multiple slippage models (fixed, percentage, market impact)
    - Configurable latency and commission structures
    - Realistic order execution behaviors
    - Position and P&L tracking
    - Market data integration
    """

    def __init__(self, event_bus, broker_id: str = "paper_trading", config: dict[str, Any] | None = None):
        """
        Initialize paper trading broker.

        Args:
            event_bus: Event bus for communication
            broker_id: Unique broker identifier
            config: Paper trading configuration (dict or PaperTradingConfig)
        """
        # Handle both dict and PaperTradingConfig inputs
        if isinstance(config, PaperTradingConfig):
            self.sim_config = config
        elif isinstance(config, dict):
            # Convert dict to PaperTradingConfig
            self.sim_config = PaperTradingConfig()
            for key, value in config.items():
                if hasattr(self.sim_config, key):
                    # Convert to proper types
                    if key in ['initial_balance', 'slippage_value', 'commission_rate',
                               'partial_fill_probability', 'rejection_probability', 'leverage']:
                        value = Decimal(str(value))
                    elif key == 'slippage_model':
                        # Handle both uppercase and lowercase values
                        value_str = str(value).lower() if isinstance(value, str) else value
                        value = SlippageModel(value_str)

                    setattr(self.sim_config, key, value)
        else:
            self.sim_config = PaperTradingConfig()

        super().__init__(
            event_bus=event_bus,
            broker_id=broker_id,
            config=config or {},
        )

        # Account state
        self._balances = {
            self.sim_config.base_currency: BrokerBalance(
                currency=self.sim_config.base_currency,
                available=self.sim_config.initial_balance,
                total=self.sim_config.initial_balance,
            )
        }

        self._positions: dict[str, BrokerPosition] = {}
        self._execution_history: list[dict] = []

        # Market data cache
        self._last_prices: dict[str, Decimal] = {}
        self._order_books: dict[str, dict] = {}

        # Order execution tasks
        self._execution_tasks: dict[str, asyncio.Task] = {}

    async def connect(self) -> None:
        """Simulate broker connection."""
        self._connection_state = ConnectionState.CONNECTING

        # Simulate connection delay
        await asyncio.sleep(self.sim_config.latency_ms / 1000.0)

        # Subscribe to market data for price updates
        self.event_bus.subscribe(
            event_type=EventType.MARKET_DATA,
            handler=self._handle_market_data,
            priority=HandlerPriority.NORMAL,
        )

        self._connection_state = ConnectionState.CONNECTED

    async def disconnect(self) -> None:
        """Disconnect simulator."""
        # Cancel all execution tasks
        for task in self._execution_tasks.values():
            if not task.done():
                task.cancel()

        # Wait for tasks to complete
        if self._execution_tasks:
            await asyncio.gather(*self._execution_tasks.values(), return_exceptions=True)

        self._execution_tasks.clear()
        self._connection_state = ConnectionState.DISCONNECTED

    async def place_order(self, order: OrderEvent) -> str:
        """
        Simulate order placement with realistic behavior.

        Args:
            order: Order to place

        Returns:
            Broker order ID

        Raises:
            Exception: If order validation fails or insufficient funds
        """
        # Simulate latency
        await asyncio.sleep(self.sim_config.latency_ms / 1000.0)

        # Random rejection simulation
        if random.random() < float(self.sim_config.rejection_probability):
            raise Exception("Order rejected by exchange")

        # Validate order
        if not await self._validate_order(order):
            raise Exception("Order validation failed: insufficient funds or invalid parameters")

        # Generate broker order ID
        broker_order_id = f"PAPER_{order.order_id}"

        # Store order in active orders
        self._active_orders[order.order_id] = order

        # Schedule execution
        execution_task = asyncio.create_task(self._execute_order(order, broker_order_id))
        self._execution_tasks[order.order_id] = execution_task

        return broker_order_id

    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an active order.

        Args:
            order_id: Internal order ID

        Returns:
            True if cancellation successful
        """
        if order_id in self._execution_tasks:
            task = self._execution_tasks[order_id]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            del self._execution_tasks[order_id]

            if order_id in self._active_orders:
                del self._active_orders[order_id]

            return True
        return False

    async def modify_order(
        self,
        order_id: str,
        quantity: Decimal | None = None,
        price: Decimal | None = None,
    ) -> bool:
        """
        Modify an existing order (not implemented for paper trading).

        Args:
            order_id: Internal order ID
            quantity: New quantity
            price: New price

        Returns:
            False (not supported)
        """
        # Paper trading doesn't support order modification
        return False

    async def get_positions(self) -> dict[str, BrokerPosition]:
        """
        Get all positions with updated P&L.

        Returns:
            Dictionary of positions by symbol
        """
        # Update current prices and P&L
        for symbol, position in self._positions.items():
            if symbol in self._last_prices:
                position.current_price = self._last_prices[symbol]
                position.update_unrealized_pnl()

        return self._positions.copy()

    async def get_position(self, symbol: str) -> BrokerPosition | None:
        """
        Get position for specific symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Position or None if not found
        """
        positions = await self.get_positions()
        return positions.get(symbol)

    async def get_account_info(self) -> BrokerAccountInfo:
        """
        Get complete account information.

        Returns:
            Account information
        """
        return BrokerAccountInfo(
            account_id="PAPER_TRADING",
            broker_name="Paper Trading Simulator",
            account_type="margin" if self.sim_config.margin_enabled else "cash",
            base_currency=self.sim_config.base_currency,
            leverage=self.sim_config.leverage,
            balances=self._balances.copy(),
            positions=await self.get_positions(),
        )

    async def get_balance(self, currency: str | None = None) -> dict[str, BrokerBalance]:
        """
        Get account balance(s).

        Args:
            currency: Specific currency (optional)

        Returns:
            Dictionary of balances by currency
        """
        if currency:
            balance = self._balances.get(currency)
            return {currency: balance} if balance is not None else {}
        return self._balances.copy()

    async def _validate_order(self, order: OrderEvent) -> bool:
        """
        Validate order against account state.

        Args:
            order: Order to validate

        Returns:
            True if order is valid
        """
        # Get symbol price
        symbol_price = self._last_prices.get(order.symbol, order.price or Decimal("100.0"))

        # Calculate required balance
        required_balance = order.quantity * symbol_price

        # Add margin for commission
        required_balance *= (Decimal("1") + self.sim_config.commission_rate)

        # Check available balance
        balance = self._balances.get(self.sim_config.base_currency)
        if not balance or balance.available < required_balance:
            return False

        # Check margin requirements if applicable
        if self.sim_config.margin_enabled:
            margin_required = required_balance / self.sim_config.leverage
            if balance.available < margin_required:
                return False

        return True

    async def _execute_order(self, order: OrderEvent, broker_order_id: str) -> None:
        """
        Execute order with realistic behavior.

        Args:
            order: Order to execute
            broker_order_id: Broker order ID
        """
        try:
            # Market orders execute immediately
            if order.order_type == OrderType.MARKET:
                await self._execute_market_order(order, broker_order_id)

            # Limit orders wait for price
            elif order.order_type == OrderType.LIMIT:
                await self._execute_limit_order(order, broker_order_id)

            # Stop orders wait for trigger
            elif order.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
                await self._execute_stop_order(order, broker_order_id)

        except asyncio.CancelledError:
            # Order cancelled
            self._metrics.orders_cancelled += 1
            raise
        except Exception as e:
            # Execution failed
            await self._handle_order_rejection(order, str(e))
        finally:
            # Clean up execution task
            if order.order_id in self._execution_tasks:
                del self._execution_tasks[order.order_id]

    async def _execute_market_order(self, order: OrderEvent, broker_order_id: str) -> None:
        """
        Execute market order immediately.

        Args:
            order: Market order to execute
            broker_order_id: Broker order ID
        """
        # Get current price
        symbol_price = self._last_prices.get(order.symbol)
        if not symbol_price:
            raise Exception("No market data available for symbol")

        # Apply slippage
        execution_price = self._apply_slippage(
            symbol_price, order.side, order.quantity, self.sim_config.slippage_model, self.sim_config.slippage_value
        )

        # Simulate partial fills
        if random.random() < float(self.sim_config.partial_fill_probability):
            # Execute in multiple fills
            remaining = order.quantity
            while remaining > Decimal("0"):
                fill_quantity = min(remaining, order.quantity * Decimal(str(random.uniform(0.1, 0.5))))

                await self._process_fill(
                    symbol=order.symbol,
                    side=order.side,
                    quantity=fill_quantity,
                    price=execution_price,
                    commission=fill_quantity * execution_price * self.sim_config.commission_rate,
                )

                remaining -= fill_quantity

                # Small delay between fills
                await asyncio.sleep(0.1)
        else:
            # Single fill
            await self._process_fill(
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                price=execution_price,
                commission=order.quantity * execution_price * self.sim_config.commission_rate,
            )

        # Publish fill event
        await self._publish_fill_event(
            order_id=order.order_id,
            symbol=order.symbol,
            executed_quantity=order.quantity,
            executed_price=execution_price,
            commission=order.quantity * execution_price * self.sim_config.commission_rate,
        )

    async def _execute_limit_order(self, order: OrderEvent, broker_order_id: str) -> None:
        """
        Execute limit order when price conditions are met.

        Args:
            order: Limit order to execute
            broker_order_id: Broker order ID
        """
        while order.order_id in self._active_orders:
            current_price = self._last_prices.get(order.symbol)
            if not current_price:
                await asyncio.sleep(0.1)
                continue

            # Check if limit price is met
            if order.price is None:
                logger.error("Limit order %s has no price set", order.order_id)
                continue

            price_met = False
            if order.side == OrderSide.BUY and current_price <= order.price:
                price_met = True
            elif order.side == OrderSide.SELL and current_price >= order.price:
                price_met = True

            if price_met:
                # Execute at limit price (or better)
                execution_price = order.price

                commission = order.quantity * execution_price * self.sim_config.commission_rate

                await self._process_fill(
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    price=execution_price,
                    commission=commission,
                )

                # Publish fill event
                await self._publish_fill_event(
                    order_id=order.order_id,
                    symbol=order.symbol,
                    executed_quantity=order.quantity,
                    executed_price=execution_price,
                    commission=commission,
                )
                break

            await asyncio.sleep(0.1)

    async def _execute_stop_order(self, order: OrderEvent, broker_order_id: str) -> None:
        """
        Execute stop order when stop price is triggered.

        Args:
            order: Stop order to execute
            broker_order_id: Broker order ID
        """
        # Wait for stop price trigger
        while order.order_id in self._active_orders:
            current_price = self._last_prices.get(order.symbol)
            if not current_price:
                await asyncio.sleep(0.1)
                continue

            # Check if stop price is triggered
            if order.stop_price is None:
                logger.error("Stop order %s has no stop_price set", order.order_id)
                break

            triggered = False
            if order.side == OrderSide.BUY and current_price >= order.stop_price:
                triggered = True
            elif order.side == OrderSide.SELL and current_price <= order.stop_price:
                triggered = True

            if triggered:
                # Convert to market order for execution
                if order.order_type == OrderType.STOP:
                    execution_price = current_price
                else:  # STOP_LIMIT
                    if order.price is None:
                        logger.error("Stop-limit order %s has no limit price set", order.order_id)
                        break
                    execution_price = order.price

                commission = order.quantity * execution_price * self.sim_config.commission_rate

                await self._process_fill(
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    price=execution_price,
                    commission=commission,
                )

                # Publish fill event
                await self._publish_fill_event(
                    order_id=order.order_id,
                    symbol=order.symbol,
                    executed_quantity=order.quantity,
                    executed_price=execution_price,
                    commission=commission,
                )
                break

            await asyncio.sleep(0.1)

    def _apply_slippage(
        self,
        price: Decimal,
        side: OrderSide,
        quantity: Decimal,
        slippage_model: SlippageModel,
        slippage_value: Decimal,
    ) -> Decimal:
        """
        Apply slippage model to execution price.

        Args:
            price: Base price
            side: Order side
            quantity: Order quantity
            slippage_model: Slippage model to use
            slippage_value: Slippage parameter

        Returns:
            Price with slippage applied
        """
        if slippage_model == SlippageModel.FIXED:
            slippage = slippage_value
        elif slippage_model == SlippageModel.PERCENTAGE:
            slippage = price * slippage_value
        else:  # MARKET_IMPACT
            # Larger orders have more impact
            impact_factor = min(quantity / Decimal("10000.0"), Decimal("0.01"))  # Max 1% impact
            slippage = price * impact_factor

        # Apply slippage in unfavorable direction
        if side == OrderSide.BUY:
            return price + slippage
        else:
            return price - slippage

    async def _process_fill(
        self,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        price: Decimal,
        commission: Decimal,
    ) -> None:
        """
        Process order fill and update positions/balances.

        Args:
            symbol: Trading symbol
            side: Order side
            quantity: Executed quantity
            price: Execution price
            commission: Commission paid
        """
        # Update position
        await self._update_position(symbol, side, quantity, price, commission)

        # Update balance
        total_cost = (quantity * price) + commission
        base_balance = self._balances[self.sim_config.base_currency]

        if side == OrderSide.BUY:
            base_balance.available -= total_cost
        else:
            base_balance.available += total_cost - (commission * Decimal("2"))  # Deduct commission twice for sell

        # Record execution
        self._execution_history.append(
            {
                "timestamp": datetime.now(timezone.utc),
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": price,
                "commission": commission,
                "slippage": price - self._last_prices.get(symbol, price),
            }
        )

    async def _update_position(
        self, symbol: str, side: OrderSide, quantity: Decimal, price: Decimal, commission: Decimal
    ) -> None:
        """
        Update or create position.

        Args:
            symbol: Trading symbol
            side: Order side
            quantity: Quantity
            price: Price
            commission: Commission
        """
        if symbol not in self._positions:
            # New position
            position_quantity = quantity if side == OrderSide.BUY else -quantity
            self._positions[symbol] = BrokerPosition(
                symbol=symbol,
                quantity=position_quantity,
                average_price=price,
                current_price=price,
                commission_paid=commission,
            )
        else:
            # Update existing position
            position = self._positions[symbol]

            if side == OrderSide.BUY:
                # Adding to position
                new_quantity = position.quantity + quantity
                if new_quantity != Decimal("0"):
                    # Calculate new average price
                    total_cost = (position.quantity * position.average_price) + (quantity * price)
                    position.average_price = total_cost / new_quantity
                position.quantity = new_quantity
            else:
                # Reducing position
                position.quantity -= quantity

                # Handle position flipping or closing
                if position.quantity < Decimal("0"):
                    # Position flipped to short
                    position.average_price = price
                elif position.quantity == Decimal("0"):
                    # Position closed
                    del self._positions[symbol]
                    return

            position.commission_paid += commission

        # Publish position update
        if symbol in self._positions:
            await self._publish_position_update(self._positions[symbol])

    async def _handle_market_data(self, event: Event) -> None:
        """
        Update market prices from market data events.

        Args:
            event: Market data event
        """
        # Cast to MarketDataEvent - we know it's the right type from subscription
        if not isinstance(event, MarketDataEvent):
            return

        self._last_prices[event.symbol] = event.price

        # Update order book if available
        if event.bid is not None and event.ask is not None:
            self._order_books[event.symbol] = {
                "bid": event.bid,
                "ask": event.ask,
                "bid_size": getattr(event, "bid_size", Decimal("0")),
                "ask_size": getattr(event, "ask_size", Decimal("0")),
            }
