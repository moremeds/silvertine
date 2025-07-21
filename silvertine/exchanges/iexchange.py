"""
Abstract broker interface for the trading system.

This module defines the AbstractBroker base class and data structures for
broker implementations, providing a unified interface for different exchanges
and trading platforms.
"""

import uuid
from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from ..core.event.event_bus import EventBus
from ..core.event.event_bus import HandlerPriority
from ..core.event.events import Event
from ..core.event.events import EventType
from ..core.event.events import FillEvent
from ..core.event.events import OrderEvent
from ..core.event.events import OrderStatus
from ..core.event.events import OrderUpdateEvent
from ..core.event.events import PositionUpdateEvent


class ConnectionState(Enum):
    """Broker connection state enumeration."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RECONNECTING = "reconnecting"


@dataclass
class BrokerPosition:
    """Represents a position held at a broker."""

    symbol: str
    quantity: Decimal
    average_price: Decimal
    current_price: Decimal = field(default=Decimal("0"))
    unrealized_pnl: Decimal = field(default=Decimal("0"))
    realized_pnl: Decimal = field(default=Decimal("0"))
    commission_paid: Decimal = field(default=Decimal("0"))

    @property
    def market_value(self) -> Decimal:
        """Calculate current market value of position."""
        return self.quantity * self.current_price

    @property
    def cost_basis(self) -> Decimal:
        """Calculate cost basis of position."""
        return abs(self.quantity) * self.average_price

    @property
    def is_long(self) -> bool:
        """Check if position is long."""
        return self.quantity > 0

    @property
    def is_short(self) -> bool:
        """Check if position is short."""
        return self.quantity < 0

    def update_unrealized_pnl(self) -> None:
        """Update unrealized P&L based on current price."""
        if self.current_price > 0:
            self.unrealized_pnl = self.quantity * (self.current_price - self.average_price)


@dataclass
class BrokerBalance:
    """Account balance information for a specific currency."""

    currency: str
    available: Decimal
    total: Decimal
    margin_used: Decimal = field(default=Decimal("0"))
    unrealized_pnl: Decimal = field(default=Decimal("0"))

    @property
    def margin_available(self) -> Decimal:
        """Calculate available margin."""
        return self.available - self.margin_used

    @property
    def equity(self) -> Decimal:
        """Calculate account equity including unrealized P&L."""
        return self.total + self.unrealized_pnl


@dataclass
class BrokerAccountInfo:
    """Complete account information from broker."""

    account_id: str
    broker_name: str
    account_type: str  # cash, margin, futures
    base_currency: str
    leverage: Decimal = field(default=Decimal("1.0"))
    balances: dict[str, BrokerBalance] = field(default_factory=dict)
    positions: dict[str, BrokerPosition] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_equity(self) -> Decimal:
        """Calculate total account equity across all currencies."""
        return sum(balance.equity for balance in self.balances.values()) or Decimal("0")

    @property
    def total_unrealized_pnl(self) -> Decimal:
        """Calculate total unrealized P&L across all positions."""
        return sum(position.unrealized_pnl for position in self.positions.values()) or Decimal("0")


@dataclass
class BrokerMetrics:
    """Performance metrics for broker operations."""

    orders_placed: int = 0
    orders_filled: int = 0
    orders_cancelled: int = 0
    orders_rejected: int = 0
    connection_errors: int = 0
    total_latency: float = 0.0
    last_order_time: datetime | None = None

    @property
    def average_latency_ms(self) -> float:
        """Calculate average order latency in milliseconds."""
        if self.orders_placed > 0:
            return (self.total_latency / self.orders_placed) * 1000
        return 0.0

    @property
    def fill_rate(self) -> float:
        """Calculate order fill rate as percentage."""
        if self.orders_placed > 0:
            return (self.orders_filled / self.orders_placed) * 100
        return 0.0

    @property
    def rejection_rate(self) -> float:
        """Calculate order rejection rate as percentage."""
        if self.orders_placed > 0:
            return (self.orders_rejected / self.orders_placed) * 100
        return 0.0


class AbstractBroker(ABC):
    """
    Abstract base class for all broker implementations.

    Provides common functionality for order management, position tracking,
    event integration, and performance monitoring.
    """

    def __init__(
        self,
        event_bus: EventBus,
        broker_id: str | None = None,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize the broker.

        Args:
            event_bus: Event bus for communication
            broker_id: Unique broker identifier
            config: Broker configuration dictionary
        """
        self.event_bus = event_bus
        self.broker_id = broker_id or str(uuid.uuid4())
        self.config = config or {}

        # Connection management
        self._connection_state = ConnectionState.DISCONNECTED
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = self.config.get("max_reconnect_attempts", 5)

        # Order tracking
        self._active_orders: dict[str, OrderEvent] = {}
        self._order_mapping: dict[str, str] = {}  # internal_id -> broker_id

        # Performance metrics
        self._metrics = BrokerMetrics()

        # Event handlers
        self._order_handler_registered = False

    @property
    def connection_state(self) -> ConnectionState:
        """Get current connection state."""
        return self._connection_state

    @property
    def is_connected(self) -> bool:
        """Check if broker is connected."""
        return self._connection_state == ConnectionState.CONNECTED

    @property
    def metrics(self) -> BrokerMetrics:
        """Get broker performance metrics."""
        return self._metrics

    async def initialize(self) -> None:
        """Initialize broker and subscribe to events."""
        if not self._order_handler_registered:
            # Subscribe to order events from strategies
            self.event_bus.subscribe(
                event_type=EventType.ORDER,
                handler=self._handle_order_event,
                priority=HandlerPriority.HIGH,
            )
            self._order_handler_registered = True

        # Connect to broker
        await self.connect()

    async def shutdown(self) -> None:
        """Graceful shutdown with order cleanup."""
        # Cancel all active orders
        for order_id in list(self._active_orders.keys()):
            try:
                await self.cancel_order(order_id)
            except Exception:
                # Log error but continue shutdown
                pass

        # Disconnect from broker
        await self.disconnect()

        # Unsubscribe from events
        if self._order_handler_registered:
            self.event_bus.unsubscribe(EventType.ORDER, self._handle_order_event)
            self._order_handler_registered = False

    # Abstract methods that must be implemented by concrete brokers

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to broker."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close broker connection."""
        pass

    @abstractmethod
    async def place_order(self, order: OrderEvent) -> str:
        """
        Place an order and return broker order ID.

        Args:
            order: Order event to execute

        Returns:
            Broker order ID

        Raises:
            Exception: If order placement fails
        """
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order by ID.

        Args:
            order_id: Internal order ID

        Returns:
            True if cancellation successful
        """
        pass

    @abstractmethod
    async def modify_order(
        self,
        order_id: str,
        quantity: Decimal | None = None,
        price: Decimal | None = None,
    ) -> bool:
        """
        Modify an existing order.

        Args:
            order_id: Internal order ID
            quantity: New quantity (optional)
            price: New price (optional)

        Returns:
            True if modification successful
        """
        pass

    @abstractmethod
    async def get_positions(self) -> dict[str, BrokerPosition]:
        """
        Get all current positions.

        Returns:
            Dictionary of positions by symbol
        """
        pass

    @abstractmethod
    async def get_position(self, symbol: str) -> BrokerPosition | None:
        """
        Get position for specific symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Position or None if not found
        """
        pass

    @abstractmethod
    async def get_account_info(self) -> BrokerAccountInfo:
        """
        Get complete account information.

        Returns:
            Account information
        """
        pass

    @abstractmethod
    async def get_balance(self, currency: str | None = None) -> dict[str, BrokerBalance]:
        """
        Get account balance(s).

        Args:
            currency: Specific currency (optional)

        Returns:
            Dictionary of balances by currency
        """
        pass

    # Event handling methods

    async def _handle_order_event(self, event: Event) -> None:
        """
        Handle incoming order events from strategies.

        Args:
            event: Order event to process
        """
        # Cast to OrderEvent - we know it's the right type from subscription
        if not isinstance(event, OrderEvent):
            return

        if event.status != OrderStatus.PENDING:
            return  # Only process new orders

        try:
            # Record order timing
            start_time = datetime.now(timezone.utc)

            # Store order
            self._active_orders[event.order_id] = event

            # Place order with broker
            broker_order_id = await self.place_order(event)

            # Calculate latency
            latency = (datetime.now(timezone.utc) - start_time).total_seconds()

            # Track mapping and update metrics
            self._order_mapping[event.order_id] = broker_order_id
            self._metrics.orders_placed += 1
            self._metrics.total_latency += latency
            self._metrics.last_order_time = start_time

            # Publish order update event
            await self._publish_order_update(
                order_id=event.order_id,
                broker_order_id=broker_order_id,
                status=OrderStatus.SUBMITTED,
                symbol=event.symbol,
            )

        except Exception as e:
            # Handle order rejection
            await self._handle_order_rejection(event, str(e))

    async def _handle_order_rejection(self, order: OrderEvent, reason: str) -> None:
        """
        Handle order rejection.

        Args:
            order: Rejected order
            reason: Rejection reason
        """
        # Update metrics
        self._metrics.orders_rejected += 1

        # Remove from active orders
        if order.order_id in self._active_orders:
            del self._active_orders[order.order_id]

        # Publish order update event
        await self._publish_order_update(
            order_id=order.order_id,
            broker_order_id="",
            status=OrderStatus.REJECTED,
            symbol=order.symbol,
            update_reason=reason,
        )

    async def _publish_order_update(
        self,
        order_id: str,
        broker_order_id: str,
        status: OrderStatus,
        symbol: str,
        filled_quantity: Decimal = Decimal("0"),
        remaining_quantity: Decimal = Decimal("0"),
        average_fill_price: Decimal = Decimal("0"),
        update_reason: str | None = None,
    ) -> None:
        """
        Publish order update event.

        Args:
            order_id: Internal order ID
            broker_order_id: Broker order ID
            status: Order status
            symbol: Trading symbol
            filled_quantity: Filled quantity
            remaining_quantity: Remaining quantity
            average_fill_price: Average fill price
            update_reason: Update reason
        """
        update_event = OrderUpdateEvent(
            order_id=order_id,
            broker_order_id=broker_order_id,
            symbol=symbol,
            status=status,
            filled_quantity=filled_quantity,
            remaining_quantity=remaining_quantity,
            average_fill_price=average_fill_price,
            broker_name=self.broker_id,
            update_reason=update_reason,
        )

        await self.event_bus.publish(update_event)

    async def _publish_fill_event(
        self,
        order_id: str,
        symbol: str,
        executed_quantity: Decimal,
        executed_price: Decimal,
        commission: Decimal = Decimal("0"),
    ) -> None:
        """
        Publish fill event.

        Args:
            order_id: Internal order ID
            symbol: Trading symbol
            executed_quantity: Executed quantity
            executed_price: Execution price
            commission: Commission paid
        """
        fill_event = FillEvent(
            order_id=order_id,
            symbol=symbol,
            executed_qty=executed_quantity,
            executed_price=executed_price,
            commission=commission,
        )

        await self.event_bus.publish(fill_event)

        # Update metrics
        self._metrics.orders_filled += 1

        # Remove from active orders if fully filled
        if order_id in self._active_orders:
            order = self._active_orders[order_id]
            if executed_quantity >= order.quantity:
                del self._active_orders[order_id]
                if order_id in self._order_mapping:
                    del self._order_mapping[order_id]

    async def _publish_position_update(self, position: BrokerPosition) -> None:
        """
        Publish position update event.

        Args:
            position: Updated position
        """
        position_event = PositionUpdateEvent(
            symbol=position.symbol,
            quantity=position.quantity,
            average_price=position.average_price,
            current_price=position.current_price,
            unrealized_pnl=position.unrealized_pnl,
            realized_pnl=position.realized_pnl,
            commission_paid=position.commission_paid,
            broker_name=self.broker_id,
        )

        await self.event_bus.publish(position_event)

    def get_metrics_dict(self) -> dict[str, Any]:
        """
        Get broker metrics as dictionary.

        Returns:
            Dictionary of broker metrics
        """
        return {
            "broker_id": self.broker_id,
            "connection_state": self._connection_state.value,
            "orders_placed": self._metrics.orders_placed,
            "orders_filled": self._metrics.orders_filled,
            "orders_cancelled": self._metrics.orders_cancelled,
            "orders_rejected": self._metrics.orders_rejected,
            "connection_errors": self._metrics.connection_errors,
            "average_latency_ms": self._metrics.average_latency_ms,
            "fill_rate": self._metrics.fill_rate,
            "rejection_rate": self._metrics.rejection_rate,
            "active_orders": len(self._active_orders),
            "last_order_time": self._metrics.last_order_time,
        }
