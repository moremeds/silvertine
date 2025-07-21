"""
Core event classes for the trading system.

This module defines the base Event class and specialized event types for:
- Market data updates
- Order operations
- Trade fills
- Trading signals

All events are immutable Pydantic models with automatic serialization/deserialization.
"""

import uuid
from datetime import datetime
from datetime import timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator


class EventType(str, Enum):
    """Event type enumeration."""

    MARKET_DATA = "MARKET_DATA"
    ORDER = "ORDER"
    FILL = "FILL"
    SIGNAL = "SIGNAL"
    ORDER_UPDATE = "ORDER_UPDATE"
    POSITION_UPDATE = "POSITION_UPDATE"


class OrderType(str, Enum):
    """Order type enumeration."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class SignalType(str, Enum):
    """Signal type enumeration."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class OrderStatus(str, Enum):
    """Order status enumeration."""

    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class OrderSide(str, Enum):
    """Order side enumeration."""

    BUY = "BUY"
    SELL = "SELL"


class Event(BaseModel):
    """
    Base event class for all trading system events.

    Provides common attributes and functionality for event identification,
    timestamping, and serialization.
    """

    event_type: EventType
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(
        frozen=True, use_enum_values=True  # Make events immutable
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return self.model_dump()

    def to_json(self) -> str:
        """Convert event to JSON string."""
        return self.model_dump_json()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        """Create event from dictionary."""
        # Handle timestamp string parsing
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


class MarketDataEvent(Event):
    """
    Market data event containing price and volume information.

    Represents real-time market data updates including price, volume,
    bid/ask spread, and derived metrics.
    """

    event_type: EventType = Field(default=EventType.MARKET_DATA)
    symbol: str = Field(..., min_length=1, description="Trading symbol")
    price: Decimal = Field(..., gt=0, description="Current market price")
    volume: Decimal = Field(..., ge=0, description="Volume traded")
    bid: Decimal | None = Field(None, gt=0, description="Bid price")
    ask: Decimal | None = Field(None, gt=0, description="Ask price")

    @field_validator("ask")
    @classmethod
    def ask_must_be_greater_than_bid(cls, v, info):
        """Validate that ask price is greater than bid price."""
        if (
            v is not None
            and hasattr(info, "data")
            and "bid" in info.data
            and info.data["bid"] is not None
        ):
            if v <= info.data["bid"]:
                raise ValueError("Ask price must be greater than bid price")
        return v

    @property
    def spread(self) -> Decimal | None:
        """Calculate bid-ask spread."""
        if self.bid is not None and self.ask is not None:
            return self.ask - self.bid
        return None

    @property
    def mid_price(self) -> Decimal | None:
        """Calculate mid price between bid and ask."""
        if self.bid is not None and self.ask is not None:
            return (self.bid + self.ask) / 2
        return None


class OrderEvent(Event):
    """
    Order event for trade execution requests.

    Represents order creation or modification requests with all
    necessary parameters for execution.
    """

    event_type: EventType = Field(default=EventType.ORDER)
    order_id: str = Field(..., min_length=1, description="Unique order identifier")
    symbol: str = Field(..., min_length=1, description="Trading symbol")
    side: OrderSide = Field(..., description="Order side")
    quantity: Decimal = Field(..., gt=0, description="Order quantity")
    order_type: OrderType = Field(..., description="Order type")
    price: Decimal | None = Field(
        None, gt=0, description="Order price for limit orders"
    )
    stop_price: Decimal | None = Field(
        None, gt=0, description="Stop price for stop orders"
    )
    status: OrderStatus = Field(default=OrderStatus.PENDING, description="Order status")
    strategy_id: str | None = Field(None, description="Strategy identifier")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @field_validator("price")
    @classmethod
    def price_required_for_limit_orders(cls, v, info):
        """Validate that price is provided for limit orders."""
        if (
            hasattr(info, "data")
            and info.data.get("order_type") in [OrderType.LIMIT, OrderType.STOP_LIMIT]
            and v is None
        ):
            raise ValueError("Price is required for limit orders")
        return v

    @field_validator("stop_price")
    @classmethod
    def stop_price_required_for_stop_orders(cls, v, info):
        """Validate that stop price is provided for stop orders."""
        if (
            hasattr(info, "data")
            and info.data.get("order_type") in [OrderType.STOP, OrderType.STOP_LIMIT]
            and v is None
        ):
            raise ValueError("Stop price is required for stop orders")
        return v


class FillEvent(Event):
    """
    Fill event for trade execution confirmations.

    Represents completed trade executions with execution details
    including quantity, price, and commission.
    """

    event_type: EventType = Field(default=EventType.FILL)
    order_id: str = Field(..., min_length=1, description="Order identifier")
    symbol: str = Field(..., min_length=1, description="Trading symbol")
    executed_qty: Decimal = Field(..., gt=0, description="Executed quantity")
    executed_price: Decimal = Field(..., gt=0, description="Execution price")
    commission: Decimal = Field(..., ge=0, description="Commission paid")

    @property
    def notional_value(self) -> Decimal:
        """Calculate the notional value of the fill."""
        return self.executed_qty * self.executed_price

    @property
    def net_proceeds(self) -> Decimal:
        """Calculate net proceeds after commission."""
        return self.notional_value - self.commission


class SignalEvent(Event):
    """
    Signal event for trading strategy signals.

    Represents trading signals generated by strategies with
    signal type, strength, and originating strategy.
    """

    event_type: EventType = Field(default=EventType.SIGNAL)
    symbol: str = Field(..., min_length=1, description="Trading symbol")
    signal_type: SignalType = Field(..., description="Signal type")
    strength: Decimal = Field(..., ge=0, le=1, description="Signal strength (0-1)")
    strategy_id: str = Field(..., min_length=1, description="Strategy identifier")

    @property
    def is_actionable(self) -> bool:
        """Check if signal is strong enough to be actionable."""
        return self.strength >= Decimal("0.5")


class OrderUpdateEvent(Event):
    """
    Order status update event from broker.

    Represents order status changes, fills, and cancellations
    from the broker execution system.
    """

    event_type: EventType = Field(default=EventType.ORDER_UPDATE)
    order_id: str = Field(..., min_length=1, description="Order identifier")
    broker_order_id: str = Field(..., description="Broker order identifier")
    symbol: str = Field(..., min_length=1, description="Trading symbol")
    status: OrderStatus = Field(..., description="Order status")
    filled_quantity: Decimal = Field(default=Decimal("0"), ge=0, description="Filled quantity")
    remaining_quantity: Decimal = Field(default=Decimal("0"), ge=0, description="Remaining quantity")
    average_fill_price: Decimal = Field(default=Decimal("0"), ge=0, description="Average fill price")
    broker_name: str = Field(..., min_length=1, description="Broker name")
    update_reason: str | None = Field(None, description="Update reason")


class PositionUpdateEvent(Event):
    """
    Position change event from broker.

    Represents position changes resulting from trade executions
    or manual position adjustments.
    """

    event_type: EventType = Field(default=EventType.POSITION_UPDATE)
    symbol: str = Field(..., min_length=1, description="Trading symbol")
    quantity: Decimal = Field(..., description="Current position quantity")
    average_price: Decimal = Field(..., gt=0, description="Average position price")
    current_price: Decimal = Field(default=Decimal("0"), ge=0, description="Current market price")
    unrealized_pnl: Decimal = Field(default=Decimal("0"), description="Unrealized P&L")
    realized_pnl: Decimal = Field(default=Decimal("0"), description="Realized P&L")
    commission_paid: Decimal = Field(default=Decimal("0"), ge=0, description="Commission paid")
    broker_name: str = Field(..., min_length=1, description="Broker name")
