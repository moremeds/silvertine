# Modular Broker Interface Design

## Executive Summary

This document presents a comprehensive design for the Silvertine modular broker interface (Task 3), architected to seamlessly integrate with the existing event-driven core engine. The design emphasizes reliability, performance, and extensibility while maintaining clean separation of concerns.

## Architecture Overview

### High-Level Integration

```
┌─────────────────────────────────────────────────────────────────┐
│                      Event Bus Core Engine                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   Order     │  │   Fill      │  │    Market Data          │ │
│  │  Events     │  │  Events     │  │     Events              │ │
│  └──────▲──────┘  └──────▲──────┘  └───────────┬─────────────┘ │
└─────────┼─────────────────┼────────────────────┼───────────────┘
          │                 │                    │
          │                 │                    ▼
┌─────────┴─────────────────┴────────────────────────────────────┐
│                      Broker Layer                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                   AbstractBroker                         │  │
│  │  - Order Management    - Position Tracking              │  │
│  │  - Event Integration   - Connection Management          │  │
│  └─────────────────────────────────────────────────────────┘  │
│         ▲                    ▲                    ▲            │
│         │                    │                    │            │
│  ┌──────┴──────┐     ┌──────┴──────┐     ┌──────┴──────┐    │
│  │   Paper     │     │   Binance   │     │     IB      │    │
│  │  Trading    │     │   Adapter   │     │   Adapter   │    │
│  └─────────────┘     └─────────────┘     └─────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

### Core Design Principles

1. **Event-Driven Integration**: Brokers subscribe to OrderEvents and publish FillEvents
2. **Asynchronous Operations**: All broker methods are async for non-blocking execution
3. **Standardized Interfaces**: Common data structures across all broker implementations
4. **Graceful Degradation**: Robust error handling with automatic recovery
5. **Performance First**: Sub-500ms order execution latency target

## Detailed Component Design

### 1. AbstractBroker Base Class

```python
# src/exchanges/ibroker.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
import asyncio
import uuid

from ..core.events import OrderEvent, FillEvent, EventType
from ..core.eventbus import EventBus, HandlerPriority

@dataclass
class BrokerPosition:
    """Represents a position held at a broker"""
    symbol: str
    quantity: float
    average_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    commission_paid: float = 0.0
    
    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price
    
    @property
    def cost_basis(self) -> float:
        return self.quantity * self.average_price

@dataclass
class BrokerBalance:
    """Account balance information"""
    currency: str
    available: float
    total: float
    margin_used: float = 0.0
    unrealized_pnl: float = 0.0
    
    @property
    def margin_available(self) -> float:
        return self.available - self.margin_used

@dataclass
class BrokerAccountInfo:
    """Complete account information"""
    account_id: str
    broker_name: str
    account_type: str  # cash, margin, futures
    base_currency: str
    leverage: float = 1.0
    balances: Dict[str, BrokerBalance] = field(default_factory=dict)
    positions: Dict[str, BrokerPosition] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.utcnow)

class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"

class AbstractBroker(ABC):
    """Abstract base class for all broker implementations"""
    
    def __init__(self, 
                 event_bus: EventBus,
                 broker_id: str = None,
                 config: Dict[str, Any] = None):
        self.event_bus = event_bus
        self.broker_id = broker_id or str(uuid.uuid4())
        self.config = config or {}
        
        # Connection management
        self._connection_state = ConnectionState.DISCONNECTED
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = self.config.get('max_reconnect_attempts', 5)
        
        # Order tracking
        self._active_orders: Dict[str, OrderEvent] = {}
        self._order_mapping: Dict[str, str] = {}  # internal_id -> broker_id
        
        # Performance metrics
        self._metrics = {
            'orders_placed': 0,
            'orders_filled': 0,
            'orders_cancelled': 0,
            'orders_rejected': 0,
            'total_latency': 0.0,
            'connection_errors': 0
        }
    
    async def initialize(self) -> None:
        """Initialize broker and subscribe to events"""
        # Subscribe to order events from strategies
        self.event_bus.subscribe(
            handler=self._handle_order_event,
            event_types=[EventType.ORDER],
            priority=HandlerPriority.HIGH
        )
        
        # Connect to broker
        await self.connect()
    
    async def shutdown(self) -> None:
        """Graceful shutdown"""
        # Cancel all active orders
        for order_id in list(self._active_orders.keys()):
            await self.cancel_order(order_id)
        
        # Disconnect
        await self.disconnect()
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to broker"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close broker connection"""
        pass
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """Check connection status"""
        pass
    
    @abstractmethod
    async def place_order(self, order: OrderEvent) -> str:
        """Place an order and return broker order ID"""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order by ID"""
        pass
    
    @abstractmethod
    async def modify_order(self, order_id: str, 
                          quantity: Optional[float] = None,
                          price: Optional[float] = None) -> bool:
        """Modify an existing order"""
        pass
    
    @abstractmethod
    async def get_positions(self) -> Dict[str, BrokerPosition]:
        """Get all current positions"""
        pass
    
    @abstractmethod
    async def get_position(self, symbol: str) -> Optional[BrokerPosition]:
        """Get position for specific symbol"""
        pass
    
    @abstractmethod
    async def get_account_info(self) -> BrokerAccountInfo:
        """Get complete account information"""
        pass
    
    @abstractmethod
    async def get_balance(self, currency: str = None) -> Dict[str, BrokerBalance]:
        """Get account balance(s)"""
        pass
    
    async def _handle_order_event(self, event: OrderEvent) -> None:
        """Handle incoming order events from strategies"""
        if event.status != OrderStatus.PENDING:
            return  # Only process new orders
        
        try:
            # Record order
            self._active_orders[event.order_id] = event
            
            # Place order with broker
            start_time = datetime.utcnow()
            broker_order_id = await self.place_order(event)
            latency = (datetime.utcnow() - start_time).total_seconds()
            
            # Track mapping
            self._order_mapping[event.order_id] = broker_order_id
            
            # Update metrics
            self._metrics['orders_placed'] += 1
            self._metrics['total_latency'] += latency
            
        except Exception as e:
            # Publish rejection event
            await self._publish_order_rejection(event, str(e))
            self._metrics['orders_rejected'] += 1
    
    async def _publish_fill_event(self, 
                                 order_id: str,
                                 symbol: str,
                                 executed_quantity: float,
                                 executed_price: float,
                                 commission: float = 0.0,
                                 trade_id: str = None) -> None:
        """Publish fill event to event bus"""
        fill_event = FillEvent(
            order_id=order_id,
            symbol=symbol,
            executed_quantity=executed_quantity,
            executed_price=executed_price,
            commission=commission,
            commission_asset=self.config.get('commission_asset', 'USD'),
            exchange=self.broker_id,
            trade_id=trade_id or str(uuid.uuid4()),
            source=f"broker:{self.broker_id}"
        )
        
        await self.event_bus.publish(fill_event)
        
        # Update metrics
        self._metrics['orders_filled'] += 1
        
        # Remove from active orders if fully filled
        if order_id in self._active_orders:
            order = self._active_orders[order_id]
            if executed_quantity >= order.quantity:
                del self._active_orders[order_id]
    
    async def _publish_order_rejection(self, order: OrderEvent, reason: str) -> None:
        """Publish order rejection event"""
        # Create rejection event (extends OrderEvent)
        rejection_event = OrderEvent(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            price=order.price,
            stop_price=order.stop_price,
            status=OrderStatus.REJECTED,
            strategy_id=order.strategy_id,
            source=f"broker:{self.broker_id}",
            metadata={'rejection_reason': reason}
        )
        
        await self.event_bus.publish(rejection_event)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get broker performance metrics"""
        avg_latency = (
            self._metrics['total_latency'] / self._metrics['orders_placed']
            if self._metrics['orders_placed'] > 0 else 0.0
        )
        
        return {
            'broker_id': self.broker_id,
            'connection_state': self._connection_state.value,
            'orders_placed': self._metrics['orders_placed'],
            'orders_filled': self._metrics['orders_filled'],
            'orders_cancelled': self._metrics['orders_cancelled'],
            'orders_rejected': self._metrics['orders_rejected'],
            'average_latency_ms': avg_latency * 1000,
            'connection_errors': self._metrics['connection_errors'],
            'active_orders': len(self._active_orders)
        }
```

### 2. Paper Trading Simulator

```python
# src/exchanges/paper/paper_broker.py
import asyncio
import random
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from collections import defaultdict

from ..ibroker import (
    AbstractBroker, BrokerPosition, BrokerBalance, 
    BrokerAccountInfo, ConnectionState
)
from ...core.events import OrderEvent, OrderStatus, OrderType, OrderSide

class SlippageModel(Enum):
    FIXED = "fixed"
    PERCENTAGE = "percentage"
    MARKET_IMPACT = "market_impact"

@dataclass
class PaperTradingConfig:
    """Configuration for paper trading simulator"""
    initial_balance: float = 100000.0
    base_currency: str = "USD"
    latency_ms: int = 50  # Simulated latency
    slippage_model: SlippageModel = SlippageModel.PERCENTAGE
    slippage_value: float = 0.0005  # 0.05% default
    commission_rate: float = 0.001  # 0.1% default
    partial_fill_probability: float = 0.1
    rejection_probability: float = 0.02
    margin_enabled: bool = True
    leverage: float = 3.0

class PaperTradingBroker(AbstractBroker):
    """Realistic paper trading simulator"""
    
    def __init__(self, event_bus: EventBus, config: PaperTradingConfig = None):
        self.sim_config = config or PaperTradingConfig()
        
        super().__init__(
            event_bus=event_bus,
            broker_id="paper_trading",
            config={'broker_type': 'paper'}
        )
        
        # Account state
        self._balances = {
            self.sim_config.base_currency: BrokerBalance(
                currency=self.sim_config.base_currency,
                available=self.sim_config.initial_balance,
                total=self.sim_config.initial_balance
            )
        }
        
        self._positions: Dict[str, BrokerPosition] = {}
        self._execution_history: List[Dict] = []
        
        # Market data cache
        self._last_prices: Dict[str, float] = {}
        self._order_books: Dict[str, Dict] = {}
        
        # Order execution tasks
        self._execution_tasks: Dict[str, asyncio.Task] = {}
    
    async def connect(self) -> None:
        """Simulate connection"""
        self._connection_state = ConnectionState.CONNECTING
        
        # Simulate connection delay
        await asyncio.sleep(0.5)
        
        # Subscribe to market data for price updates
        self.event_bus.subscribe(
            handler=self._handle_market_data,
            event_types=[EventType.MARKET_DATA],
            priority=HandlerPriority.NORMAL
        )
        
        self._connection_state = ConnectionState.CONNECTED
    
    async def disconnect(self) -> None:
        """Disconnect simulator"""
        # Cancel all execution tasks
        for task in self._execution_tasks.values():
            task.cancel()
        
        self._connection_state = ConnectionState.DISCONNECTED
    
    async def is_connected(self) -> bool:
        return self._connection_state == ConnectionState.CONNECTED
    
    async def place_order(self, order: OrderEvent) -> str:
        """Simulate order placement"""
        # Simulate latency
        await asyncio.sleep(self.sim_config.latency_ms / 1000.0)
        
        # Random rejection
        if random.random() < self.sim_config.rejection_probability:
            raise Exception("Order rejected by exchange")
        
        # Validate order
        if not await self._validate_order(order):
            raise Exception("Insufficient funds or invalid order")
        
        # Generate broker order ID
        broker_order_id = f"PAPER_{order.order_id}"
        
        # Schedule execution
        execution_task = asyncio.create_task(
            self._execute_order(order, broker_order_id)
        )
        self._execution_tasks[order.order_id] = execution_task
        
        return broker_order_id
    
    async def _validate_order(self, order: OrderEvent) -> bool:
        """Validate order against account state"""
        symbol_price = self._last_prices.get(order.symbol, order.price or 100.0)
        required_balance = order.quantity * symbol_price
        
        # Add margin for commission
        required_balance *= (1 + self.sim_config.commission_rate)
        
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
        """Simulate order execution with realistic behavior"""
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
            self._metrics['orders_cancelled'] += 1
        except Exception as e:
            # Execution failed
            await self._publish_order_rejection(order, str(e))
    
    async def _execute_market_order(self, order: OrderEvent, broker_order_id: str) -> None:
        """Execute market order immediately"""
        # Get current price
        symbol_price = self._last_prices.get(order.symbol)
        if not symbol_price:
            raise Exception("No market data available")
        
        # Apply slippage
        execution_price = self._apply_slippage(symbol_price, order.side, order.quantity)
        
        # Simulate partial fills
        if random.random() < self.sim_config.partial_fill_probability:
            # Execute in multiple fills
            remaining = order.quantity
            while remaining > 0:
                fill_quantity = min(remaining, order.quantity * random.uniform(0.1, 0.5))
                
                await self._process_fill(
                    order=order,
                    broker_order_id=broker_order_id,
                    executed_quantity=fill_quantity,
                    executed_price=execution_price
                )
                
                remaining -= fill_quantity
                
                # Small delay between fills
                await asyncio.sleep(0.1)
        else:
            # Single fill
            await self._process_fill(
                order=order,
                broker_order_id=broker_order_id,
                executed_quantity=order.quantity,
                executed_price=execution_price
            )
    
    async def _execute_limit_order(self, order: OrderEvent, broker_order_id: str) -> None:
        """Execute limit order when price conditions are met"""
        while order.order_id in self._active_orders:
            current_price = self._last_prices.get(order.symbol)
            if not current_price:
                await asyncio.sleep(0.1)
                continue
            
            # Check if limit price is met
            price_met = False
            if order.side == OrderSide.BUY and current_price <= order.price:
                price_met = True
            elif order.side == OrderSide.SELL and current_price >= order.price:
                price_met = True
            
            if price_met:
                # Execute at limit price (or better)
                execution_price = order.price
                
                await self._process_fill(
                    order=order,
                    broker_order_id=broker_order_id,
                    executed_quantity=order.quantity,
                    executed_price=execution_price
                )
                break
            
            await asyncio.sleep(0.1)
    
    def _apply_slippage(self, price: float, side: OrderSide, quantity: float) -> float:
        """Apply slippage model to execution price"""
        if self.sim_config.slippage_model == SlippageModel.FIXED:
            slippage = self.sim_config.slippage_value
        elif self.sim_config.slippage_model == SlippageModel.PERCENTAGE:
            slippage = price * self.sim_config.slippage_value
        else:  # MARKET_IMPACT
            # Larger orders have more impact
            impact_factor = min(quantity / 10000.0, 0.01)  # Max 1% impact
            slippage = price * impact_factor
        
        # Apply slippage in unfavorable direction
        if side == OrderSide.BUY:
            return price + slippage
        else:
            return price - slippage
    
    async def _process_fill(self, order: OrderEvent, broker_order_id: str,
                           executed_quantity: float, executed_price: float) -> None:
        """Process order fill and update positions"""
        # Calculate commission
        commission = executed_quantity * executed_price * self.sim_config.commission_rate
        
        # Update position
        await self._update_position(
            symbol=order.symbol,
            side=order.side,
            quantity=executed_quantity,
            price=executed_price,
            commission=commission
        )
        
        # Update balance
        total_cost = (executed_quantity * executed_price) + commission
        if order.side == OrderSide.BUY:
            self._balances[self.sim_config.base_currency].available -= total_cost
        else:
            self._balances[self.sim_config.base_currency].available += (total_cost - 2 * commission)
        
        # Record execution
        self._execution_history.append({
            'timestamp': datetime.utcnow(),
            'order_id': order.order_id,
            'broker_order_id': broker_order_id,
            'symbol': order.symbol,
            'side': order.side,
            'quantity': executed_quantity,
            'price': executed_price,
            'commission': commission,
            'slippage': executed_price - self._last_prices.get(order.symbol, executed_price)
        })
        
        # Publish fill event
        await self._publish_fill_event(
            order_id=order.order_id,
            symbol=order.symbol,
            executed_quantity=executed_quantity,
            executed_price=executed_price,
            commission=commission,
            trade_id=broker_order_id
        )
    
    async def _update_position(self, symbol: str, side: OrderSide,
                              quantity: float, price: float, commission: float) -> None:
        """Update or create position"""
        if symbol not in self._positions:
            # New position
            self._positions[symbol] = BrokerPosition(
                symbol=symbol,
                quantity=quantity if side == OrderSide.BUY else -quantity,
                average_price=price,
                current_price=price,
                commission_paid=commission
            )
        else:
            # Update existing position
            position = self._positions[symbol]
            
            if side == OrderSide.BUY:
                # Adding to position
                new_quantity = position.quantity + quantity
                if new_quantity != 0:
                    position.average_price = (
                        (position.quantity * position.average_price + quantity * price) /
                        new_quantity
                    )
                position.quantity = new_quantity
            else:
                # Reducing position
                position.quantity -= quantity
                
                # Calculate realized P&L
                if position.quantity < 0:
                    # Position flipped
                    position.average_price = price
                elif position.quantity == 0:
                    # Position closed
                    del self._positions[symbol]
                    return
            
            position.commission_paid += commission
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an active order"""
        if order_id in self._execution_tasks:
            self._execution_tasks[order_id].cancel()
            del self._execution_tasks[order_id]
            
            if order_id in self._active_orders:
                del self._active_orders[order_id]
            
            return True
        return False
    
    async def get_positions(self) -> Dict[str, BrokerPosition]:
        """Get all positions with updated P&L"""
        # Update current prices and P&L
        for symbol, position in self._positions.items():
            if symbol in self._last_prices:
                position.current_price = self._last_prices[symbol]
                position.unrealized_pnl = (
                    position.quantity * (position.current_price - position.average_price)
                )
        
        return self._positions.copy()
    
    async def get_account_info(self) -> BrokerAccountInfo:
        """Get complete account information"""
        return BrokerAccountInfo(
            account_id="PAPER_TRADING",
            broker_name="Paper Trading Simulator",
            account_type="margin" if self.sim_config.margin_enabled else "cash",
            base_currency=self.sim_config.base_currency,
            leverage=self.sim_config.leverage,
            balances=self._balances.copy(),
            positions=await self.get_positions()
        )
    
    async def _handle_market_data(self, event) -> None:
        """Update market prices from events"""
        if hasattr(event, 'symbol') and hasattr(event, 'price'):
            self._last_prices[event.symbol] = event.price
            
            # Update order book if available
            if hasattr(event, 'bid') and hasattr(event, 'ask'):
                self._order_books[event.symbol] = {
                    'bid': event.bid,
                    'ask': event.ask,
                    'bid_size': getattr(event, 'bid_size', 0),
                    'ask_size': getattr(event, 'ask_size', 0)
                }
```

### 3. Binance Exchange Adapter

```python
# src/exchanges/binance/binance_broker.py
import asyncio
import aiohttp
from typing import Dict, Optional, List
from datetime import datetime
import hmac
import hashlib
from urllib.parse import urlencode

from ..ibroker import (
    AbstractBroker, BrokerPosition, BrokerBalance,
    BrokerAccountInfo, ConnectionState
)
from ...core.events import OrderEvent, OrderStatus, OrderType, OrderSide

class BinanceBroker(AbstractBroker):
    """Binance exchange adapter supporting spot and futures"""
    
    def __init__(self, event_bus: EventBus, config: Dict[str, Any]):
        super().__init__(
            event_bus=event_bus,
            broker_id="binance",
            config=config
        )
        
        # API configuration
        self.api_key = config.get('api_key', '')
        self.api_secret = config.get('api_secret', '')
        self.testnet = config.get('testnet', True)
        
        # URLs
        if self.testnet:
            self.rest_url = "https://testnet.binance.vision/api/v3"
            self.ws_url = "wss://testnet.binance.vision/ws"
        else:
            self.rest_url = "https://api.binance.com/api/v3"
            self.ws_url = "wss://stream.binance.com:9443/ws"
        
        # Rate limiting
        self.rate_limiter = RateLimiter(
            requests_per_minute=1200,  # Binance limit
            orders_per_second=10
        )
        
        # WebSocket connections
        self.market_ws = None
        self.user_ws = None
        self.listen_key = None
        
        # Session for HTTP requests
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def connect(self) -> None:
        """Connect to Binance"""
        self._connection_state = ConnectionState.CONNECTING
        
        try:
            # Create HTTP session
            self.session = aiohttp.ClientSession()
            
            # Test connectivity
            await self._test_connectivity()
            
            # Get listen key for user data stream
            self.listen_key = await self._get_listen_key()
            
            # Connect WebSockets
            await self._connect_websockets()
            
            # Start listen key keepalive
            asyncio.create_task(self._keepalive_listen_key())
            
            self._connection_state = ConnectionState.CONNECTED
            
        except Exception as e:
            self._connection_state = ConnectionState.ERROR
            raise Exception(f"Failed to connect to Binance: {e}")
    
    async def _connect_websockets(self) -> None:
        """Establish WebSocket connections"""
        # User data stream
        user_stream_url = f"{self.ws_url}/{self.listen_key}"
        self.user_ws = await self._create_websocket(
            user_stream_url,
            self._handle_user_message
        )
        
        # Market data streams (subscribe as needed)
        self.market_ws = await self._create_websocket(
            self.ws_url,
            self._handle_market_message
        )
    
    async def _handle_user_message(self, message: Dict) -> None:
        """Process user data stream messages"""
        event_type = message.get('e')
        
        if event_type == 'executionReport':
            # Order update
            await self._process_order_update(message)
        elif event_type == 'outboundAccountPosition':
            # Balance update
            await self._process_balance_update(message)
    
    async def _process_order_update(self, message: Dict) -> None:
        """Process order execution report"""
        order_id = message['c']  # Client order ID
        status = message['X']  # Order status
        
        if status == 'FILLED' or status == 'PARTIALLY_FILLED':
            # Generate fill event
            executed_qty = float(message['z'])  # Cumulative filled quantity
            executed_price = float(message['Z']) / executed_qty  # Avg price
            commission = float(message['n'])  # Commission
            
            if order_id in self._active_orders:
                await self._publish_fill_event(
                    order_id=order_id,
                    symbol=message['s'],
                    executed_quantity=executed_qty,
                    executed_price=executed_price,
                    commission=commission,
                    trade_id=str(message['t'])  # Trade ID
                )
        
        elif status == 'CANCELED':
            if order_id in self._active_orders:
                del self._active_orders[order_id]
                self._metrics['orders_cancelled'] += 1
        
        elif status == 'REJECTED':
            if order_id in self._active_orders:
                await self._publish_order_rejection(
                    self._active_orders[order_id],
                    message.get('r', 'Unknown reason')
                )
    
    async def place_order(self, order: OrderEvent) -> str:
        """Place order on Binance"""
        # Rate limiting
        await self.rate_limiter.acquire_order()
        
        # Map order type
        binance_order = {
            'symbol': order.symbol.replace('/', ''),  # BTC/USDT -> BTCUSDT
            'side': order.side.value.upper(),
            'type': self._map_order_type(order.order_type),
            'quantity': order.quantity,
            'newClientOrderId': order.order_id
        }
        
        # Add price for limit orders
        if order.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
            binance_order['price'] = str(order.price)
            binance_order['timeInForce'] = 'GTC'  # Good till cancelled
        
        # Add stop price for stop orders
        if order.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
            binance_order['stopPrice'] = str(order.stop_price)
        
        # Send order
        response = await self._request(
            'POST',
            '/order',
            signed=True,
            data=binance_order
        )
        
        return response['orderId']
    
    def _map_order_type(self, order_type: OrderType) -> str:
        """Map internal order type to Binance"""
        mapping = {
            OrderType.MARKET: 'MARKET',
            OrderType.LIMIT: 'LIMIT',
            OrderType.STOP: 'STOP_LOSS',
            OrderType.STOP_LIMIT: 'STOP_LOSS_LIMIT'
        }
        return mapping.get(order_type, 'MARKET')
    
    async def get_positions(self) -> Dict[str, BrokerPosition]:
        """Get current positions from account balances"""
        account_info = await self._request('GET', '/account', signed=True)
        
        positions = {}
        for balance in account_info['balances']:
            asset = balance['asset']
            free = float(balance['free'])
            locked = float(balance['locked'])
            total = free + locked
            
            if total > 0:
                # Get current price
                symbol = f"{asset}USDT"
                ticker = await self._request('GET', '/ticker/price', {'symbol': symbol})
                current_price = float(ticker['price']) if ticker else 0.0
                
                positions[asset] = BrokerPosition(
                    symbol=asset,
                    quantity=total,
                    average_price=0.0,  # Binance doesn't track this
                    current_price=current_price
                )
        
        return positions
    
    async def _request(self, method: str, endpoint: str, 
                      data: Dict = None, signed: bool = False) -> Dict:
        """Make HTTP request to Binance API"""
        await self.rate_limiter.acquire_request()
        
        url = self.rest_url + endpoint
        headers = {'X-MBX-APIKEY': self.api_key}
        
        if signed:
            # Add timestamp
            if data is None:
                data = {}
            data['timestamp'] = int(datetime.utcnow().timestamp() * 1000)
            
            # Create signature
            query_string = urlencode(data)
            signature = hmac.new(
                self.api_secret.encode(),
                query_string.encode(),
                hashlib.sha256
            ).hexdigest()
            data['signature'] = signature
        
        async with self.session.request(
            method, url, headers=headers, params=data
        ) as response:
            if response.status != 200:
                error = await response.json()
                raise Exception(f"Binance API error: {error}")
            
            return await response.json()

class RateLimiter:
    """Rate limiter for Binance API"""
    
    def __init__(self, requests_per_minute: int, orders_per_second: int):
        self.requests_per_minute = requests_per_minute
        self.orders_per_second = orders_per_second
        
        # Token buckets
        self.request_bucket = TokenBucket(
            capacity=requests_per_minute,
            refill_rate=requests_per_minute / 60.0
        )
        self.order_bucket = TokenBucket(
            capacity=orders_per_second * 10,
            refill_rate=orders_per_second
        )
    
    async def acquire_request(self) -> None:
        """Acquire token for general request"""
        await self.request_bucket.acquire()
    
    async def acquire_order(self) -> None:
        """Acquire token for order placement"""
        await self.order_bucket.acquire()
        await self.request_bucket.acquire()
```

### 4. Interactive Brokers Adapter

```python
# src/exchanges/ib/ib_broker.py
import asyncio
from typing import Dict, Optional, List, Set
from datetime import datetime
from decimal import Decimal

from ib_insync import IB, Contract, Order as IBOrder, Trade, Position
from ib_insync.util import startLoop

from ..ibroker import (
    AbstractBroker, BrokerPosition, BrokerBalance,
    BrokerAccountInfo, ConnectionState
)
from ...core.events import OrderEvent, OrderStatus, OrderType, OrderSide

class InteractiveBrokersBroker(AbstractBroker):
    """Interactive Brokers adapter using ib_insync"""
    
    def __init__(self, event_bus: EventBus, config: Dict[str, Any]):
        super().__init__(
            event_bus=event_bus,
            broker_id="interactive_brokers",
            config=config
        )
        
        # IB connection settings
        self.host = config.get('host', '127.0.0.1')
        self.port = config.get('port', 7497)  # TWS paper trading
        self.client_id = config.get('client_id', 1)
        self.account = config.get('account', '')  # Empty for primary
        
        # IB client
        self.ib = IB()
        
        # Contract cache
        self._contract_cache: Dict[str, Contract] = {}
        
        # Order tracking
        self._ib_orders: Dict[str, Trade] = {}  # order_id -> Trade
        
        # Market data subscriptions
        self._market_data_handles: Dict[str, Any] = {}
        self._subscription_limit = config.get('md_subscription_limit', 100)
    
    async def connect(self) -> None:
        """Connect to IB Gateway or TWS"""
        self._connection_state = ConnectionState.CONNECTING
        
        try:
            # Connect with retry logic
            for attempt in range(self._max_reconnect_attempts):
                try:
                    await self.ib.connectAsync(
                        host=self.host,
                        port=self.port,
                        clientId=self.client_id
                    )
                    break
                except Exception as e:
                    if attempt == self._max_reconnect_attempts - 1:
                        raise
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
            
            # Set up event handlers
            self._setup_event_handlers()
            
            # Request positions and account updates
            self.ib.reqPositions()
            self.ib.reqAccountUpdates(subscribe=True, account=self.account)
            
            # Start order monitoring
            await self._start_order_monitoring()
            
            self._connection_state = ConnectionState.CONNECTED
            
        except Exception as e:
            self._connection_state = ConnectionState.ERROR
            raise Exception(f"Failed to connect to IB: {e}")
    
    def _setup_event_handlers(self) -> None:
        """Configure IB event handlers"""
        # Order events
        self.ib.orderStatusEvent += self._on_order_status
        self.ib.execDetailsEvent += self._on_execution
        self.ib.commissionReportEvent += self._on_commission
        
        # Connection events
        self.ib.connectedEvent += self._on_connected
        self.ib.disconnectedEvent += self._on_disconnected
        self.ib.errorEvent += self._on_error
        
        # Position events
        self.ib.positionEvent += self._on_position_update
        self.ib.accountValueEvent += self._on_account_update
    
    async def _on_order_status(self, trade: Trade) -> None:
        """Handle order status updates"""
        # Find our order ID
        order_id = None
        for oid, ib_trade in self._ib_orders.items():
            if ib_trade.order.orderId == trade.order.orderId:
                order_id = oid
                break
        
        if not order_id:
            return
        
        status = trade.orderStatus.status
        
        if status == 'Filled':
            # Will handle in execution details
            pass
        elif status == 'Cancelled':
            if order_id in self._active_orders:
                del self._active_orders[order_id]
                self._metrics['orders_cancelled'] += 1
        elif status == 'Inactive':
            # Order rejected
            if order_id in self._active_orders:
                await self._publish_order_rejection(
                    self._active_orders[order_id],
                    trade.orderStatus.warningText or 'Order rejected'
                )
    
    async def _on_execution(self, trade: Trade, fill) -> None:
        """Handle order execution"""
        # Find our order ID
        order_id = None
        for oid, ib_trade in self._ib_orders.items():
            if ib_trade.order.orderId == trade.order.orderId:
                order_id = oid
                break
        
        if not order_id or order_id not in self._active_orders:
            return
        
        # Convert IB fill to our fill event
        order = self._active_orders[order_id]
        
        await self._publish_fill_event(
            order_id=order_id,
            symbol=order.symbol,
            executed_quantity=abs(fill.execution.shares),
            executed_price=fill.execution.price,
            commission=0.0,  # Will be updated in commission event
            trade_id=str(fill.execution.execId)
        )
    
    async def place_order(self, order: OrderEvent) -> str:
        """Place order with Interactive Brokers"""
        # Get or create contract
        contract = await self._get_contract(order.symbol)
        
        # Create IB order
        ib_order = IBOrder()
        ib_order.action = 'BUY' if order.side == OrderSide.BUY else 'SELL'
        ib_order.totalQuantity = order.quantity
        ib_order.orderType = self._map_order_type(order.order_type)
        
        # Set prices
        if order.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
            ib_order.lmtPrice = float(order.price)
        if order.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
            ib_order.auxPrice = float(order.stop_price)  # Stop price in IB
        
        # Additional order attributes
        ib_order.tif = 'GTC'  # Good till cancelled
        ib_order.transmit = True
        
        # Place order
        trade = self.ib.placeOrder(contract, ib_order)
        
        # Track order
        self._ib_orders[order.order_id] = trade
        
        return str(trade.order.orderId)
    
    async def _get_contract(self, symbol: str) -> Contract:
        """Get or create IB contract"""
        if symbol in self._contract_cache:
            return self._contract_cache[symbol]
        
        # Parse symbol (simple implementation)
        if '/' in symbol:
            # Forex pair
            base, quote = symbol.split('/')
            contract = Contract(
                symbol=base,
                secType='CASH',
                currency=quote,
                exchange='IDEALPRO'
            )
        elif symbol.endswith('USD'):
            # Crypto
            contract = Contract(
                symbol=symbol[:-3],
                secType='CRYPTO',
                currency='USD',
                exchange='PAXOS'
            )
        else:
            # Stock
            contract = Contract(
                symbol=symbol,
                secType='STK',
                currency='USD',
                exchange='SMART'
            )
        
        # Validate contract
        details = await self.ib.reqContractDetailsAsync(contract)
        if details:
            contract = details[0].contract
            self._contract_cache[symbol] = contract
            return contract
        else:
            raise Exception(f"Contract not found: {symbol}")
    
    def _map_order_type(self, order_type: OrderType) -> str:
        """Map internal order type to IB"""
        mapping = {
            OrderType.MARKET: 'MKT',
            OrderType.LIMIT: 'LMT',
            OrderType.STOP: 'STP',
            OrderType.STOP_LIMIT: 'STP LMT'
        }
        return mapping.get(order_type, 'MKT')
    
    async def get_positions(self) -> Dict[str, BrokerPosition]:
        """Get current positions"""
        positions = {}
        
        for ib_position in self.ib.positions(account=self.account):
            symbol = self._contract_to_symbol(ib_position.contract)
            
            # Get current price
            ticker = self.ib.ticker(ib_position.contract)
            current_price = ticker.marketPrice() if ticker else 0.0
            
            position = BrokerPosition(
                symbol=symbol,
                quantity=ib_position.position,
                average_price=ib_position.avgCost / ib_position.contract.multiplier,
                current_price=current_price
            )
            
            # Calculate P&L
            if current_price > 0:
                position.unrealized_pnl = (
                    position.quantity * (current_price - position.average_price)
                )
            
            positions[symbol] = position
        
        return positions
    
    def _contract_to_symbol(self, contract: Contract) -> str:
        """Convert IB contract to our symbol format"""
        if contract.secType == 'CASH':
            return f"{contract.symbol}/{contract.currency}"
        elif contract.secType == 'CRYPTO':
            return f"{contract.symbol}{contract.currency}"
        else:
            return contract.symbol
    
    async def get_account_info(self) -> BrokerAccountInfo:
        """Get account information"""
        account_values = self.ib.accountValues(account=self.account)
        
        # Parse account values
        balances = {}
        base_currency = 'USD'
        leverage = 1.0
        
        for av in account_values:
            if av.tag == 'CashBalance':
                currency = av.currency
                if currency not in balances:
                    balances[currency] = BrokerBalance(
                        currency=currency,
                        available=0.0,
                        total=0.0
                    )
                balances[currency].total = float(av.value)
            
            elif av.tag == 'AvailableFunds':
                currency = av.currency
                if currency in balances:
                    balances[currency].available = float(av.value)
            
            elif av.tag == 'Leverage-S':
                leverage = float(av.value)
        
        return BrokerAccountInfo(
            account_id=self.account or 'PRIMARY',
            broker_name="Interactive Brokers",
            account_type="margin",
            base_currency=base_currency,
            leverage=leverage,
            balances=balances,
            positions=await self.get_positions()
        )
```

### 5. Broker Factory and Configuration System

```python
# src/exchanges/factory.py
import asyncio
import importlib
from typing import Dict, Optional, Type, List, Any
from dataclasses import dataclass
import yaml
import os
from string import Template

from .ibroker import AbstractBroker
from ..core.eventbus import EventBus

@dataclass
class BrokerConfig:
    """Broker configuration with validation"""
    broker_type: str
    enabled: bool = True
    credentials: Dict[str, str] = None
    connection: Dict[str, Any] = None
    trading: Dict[str, Any] = None
    risk_limits: Dict[str, Any] = None
    
    def validate(self) -> None:
        """Validate configuration"""
        if self.broker_type not in BrokerRegistry.get_available_brokers():
            raise ValueError(f"Unknown broker type: {self.broker_type}")
        
        # Validate required fields based on broker type
        if self.broker_type == 'binance':
            if not self.credentials or 'api_key' not in self.credentials:
                raise ValueError("Binance requires api_key in credentials")
        elif self.broker_type == 'interactive_brokers':
            if not self.connection or 'host' not in self.connection:
                raise ValueError("IB requires host in connection settings")

class BrokerRegistry:
    """Registry for available broker implementations"""
    _brokers: Dict[str, Type[AbstractBroker]] = {}
    
    @classmethod
    def register(cls, name: str, broker_class: Type[AbstractBroker]) -> None:
        """Register a broker implementation"""
        cls._brokers[name] = broker_class
    
    @classmethod
    def get(cls, name: str) -> Optional[Type[AbstractBroker]]:
        """Get broker class by name"""
        return cls._brokers.get(name)
    
    @classmethod
    def get_available_brokers(cls) -> List[str]:
        """Get list of available broker types"""
        return list(cls._brokers.keys())

# Auto-register built-in brokers
BrokerRegistry.register('paper', PaperTradingBroker)
BrokerRegistry.register('binance', BinanceBroker)
BrokerRegistry.register('interactive_brokers', InteractiveBrokersBroker)

class BrokerFactory:
    """Factory for creating and managing broker instances"""
    
    def __init__(self, event_bus: EventBus, config_path: str = None):
        self.event_bus = event_bus
        self.config_path = config_path or "config/exchanges/"
        self._brokers: Dict[str, AbstractBroker] = {}
        self._configs: Dict[str, BrokerConfig] = {}
        self._health_monitor: Optional[BrokerHealthMonitor] = None
    
    async def initialize(self) -> None:
        """Initialize factory and load configurations"""
        # Load all broker configurations
        await self._load_configurations()
        
        # Start health monitoring
        self._health_monitor = BrokerHealthMonitor(self._brokers)
        await self._health_monitor.start()
    
    async def _load_configurations(self) -> None:
        """Load broker configurations from YAML files"""
        for filename in os.listdir(self.config_path):
            if filename.endswith('.yaml') and not filename.endswith('.example'):
                broker_name = filename[:-5]  # Remove .yaml
                
                try:
                    config = await self._load_config_file(
                        os.path.join(self.config_path, filename)
                    )
                    self._configs[broker_name] = config
                except Exception as e:
                    print(f"Failed to load config for {broker_name}: {e}")
    
    async def _load_config_file(self, filepath: str) -> BrokerConfig:
        """Load and parse configuration file"""
        with open(filepath, 'r') as f:
            raw_config = f.read()
        
        # Substitute environment variables
        template = Template(raw_config)
        substituted = template.substitute(os.environ)
        
        # Parse YAML
        config_data = yaml.safe_load(substituted)
        
        # Create config object
        config = BrokerConfig(**config_data)
        config.validate()
        
        return config
    
    async def create_broker(self, name: str) -> AbstractBroker:
        """Create or get broker instance"""
        # Return existing instance
        if name in self._brokers:
            return self._brokers[name]
        
        # Check configuration exists
        if name not in self._configs:
            raise ValueError(f"No configuration found for broker: {name}")
        
        config = self._configs[name]
        if not config.enabled:
            raise ValueError(f"Broker {name} is disabled")
        
        # Get broker class
        broker_class = BrokerRegistry.get(config.broker_type)
        if not broker_class:
            raise ValueError(f"No implementation for broker type: {config.broker_type}")
        
        # Create broker instance
        broker_config = {
            **config.credentials,
            **config.connection,
            **config.trading,
            'risk_limits': config.risk_limits
        }
        
        broker = broker_class(
            event_bus=self.event_bus,
            config=broker_config
        )
        
        # Initialize broker
        await broker.initialize()
        
        # Register with health monitor
        self._brokers[name] = broker
        
        return broker
    
    async def get_broker(self, name: str) -> Optional[AbstractBroker]:
        """Get broker instance if exists"""
        return self._brokers.get(name)
    
    async def list_brokers(self) -> List[Dict[str, Any]]:
        """List all configured brokers with status"""
        brokers = []
        
        for name, config in self._configs.items():
            broker_info = {
                'name': name,
                'type': config.broker_type,
                'enabled': config.enabled,
                'connected': False,
                'health': 'unknown'
            }
            
            if name in self._brokers:
                broker = self._brokers[name]
                broker_info['connected'] = await broker.is_connected()
                broker_info['metrics'] = broker.get_metrics()
                
                if self._health_monitor:
                    broker_info['health'] = self._health_monitor.get_health(name)
            
            brokers.append(broker_info)
        
        return brokers
    
    async def switch_broker(self, from_broker: str, to_broker: str) -> None:
        """Switch active broker with position transfer"""
        # Ensure both brokers exist
        from_b = await self.get_broker(from_broker)
        to_b = await self.create_broker(to_broker)
        
        if not from_b or not to_b:
            raise ValueError("Invalid broker names")
        
        # Get positions from source
        positions = await from_b.get_positions()
        
        # Cancel all active orders on source
        for order_id in list(from_b._active_orders.keys()):
            await from_b.cancel_order(order_id)
        
        # Note: Actual position transfer would require manual intervention
        # This is just for switching active trading
        
        print(f"Switched from {from_broker} to {to_broker}")
        print(f"Warning: {len(positions)} positions require manual transfer")
    
    async def shutdown(self) -> None:
        """Shutdown all brokers and monitoring"""
        # Stop health monitor
        if self._health_monitor:
            await self._health_monitor.stop()
        
        # Shutdown all brokers
        for broker in self._brokers.values():
            await broker.shutdown()

class BrokerHealthMonitor:
    """Monitor broker health and performance"""
    
    def __init__(self, brokers: Dict[str, AbstractBroker]):
        self.brokers = brokers
        self._monitoring = False
        self._health_scores: Dict[str, float] = {}
        self._monitor_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start health monitoring"""
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
    
    async def stop(self) -> None:
        """Stop health monitoring"""
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self._monitoring:
            for name, broker in self.brokers.items():
                try:
                    # Check connection
                    connected = await broker.is_connected()
                    
                    # Get metrics
                    metrics = broker.get_metrics()
                    
                    # Calculate health score
                    score = self._calculate_health_score(connected, metrics)
                    self._health_scores[name] = score
                    
                    # Check for issues
                    if score < 0.5:
                        print(f"Warning: Broker {name} health degraded: {score:.2f}")
                    
                except Exception as e:
                    print(f"Error monitoring broker {name}: {e}")
                    self._health_scores[name] = 0.0
            
            await asyncio.sleep(30)  # Check every 30 seconds
    
    def _calculate_health_score(self, connected: bool, metrics: Dict) -> float:
        """Calculate health score from 0 to 1"""
        if not connected:
            return 0.0
        
        score = 1.0
        
        # Check latency
        avg_latency = metrics.get('average_latency_ms', 0)
        if avg_latency > 1000:  # >1s is bad
            score *= 0.5
        elif avg_latency > 500:  # >500ms is concerning
            score *= 0.8
        
        # Check error rates
        total_orders = metrics.get('orders_placed', 0)
        if total_orders > 0:
            rejected = metrics.get('orders_rejected', 0)
            rejection_rate = rejected / total_orders
            if rejection_rate > 0.1:  # >10% rejection
                score *= 0.7
        
        # Check connection errors
        conn_errors = metrics.get('connection_errors', 0)
        if conn_errors > 5:
            score *= 0.6
        
        return score
    
    def get_health(self, broker_name: str) -> str:
        """Get health status as string"""
        score = self._health_scores.get(broker_name, 0.0)
        
        if score >= 0.9:
            return 'excellent'
        elif score >= 0.7:
            return 'good'
        elif score >= 0.5:
            return 'fair'
        elif score > 0:
            return 'poor'
        else:
            return 'offline'
```

## Configuration Examples

### Paper Trading Configuration
```yaml
# config/exchanges/paper.yaml
broker_type: paper
enabled: true

trading:
  initial_balance: 100000.0
  base_currency: USD
  latency_ms: 50
  slippage_model: percentage
  slippage_value: 0.0005
  commission_rate: 0.001
  partial_fill_probability: 0.1
  rejection_probability: 0.02
  margin_enabled: true
  leverage: 3.0

risk_limits:
  max_position_size: 10000
  max_order_value: 50000
  max_daily_loss: 5000
  max_open_orders: 20
```

### Binance Configuration
```yaml
# config/exchanges/binance.yaml
broker_type: binance
enabled: true

credentials:
  api_key: ${BINANCE_API_KEY}
  api_secret: ${BINANCE_API_SECRET}

connection:
  testnet: true
  rate_limit_buffer: 0.8  # Use 80% of rate limits

trading:
  default_order_type: limit
  post_only: false
  time_in_force: GTC

risk_limits:
  max_position_size: 1000
  max_order_value: 10000
  min_order_value: 10
  max_open_orders: 10
```

### Interactive Brokers Configuration
```yaml
# config/exchanges/interactive_brokers.yaml
broker_type: interactive_brokers
enabled: true

connection:
  host: 127.0.0.1
  port: 7497  # TWS paper trading
  client_id: 1
  account: ""  # Empty for primary account

trading:
  md_subscription_limit: 100
  order_id_prefix: SILV
  use_adaptive_orders: true

risk_limits:
  max_position_value: 100000
  max_order_value: 50000
  max_margin_usage: 0.5
  position_limit_per_symbol: 1000
```

## Implementation Roadmap

### Phase 1: Core Infrastructure (Week 1)
1. **Days 1-2**: Implement AbstractBroker base class
   - Event integration
   - Standard data structures
   - Base functionality
   
2. **Days 3-5**: Implement Paper Trading Simulator
   - Order execution logic
   - Slippage models
   - Position tracking
   - P&L calculation

### Phase 2: Binance Integration (Week 2)
1. **Days 1-2**: REST API integration
   - Authentication
   - Order placement
   - Account queries
   
2. **Days 3-4**: WebSocket integration
   - User data stream
   - Real-time updates
   - Reconnection logic
   
3. **Day 5**: Testing and optimization
   - Rate limit testing
   - Error handling
   - Performance tuning

### Phase 3: Interactive Brokers (Week 3)
1. **Days 1-2**: IB Gateway connection
   - ib_insync setup
   - Connection management
   - Event handling
   
2. **Days 3-4**: Multi-asset support
   - Contract management
   - Order routing
   - Position tracking
   
3. **Day 5**: Complex features
   - Bracket orders
   - Market data management
   - Commission tracking

### Phase 4: Factory and Monitoring (Week 4)
1. **Days 1-2**: Broker Factory
   - Dynamic loading
   - Configuration management
   - Multi-broker support
   
2. **Days 3-4**: Health Monitoring
   - Performance metrics
   - Failover logic
   - Alert system
   
3. **Day 5**: Integration testing
   - End-to-end tests
   - Performance benchmarks
   - Documentation

## Testing Strategy

### Unit Tests
```python
# tests/unit/test_broker_interface.py
import pytest
from src.exchanges.ibroker import AbstractBroker, BrokerPosition

class TestAbstractBroker:
    def test_position_calculations(self):
        position = BrokerPosition(
            symbol="BTC/USD",
            quantity=2.5,
            average_price=40000.0,
            current_price=45000.0
        )
        
        assert position.market_value == 112500.0
        assert position.cost_basis == 100000.0
        
        position.unrealized_pnl = position.quantity * (
            position.current_price - position.average_price
        )
        assert position.unrealized_pnl == 12500.0
```

### Integration Tests
```python
# tests/integration/test_broker_integration.py
@pytest.mark.asyncio
async def test_paper_trading_flow():
    # Create event bus and broker
    event_bus = EventBus()
    broker = PaperTradingBroker(event_bus)
    
    await event_bus.start()
    await broker.initialize()
    
    # Create test order
    order = OrderEvent(
        symbol="BTC/USD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.1,
        strategy_id="test_strategy"
    )
    
    # Track fills
    fills = []
    async def fill_handler(event):
        fills.append(event)
    
    event_bus.subscribe(fill_handler, [EventType.FILL])
    
    # Place order
    await event_bus.publish(order)
    
    # Wait for execution
    await asyncio.sleep(0.5)
    
    # Verify fill
    assert len(fills) == 1
    assert fills[0].symbol == "BTC/USD"
    assert fills[0].executed_quantity == 0.1
```

## Performance Requirements

### Latency Targets
- Order placement: < 500ms (paper < 100ms)
- Order cancellation: < 300ms
- Position updates: < 1000ms
- Balance queries: < 500ms

### Throughput Targets
- Concurrent orders: 100+
- Orders per second: 10+ (exchange limited)
- Position updates: Real-time
- WebSocket messages: 1000/second

## Security Considerations

1. **Credential Management**
   - Environment variables for API keys
   - Encrypted credential storage
   - Separate keys for test/production

2. **Order Validation**
   - Pre-trade risk checks
   - Position limit enforcement
   - Order value validation

3. **Network Security**
   - TLS for all connections
   - IP whitelisting where supported
   - API key permissions (trade-only)

4. **Audit Trail**
   - All orders logged
   - Execution history retained
   - Error tracking

## Conclusion

This modular broker interface design provides a robust foundation for the Silvertine trading platform, with:

- **Clean abstraction** allowing easy addition of new brokers
- **Event-driven integration** with the existing architecture
- **Realistic paper trading** for strategy development
- **Production-ready** exchange adapters
- **Comprehensive monitoring** and failover capabilities

The design emphasizes reliability, performance, and extensibility while maintaining clean separation of concerns.