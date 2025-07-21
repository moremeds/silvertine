# Event-Driven Core Architecture Design

## Executive Summary

This document presents a comprehensive architectural design for the Silvertine event-driven trading platform's core engine. The design leverages Python 3.11+ asyncio for high-performance asynchronous processing and Redis Streams for event persistence and replay capabilities.

## Architecture Overview

### High-Level Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Data Sources   │     │    Brokers      │     │   Strategies    │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                         │
         ▼                       ▼                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Event Bus Core Engine                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   Event     │  │   Redis     │  │    Event Processing     │ │
│  │  Publisher  │  │  Streams    │  │      Pipeline          │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
         │                       │                         │
         ▼                       ▼                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Risk Manager   │     │   Backtester    │     │   TUI/API       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Core Components

1. **Event System Architecture**: Base event classes and type definitions
2. **Redis Streams Integration**: Persistent event storage and replay
3. **Asyncio Event Bus**: In-memory event routing and processing
4. **Event Processing Pipeline**: Stream consumption and handler orchestration
5. **Monitoring & Replay System**: Observability and recovery capabilities

## Detailed Component Design

### 1. Event System Architecture

#### Base Event Classes

```python
# src/core/events/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
import uuid

class EventType(Enum):
    MARKET_DATA = "market_data"
    ORDER = "order"
    FILL = "fill"
    SIGNAL = "signal"
    SYSTEM = "system"

@dataclass
class Event(ABC):
    """Base class for all events in the system"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_type: EventType = field(init=False)
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate event after initialization"""
        self.validate()
    
    @abstractmethod
    def validate(self) -> None:
        """Validate event data integrity"""
        pass
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serialize event to dictionary for Redis storage"""
        pass
    
    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Deserialize event from dictionary"""
        pass
```

#### Core Event Types

```python
# src/core/events/market_data.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from .base import Event, EventType

@dataclass
class MarketDataEvent(Event):
    """Market data update event"""
    event_type: EventType = field(default=EventType.MARKET_DATA, init=False)
    symbol: str = ""
    price: float = 0.0
    volume: int = 0
    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None
    
    def validate(self) -> None:
        if not self.symbol:
            raise ValueError("Symbol cannot be empty")
        if self.price <= 0:
            raise ValueError("Price must be positive")
        if self.volume < 0:
            raise ValueError("Volume cannot be negative")
        if self.bid and self.ask and self.bid > self.ask:
            raise ValueError("Bid cannot exceed ask")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "source": self.source,
            "metadata": self.metadata,
            "symbol": self.symbol,
            "price": self.price,
            "volume": self.volume,
            "bid": self.bid,
            "ask": self.ask,
            "bid_size": self.bid_size,
            "ask_size": self.ask_size
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MarketDataEvent':
        return cls(
            event_id=data["event_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source=data.get("source", ""),
            metadata=data.get("metadata", {}),
            symbol=data["symbol"],
            price=data["price"],
            volume=data["volume"],
            bid=data.get("bid"),
            ask=data.get("ask"),
            bid_size=data.get("bid_size"),
            ask_size=data.get("ask_size")
        )
```

```python
# src/core/events/order.py
from dataclasses import dataclass
from enum import Enum
from .base import Event, EventType

class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"

class OrderStatus(Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

@dataclass
class OrderEvent(Event):
    """Order creation/modification event"""
    event_type: EventType = field(default=EventType.ORDER, init=False)
    order_id: str = ""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.MARKET
    quantity: float = 0.0
    price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    strategy_id: str = ""
    
    def validate(self) -> None:
        if not self.order_id:
            raise ValueError("Order ID cannot be empty")
        if not self.symbol:
            raise ValueError("Symbol cannot be empty")
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive")
        if self.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT] and not self.price:
            raise ValueError(f"{self.order_type.value} orders require price")
        if self.order_type in [OrderType.STOP, OrderType.STOP_LIMIT] and not self.stop_price:
            raise ValueError(f"{self.order_type.value} orders require stop price")
```

```python
# src/core/events/fill.py
from dataclasses import dataclass
from .base import Event, EventType

@dataclass
class FillEvent(Event):
    """Order execution/fill event"""
    event_type: EventType = field(default=EventType.FILL, init=False)
    order_id: str = ""
    symbol: str = ""
    executed_quantity: float = 0.0
    executed_price: float = 0.0
    commission: float = 0.0
    commission_asset: str = ""
    exchange: str = ""
    trade_id: str = ""
    
    def validate(self) -> None:
        if not self.order_id:
            raise ValueError("Order ID cannot be empty")
        if not self.symbol:
            raise ValueError("Symbol cannot be empty")
        if self.executed_quantity <= 0:
            raise ValueError("Executed quantity must be positive")
        if self.executed_price <= 0:
            raise ValueError("Executed price must be positive")
        if self.commission < 0:
            raise ValueError("Commission cannot be negative")
```

```python
# src/core/events/signal.py
from dataclasses import dataclass
from enum import Enum
from .base import Event, EventType

class SignalType(Enum):
    LONG = "long"
    SHORT = "short"
    EXIT = "exit"
    NEUTRAL = "neutral"

@dataclass
class SignalEvent(Event):
    """Trading signal event from strategies"""
    event_type: EventType = field(default=EventType.SIGNAL, init=False)
    symbol: str = ""
    signal_type: SignalType = SignalType.NEUTRAL
    strength: float = 0.0  # -1.0 to 1.0
    strategy_id: str = ""
    reason: str = ""
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    def validate(self) -> None:
        if not self.symbol:
            raise ValueError("Symbol cannot be empty")
        if not self.strategy_id:
            raise ValueError("Strategy ID cannot be empty")
        if not -1.0 <= self.strength <= 1.0:
            raise ValueError("Signal strength must be between -1.0 and 1.0")
```

### 2. Redis Streams Integration Layer

```python
# src/core/redis/stream_manager.py
import asyncio
import json
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
import redis.asyncio as redis
from redis.exceptions import ConnectionError, RedisError
import logging

from ..events.base import Event, EventType

logger = logging.getLogger(__name__)

class RedisStreamManager:
    """Manages Redis Streams for event persistence and replay"""
    
    def __init__(self, 
                 redis_url: str = "redis://localhost:6379",
                 max_retries: int = 3,
                 retry_delay: float = 1.0):
        self.redis_url = redis_url
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._redis: Optional[redis.Redis] = None
        self._consumer_groups: Dict[str, str] = {}
        self._stream_keys: Dict[EventType, str] = {
            EventType.MARKET_DATA: "events:market_data",
            EventType.ORDER: "events:order",
            EventType.FILL: "events:fill",
            EventType.SIGNAL: "events:signal",
            EventType.SYSTEM: "events:system"
        }
    
    async def connect(self) -> None:
        """Establish Redis connection with retry logic"""
        retries = 0
        while retries < self.max_retries:
            try:
                self._redis = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    health_check_interval=30
                )
                await self._redis.ping()
                logger.info("Connected to Redis successfully")
                await self._initialize_streams()
                return
            except ConnectionError as e:
                retries += 1
                if retries >= self.max_retries:
                    logger.error(f"Failed to connect to Redis after {self.max_retries} attempts")
                    raise
                logger.warning(f"Redis connection attempt {retries} failed: {e}")
                await asyncio.sleep(self.retry_delay * retries)
    
    async def disconnect(self) -> None:
        """Close Redis connection gracefully"""
        if self._redis:
            await self._redis.aclose()
            self._redis = None
            logger.info("Disconnected from Redis")
    
    async def _initialize_streams(self) -> None:
        """Initialize Redis streams and consumer groups"""
        for event_type, stream_key in self._stream_keys.items():
            try:
                # Create consumer group if not exists
                await self._redis.xgroup_create(
                    name=stream_key,
                    groupname="trading_engine",
                    id="0",
                    mkstream=True
                )
                logger.info(f"Created consumer group for {stream_key}")
            except redis.ResponseError as e:
                if "BUSYGROUP" in str(e):
                    logger.debug(f"Consumer group already exists for {stream_key}")
                else:
                    raise
    
    async def publish_event(self, event: Event) -> str:
        """Publish event to appropriate Redis stream"""
        if not self._redis:
            raise RuntimeError("Redis connection not established")
        
        stream_key = self._stream_keys[event.event_type]
        event_data = event.to_dict()
        
        # Add stream metadata
        event_data["_published_at"] = datetime.utcnow().isoformat()
        event_data["_version"] = "1.0"
        
        try:
            # XADD to stream
            message_id = await self._redis.xadd(
                stream_key,
                event_data,
                maxlen=100000,  # Approximate stream length limit
                approximate=True
            )
            
            logger.debug(f"Published {event.event_type.value} event {event.event_id} to stream {stream_key}")
            return message_id
            
        except RedisError as e:
            logger.error(f"Failed to publish event {event.event_id}: {e}")
            raise
    
    async def consume_events(self,
                           event_types: List[EventType],
                           consumer_name: str,
                           block: int = 1000,
                           count: int = 10) -> List[Dict[str, Any]]:
        """Consume events from specified streams"""
        if not self._redis:
            raise RuntimeError("Redis connection not established")
        
        # Build streams dict for XREADGROUP
        streams = {}
        for event_type in event_types:
            stream_key = self._stream_keys[event_type]
            streams[stream_key] = ">"  # Read only new messages
        
        try:
            messages = await self._redis.xreadgroup(
                groupname="trading_engine",
                consumername=consumer_name,
                streams=streams,
                block=block,
                count=count
            )
            
            processed_messages = []
            for stream_key, stream_messages in messages:
                for message_id, data in stream_messages:
                    processed_messages.append({
                        "stream": stream_key,
                        "id": message_id,
                        "data": data
                    })
            
            return processed_messages
            
        except RedisError as e:
            logger.error(f"Failed to consume events: {e}")
            raise
    
    async def acknowledge_event(self, stream_key: str, message_id: str) -> None:
        """Acknowledge successful event processing"""
        if not self._redis:
            raise RuntimeError("Redis connection not established")
        
        try:
            await self._redis.xack(stream_key, "trading_engine", message_id)
            logger.debug(f"Acknowledged message {message_id} in stream {stream_key}")
        except RedisError as e:
            logger.error(f"Failed to acknowledge message {message_id}: {e}")
            raise
    
    async def replay_events(self,
                          event_type: EventType,
                          start_time: Optional[str] = None,
                          end_time: Optional[str] = None,
                          count: int = 100) -> List[Dict[str, Any]]:
        """Replay historical events from a stream"""
        if not self._redis:
            raise RuntimeError("Redis connection not established")
        
        stream_key = self._stream_keys[event_type]
        start = start_time or "-"
        end = end_time or "+"
        
        try:
            messages = await self._redis.xrange(
                stream_key,
                min=start,
                max=end,
                count=count
            )
            
            return [{
                "stream": stream_key,
                "id": message_id,
                "data": data
            } for message_id, data in messages]
            
        except RedisError as e:
            logger.error(f"Failed to replay events from {stream_key}: {e}")
            raise
    
    async def get_stream_info(self, event_type: EventType) -> Dict[str, Any]:
        """Get information about a stream"""
        if not self._redis:
            raise RuntimeError("Redis connection not established")
        
        stream_key = self._stream_keys[event_type]
        
        try:
            info = await self._redis.xinfo_stream(stream_key)
            groups = await self._redis.xinfo_groups(stream_key)
            
            return {
                "stream_key": stream_key,
                "length": info["length"],
                "first_entry": info.get("first-entry"),
                "last_entry": info.get("last-entry"),
                "consumer_groups": groups
            }
        except RedisError as e:
            logger.error(f"Failed to get stream info for {stream_key}: {e}")
            raise
```

### 3. Asyncio Event Bus Core

```python
# src/core/eventbus/bus.py
import asyncio
from typing import Dict, List, Callable, Any, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime
import logging
from enum import Enum
import weakref

from ..events.base import Event, EventType

logger = logging.getLogger(__name__)

class HandlerPriority(Enum):
    """Handler execution priority levels"""
    CRITICAL = 0    # Risk management, circuit breakers
    HIGH = 1        # Order execution, position updates
    NORMAL = 2      # Strategy calculations
    LOW = 3         # Logging, metrics

@dataclass
class HandlerRegistration:
    """Represents a registered event handler"""
    handler: Callable[[Event], asyncio.Future]
    priority: HandlerPriority = HandlerPriority.NORMAL
    event_types: Set[EventType] = field(default_factory=set)
    handler_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
class EventBus:
    """Central asyncio-based event bus for in-memory event routing"""
    
    def __init__(self, 
                 max_queue_size: int = 10000,
                 enable_metrics: bool = True):
        self.max_queue_size = max_queue_size
        self.enable_metrics = enable_metrics
        
        # Separate queues for each event type to ensure ordering
        self._queues: Dict[EventType, asyncio.Queue] = {}
        self._handlers: Dict[EventType, List[HandlerRegistration]] = defaultdict(list)
        
        # Idempotency tracking (time-windowed)
        self._processed_events: Dict[str, datetime] = {}
        self._idempotency_window: int = 300  # 5 minutes
        
        # Circuit breaker for failing handlers
        self._handler_failures: Dict[str, int] = defaultdict(int)
        self._handler_circuit_open: Dict[str, datetime] = {}
        self._failure_threshold: int = 5
        self._circuit_reset_time: int = 60  # seconds
        
        # Metrics
        self._metrics = {
            "events_published": defaultdict(int),
            "events_processed": defaultdict(int),
            "events_failed": defaultdict(int),
            "queue_sizes": {},
            "processing_times": defaultdict(list)
        }
        
        # Processing tasks
        self._processing_tasks: List[asyncio.Task] = []
        self._running = False
    
    async def start(self) -> None:
        """Start event processing tasks"""
        if self._running:
            return
        
        self._running = True
        
        # Initialize queues and start processors for each event type
        for event_type in EventType:
            self._queues[event_type] = asyncio.Queue(maxsize=self.max_queue_size)
            task = asyncio.create_task(
                self._process_events(event_type),
                name=f"event_processor_{event_type.value}"
            )
            self._processing_tasks.append(task)
        
        # Start metrics collection
        if self.enable_metrics:
            task = asyncio.create_task(self._collect_metrics())
            self._processing_tasks.append(task)
        
        # Start idempotency cleanup
        task = asyncio.create_task(self._cleanup_processed_events())
        self._processing_tasks.append(task)
        
        logger.info("Event bus started")
    
    async def stop(self) -> None:
        """Stop event processing gracefully"""
        if not self._running:
            return
        
        self._running = False
        
        # Wait for queues to drain
        for event_type, queue in self._queues.items():
            if not queue.empty():
                logger.info(f"Waiting for {queue.qsize()} events in {event_type.value} queue")
                await queue.join()
        
        # Cancel processing tasks
        for task in self._processing_tasks:
            task.cancel()
        
        await asyncio.gather(*self._processing_tasks, return_exceptions=True)
        self._processing_tasks.clear()
        
        logger.info("Event bus stopped")
    
    def subscribe(self,
                  handler: Callable[[Event], asyncio.Future],
                  event_types: List[EventType],
                  priority: HandlerPriority = HandlerPriority.NORMAL) -> str:
        """Subscribe handler to specified event types"""
        registration = HandlerRegistration(
            handler=handler,
            priority=priority,
            event_types=set(event_types)
        )
        
        for event_type in event_types:
            # Insert handler in priority order
            handlers = self._handlers[event_type]
            insert_idx = 0
            for i, existing in enumerate(handlers):
                if existing.priority.value > priority.value:
                    insert_idx = i
                    break
                insert_idx = i + 1
            
            handlers.insert(insert_idx, registration)
            logger.debug(f"Subscribed handler {registration.handler_id} to {event_type.value}")
        
        return registration.handler_id
    
    def unsubscribe(self, handler_id: str) -> None:
        """Unsubscribe handler from all event types"""
        for event_type, handlers in self._handlers.items():
            self._handlers[event_type] = [
                h for h in handlers if h.handler_id != handler_id
            ]
        logger.debug(f"Unsubscribed handler {handler_id}")
    
    async def publish(self, event: Event) -> None:
        """Publish event to the bus"""
        # Check idempotency
        if self._is_duplicate_event(event):
            logger.debug(f"Duplicate event {event.event_id} ignored")
            return
        
        # Add to appropriate queue
        queue = self._queues[event.event_type]
        
        try:
            await asyncio.wait_for(
                queue.put(event),
                timeout=1.0  # Prevent indefinite blocking
            )
            
            self._metrics["events_published"][event.event_type] += 1
            self._processed_events[event.event_id] = datetime.utcnow()
            
        except asyncio.TimeoutError:
            logger.error(f"Failed to publish event {event.event_id} - queue full")
            self._metrics["events_failed"][event.event_type] += 1
            raise
        except Exception as e:
            logger.error(f"Error publishing event {event.event_id}: {e}")
            self._metrics["events_failed"][event.event_type] += 1
            raise
    
    async def _process_events(self, event_type: EventType) -> None:
        """Process events from a specific queue"""
        queue = self._queues[event_type]
        
        while self._running:
            try:
                # Get event from queue
                event = await queue.get()
                
                # Process with all registered handlers
                start_time = datetime.utcnow()
                await self._dispatch_event(event)
                
                # Track metrics
                processing_time = (datetime.utcnow() - start_time).total_seconds()
                self._metrics["processing_times"][event_type].append(processing_time)
                self._metrics["events_processed"][event_type] += 1
                
                # Mark task as done
                queue.task_done()
                
            except Exception as e:
                logger.error(f"Error processing {event_type.value} event: {e}")
                self._metrics["events_failed"][event_type] += 1
    
    async def _dispatch_event(self, event: Event) -> None:
        """Dispatch event to all registered handlers"""
        handlers = self._handlers[event.event_type]
        
        # Execute handlers concurrently within priority groups
        for priority in HandlerPriority:
            priority_handlers = [h for h in handlers if h.priority == priority]
            
            if priority_handlers:
                tasks = []
                for handler_reg in priority_handlers:
                    if self._is_circuit_open(handler_reg.handler_id):
                        continue
                    
                    task = asyncio.create_task(
                        self._execute_handler(handler_reg, event)
                    )
                    tasks.append(task)
                
                # Wait for all handlers in this priority group
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _execute_handler(self, 
                             handler_reg: HandlerRegistration,
                             event: Event) -> None:
        """Execute a single handler with error handling"""
        try:
            await asyncio.wait_for(
                handler_reg.handler(event),
                timeout=5.0  # Handler timeout
            )
            
            # Reset failure count on success
            self._handler_failures[handler_reg.handler_id] = 0
            
        except asyncio.TimeoutError:
            logger.error(f"Handler {handler_reg.handler_id} timed out processing {event.event_id}")
            self._record_handler_failure(handler_reg.handler_id)
        except Exception as e:
            logger.error(f"Handler {handler_reg.handler_id} failed processing {event.event_id}: {e}")
            self._record_handler_failure(handler_reg.handler_id)
    
    def _record_handler_failure(self, handler_id: str) -> None:
        """Record handler failure and open circuit if threshold reached"""
        self._handler_failures[handler_id] += 1
        
        if self._handler_failures[handler_id] >= self._failure_threshold:
            self._handler_circuit_open[handler_id] = datetime.utcnow()
            logger.warning(f"Circuit breaker opened for handler {handler_id}")
    
    def _is_circuit_open(self, handler_id: str) -> bool:
        """Check if handler circuit breaker is open"""
        if handler_id not in self._handler_circuit_open:
            return False
        
        open_time = self._handler_circuit_open[handler_id]
        if (datetime.utcnow() - open_time).total_seconds() > self._circuit_reset_time:
            # Reset circuit
            del self._handler_circuit_open[handler_id]
            self._handler_failures[handler_id] = 0
            logger.info(f"Circuit breaker reset for handler {handler_id}")
            return False
        
        return True
    
    def _is_duplicate_event(self, event: Event) -> bool:
        """Check if event was already processed within time window"""
        if event.event_id not in self._processed_events:
            return False
        
        processed_time = self._processed_events[event.event_id]
        age = (datetime.utcnow() - processed_time).total_seconds()
        
        return age < self._idempotency_window
    
    async def _cleanup_processed_events(self) -> None:
        """Periodically clean up old processed event IDs"""
        while self._running:
            await asyncio.sleep(60)  # Run every minute
            
            cutoff_time = datetime.utcnow()
            expired_ids = [
                event_id for event_id, processed_time in self._processed_events.items()
                if (cutoff_time - processed_time).total_seconds() > self._idempotency_window
            ]
            
            for event_id in expired_ids:
                del self._processed_events[event_id]
            
            if expired_ids:
                logger.debug(f"Cleaned up {len(expired_ids)} expired event IDs")
    
    async def _collect_metrics(self) -> None:
        """Collect queue size metrics periodically"""
        while self._running:
            await asyncio.sleep(10)  # Collect every 10 seconds
            
            for event_type, queue in self._queues.items():
                self._metrics["queue_sizes"][event_type.value] = queue.qsize()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot"""
        return {
            "events_published": dict(self._metrics["events_published"]),
            "events_processed": dict(self._metrics["events_processed"]),
            "events_failed": dict(self._metrics["events_failed"]),
            "queue_sizes": dict(self._metrics["queue_sizes"]),
            "avg_processing_times": {
                event_type.value: sum(times) / len(times) if times else 0
                for event_type, times in self._metrics["processing_times"].items()
            },
            "handler_circuit_breakers": len(self._handler_circuit_open)
        }
```

### 4. Event Processing Pipeline

```python
# src/core/pipeline/processor.py
import asyncio
from typing import Dict, List, Optional, Callable
from datetime import datetime
import logging

from ..events.base import Event, EventType
from ..events import MarketDataEvent, OrderEvent, FillEvent, SignalEvent
from ..redis.stream_manager import RedisStreamManager
from ..eventbus.bus import EventBus, HandlerPriority

logger = logging.getLogger(__name__)

class EventProcessor:
    """Bridges Redis Streams and the asyncio event bus"""
    
    def __init__(self,
                 redis_manager: RedisStreamManager,
                 event_bus: EventBus,
                 consumer_name: str = "processor_1",
                 batch_size: int = 100,
                 checkpoint_interval: int = 60):
        self.redis_manager = redis_manager
        self.event_bus = event_bus
        self.consumer_name = consumer_name
        self.batch_size = batch_size
        self.checkpoint_interval = checkpoint_interval
        
        self._running = False
        self._consumer_tasks: List[asyncio.Task] = []
        self._checkpoints: Dict[str, str] = {}  # stream -> last_id
        self._last_checkpoint_time = datetime.utcnow()
        
        # Event deserializers
        self._deserializers = {
            EventType.MARKET_DATA: MarketDataEvent.from_dict,
            EventType.ORDER: OrderEvent.from_dict,
            EventType.FILL: FillEvent.from_dict,
            EventType.SIGNAL: SignalEvent.from_dict
        }
    
    async def start(self) -> None:
        """Start event processing pipeline"""
        if self._running:
            return
        
        self._running = True
        
        # Start consumer task for each event type
        for event_type in EventType:
            if event_type == EventType.SYSTEM:
                continue  # Skip system events for now
            
            task = asyncio.create_task(
                self._consume_stream(event_type),
                name=f"stream_consumer_{event_type.value}"
            )
            self._consumer_tasks.append(task)
        
        # Start checkpoint task
        task = asyncio.create_task(self._save_checkpoints())
        self._consumer_tasks.append(task)
        
        logger.info("Event processor started")
    
    async def stop(self) -> None:
        """Stop event processing pipeline"""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel all consumer tasks
        for task in self._consumer_tasks:
            task.cancel()
        
        await asyncio.gather(*self._consumer_tasks, return_exceptions=True)
        self._consumer_tasks.clear()
        
        # Save final checkpoints
        await self._persist_checkpoints()
        
        logger.info("Event processor stopped")
    
    async def _consume_stream(self, event_type: EventType) -> None:
        """Consume events from a specific Redis stream"""
        while self._running:
            try:
                # Consume batch of events
                messages = await self.redis_manager.consume_events(
                    event_types=[event_type],
                    consumer_name=self.consumer_name,
                    block=1000,  # 1 second timeout
                    count=self.batch_size
                )
                
                if not messages:
                    continue
                
                # Process each message
                for message in messages:
                    await self._process_message(message, event_type)
                
            except Exception as e:
                logger.error(f"Error consuming {event_type.value} stream: {e}")
                await asyncio.sleep(1)  # Back off on error
    
    async def _process_message(self, 
                             message: Dict[str, Any],
                             event_type: EventType) -> None:
        """Process a single message from Redis stream"""
        stream_key = message["stream"]
        message_id = message["id"]
        data = message["data"]
        
        try:
            # Deserialize event
            deserializer = self._deserializers.get(event_type)
            if not deserializer:
                logger.error(f"No deserializer for event type {event_type}")
                return
            
            event = deserializer(data)
            
            # Validate event
            event.validate()
            
            # Transform if needed (e.g., enrich with additional data)
            event = await self._transform_event(event)
            
            # Route to event bus
            await self.event_bus.publish(event)
            
            # Acknowledge successful processing
            await self.redis_manager.acknowledge_event(stream_key, message_id)
            
            # Update checkpoint
            self._checkpoints[stream_key] = message_id
            
        except Exception as e:
            logger.error(f"Failed to process message {message_id}: {e}")
            # Don't acknowledge - will be redelivered
    
    async def _transform_event(self, event: Event) -> Event:
        """Transform event before routing (enrichment, validation, etc.)"""
        # Add processing metadata
        event.metadata["processed_at"] = datetime.utcnow().isoformat()
        event.metadata["processor"] = self.consumer_name
        
        # Event-specific transformations
        if isinstance(event, MarketDataEvent):
            # Could enrich with technical indicators, etc.
            pass
        elif isinstance(event, OrderEvent):
            # Could validate against risk limits, etc.
            pass
        
        return event
    
    async def _save_checkpoints(self) -> None:
        """Periodically save processing checkpoints"""
        while self._running:
            await asyncio.sleep(self.checkpoint_interval)
            await self._persist_checkpoints()
    
    async def _persist_checkpoints(self) -> None:
        """Persist current checkpoints to Redis"""
        if not self._checkpoints:
            return
        
        try:
            # Save checkpoints as Redis hash
            checkpoint_data = {
                f"{k}:{self.consumer_name}": v 
                for k, v in self._checkpoints.items()
            }
            
            if self.redis_manager._redis:
                await self.redis_manager._redis.hset(
                    "checkpoints",
                    mapping=checkpoint_data
                )
                
                logger.debug(f"Saved {len(checkpoint_data)} checkpoints")
        
        except Exception as e:
            logger.error(f"Failed to save checkpoints: {e}")
```

### 5. Event Monitoring and Replay System

```python
# src/core/monitoring/monitor.py
import asyncio
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from collections import deque
import json
import logging

from ..events.base import Event, EventType
from ..redis.stream_manager import RedisStreamManager
from ..eventbus.bus import EventBus

logger = logging.getLogger(__name__)

class EventMonitor:
    """Real-time event monitoring and replay coordinator"""
    
    def __init__(self,
                 redis_manager: RedisStreamManager,
                 event_bus: EventBus):
        self.redis_manager = redis_manager
        self.event_bus = event_bus
        
        # Event flow tracking
        self._event_rates: Dict[EventType, deque] = {
            event_type: deque(maxlen=60)  # Last 60 seconds
            for event_type in EventType
        }
        
        # Replay state
        self._replay_in_progress = False
        self._replay_progress: Dict[str, Any] = {}
    
    async def get_event_flow_metrics(self) -> Dict[str, Any]:
        """Get real-time event flow metrics"""
        metrics = {}
        
        for event_type in EventType:
            # Get stream info
            stream_info = await self.redis_manager.get_stream_info(event_type)
            
            # Calculate rate
            rate_data = list(self._event_rates[event_type])
            current_rate = len(rate_data)  # Events per minute
            
            metrics[event_type.value] = {
                "stream_length": stream_info["length"],
                "first_event": stream_info.get("first_entry"),
                "last_event": stream_info.get("last_entry"),
                "current_rate_per_min": current_rate,
                "consumer_groups": len(stream_info.get("consumer_groups", []))
            }
        
        # Add event bus metrics
        bus_metrics = self.event_bus.get_metrics()
        metrics["event_bus"] = bus_metrics
        
        return metrics
    
    async def replay_events(self,
                          event_type: EventType,
                          start_time: Optional[datetime] = None,
                          end_time: Optional[datetime] = None,
                          speed_multiplier: float = 1.0,
                          filter_predicate: Optional[Callable[[Event], bool]] = None) -> Dict[str, Any]:
        """Replay historical events with speed control"""
        if self._replay_in_progress:
            raise RuntimeError("Replay already in progress")
        
        self._replay_in_progress = True
        self._replay_progress = {
            "event_type": event_type.value,
            "start_time": start_time,
            "end_time": end_time,
            "speed": speed_multiplier,
            "events_replayed": 0,
            "events_filtered": 0,
            "started_at": datetime.utcnow()
        }
        
        try:
            # Convert times to Redis stream IDs
            start_id = self._datetime_to_stream_id(start_time) if start_time else "-"
            end_id = self._datetime_to_stream_id(end_time) if end_time else "+"
            
            # Replay in batches
            batch_size = 100
            last_timestamp = None
            
            while True:
                # Fetch batch of events
                messages = await self.redis_manager.replay_events(
                    event_type=event_type,
                    start_time=start_id,
                    end_time=end_id,
                    count=batch_size
                )
                
                if not messages:
                    break
                
                # Process each event
                for message in messages:
                    event_data = message["data"]
                    
                    # Deserialize event
                    event = self._deserialize_event(event_type, event_data)
                    
                    # Apply filter if provided
                    if filter_predicate and not filter_predicate(event):
                        self._replay_progress["events_filtered"] += 1
                        continue
                    
                    # Calculate delay for speed control
                    if speed_multiplier > 0 and last_timestamp:
                        time_diff = (event.timestamp - last_timestamp).total_seconds()
                        delay = time_diff / speed_multiplier
                        if delay > 0:
                            await asyncio.sleep(delay)
                    
                    # Publish to event bus
                    await self.event_bus.publish(event)
                    
                    self._replay_progress["events_replayed"] += 1
                    last_timestamp = event.timestamp
                
                # Update start_id for next batch
                if messages:
                    start_id = messages[-1]["id"]
                    
                    # Check if we've reached the end time
                    last_event_time = datetime.fromisoformat(
                        messages[-1]["data"]["timestamp"]
                    )
                    if end_time and last_event_time >= end_time:
                        break
            
            self._replay_progress["completed_at"] = datetime.utcnow()
            self._replay_progress["duration"] = (
                self._replay_progress["completed_at"] - 
                self._replay_progress["started_at"]
            ).total_seconds()
            
            return self._replay_progress
            
        finally:
            self._replay_in_progress = False
    
    def _datetime_to_stream_id(self, dt: datetime) -> str:
        """Convert datetime to Redis stream ID format"""
        timestamp_ms = int(dt.timestamp() * 1000)
        return f"{timestamp_ms}-0"
    
    def _deserialize_event(self, event_type: EventType, data: Dict[str, Any]) -> Event:
        """Deserialize event from Redis data"""
        from ..events import MarketDataEvent, OrderEvent, FillEvent, SignalEvent
        
        deserializers = {
            EventType.MARKET_DATA: MarketDataEvent.from_dict,
            EventType.ORDER: OrderEvent.from_dict,
            EventType.FILL: FillEvent.from_dict,
            EventType.SIGNAL: SignalEvent.from_dict
        }
        
        deserializer = deserializers.get(event_type)
        if not deserializer:
            raise ValueError(f"No deserializer for event type {event_type}")
        
        return deserializer(data)
    
    async def create_event_audit_trail(self,
                                     event_id: str,
                                     event_type: EventType) -> List[Dict[str, Any]]:
        """Create audit trail for a specific event"""
        audit_trail = []
        
        # Search for event in stream
        messages = await self.redis_manager.replay_events(
            event_type=event_type,
            count=10000  # Search through recent events
        )
        
        for message in messages:
            if message["data"].get("event_id") == event_id:
                audit_trail.append({
                    "stream_id": message["id"],
                    "timestamp": message["data"].get("timestamp"),
                    "published_at": message["data"].get("_published_at"),
                    "processor": message["data"].get("metadata", {}).get("processor"),
                    "data": message["data"]
                })
                break
        
        return audit_trail
```

## Implementation Roadmap

### Phase 1: Core Event System (Week 1)
1. Implement base event classes and core event types
2. Set up project structure and development environment
3. Write comprehensive unit tests for event validation
4. Create event serialization/deserialization logic

### Phase 2: Redis Integration (Week 1-2)
1. Implement RedisStreamManager with connection pooling
2. Set up Redis Streams and consumer groups
3. Implement event publishing and consumption
4. Add replay functionality and checkpointing

### Phase 3: Asyncio Event Bus (Week 2)
1. Implement EventBus with priority-based handlers
2. Add circuit breaker pattern for fault tolerance
3. Implement idempotency checks
4. Create metrics collection system

### Phase 4: Processing Pipeline (Week 3)
1. Implement EventProcessor to bridge Redis and EventBus
2. Add event transformation and enrichment
3. Implement backpressure handling
4. Create checkpoint management

### Phase 5: Monitoring & Tools (Week 3-4)
1. Implement EventMonitor for observability
2. Create replay coordinator with speed control
3. Add audit trail functionality
4. Build command-line tools for debugging

## Performance Considerations

### Latency Optimization
- **Event Processing**: Target < 100ms through efficient asyncio usage
- **Queue Management**: Separate queues per event type prevent head-of-line blocking
- **Batch Processing**: Redis XREADGROUP with configurable batch sizes
- **Memory Efficiency**: Bounded queues and time-windowed caches

### Scalability Design
- **Horizontal Scaling**: Multiple consumer instances via Redis consumer groups
- **Vertical Scaling**: Asyncio concurrent handler execution
- **Resource Management**: Configurable queue sizes and connection pools
- **Load Distribution**: Priority-based handler execution

### Reliability Features
- **At-Least-Once Delivery**: Redis Streams with explicit acknowledgment
- **Idempotency**: Time-windowed event ID tracking
- **Circuit Breakers**: Automatic handler failure isolation
- **Graceful Degradation**: Continue operation with failed handlers

## Testing Strategy

### Unit Tests
```python
# tests/unit/test_events.py
import pytest
from datetime import datetime
from src.core.events import MarketDataEvent, OrderEvent

class TestMarketDataEvent:
    def test_valid_event_creation(self):
        event = MarketDataEvent(
            symbol="BTC/USD",
            price=50000.0,
            volume=100,
            bid=49999.0,
            ask=50001.0
        )
        assert event.symbol == "BTC/USD"
        assert event.price == 50000.0
        
    def test_event_validation(self):
        with pytest.raises(ValueError, match="Symbol cannot be empty"):
            MarketDataEvent(symbol="", price=100.0)
        
        with pytest.raises(ValueError, match="Price must be positive"):
            MarketDataEvent(symbol="BTC/USD", price=-100.0)
    
    def test_event_serialization(self):
        event = MarketDataEvent(symbol="BTC/USD", price=50000.0, volume=100)
        data = event.to_dict()
        
        assert data["symbol"] == "BTC/USD"
        assert data["price"] == 50000.0
        assert "event_id" in data
        assert "timestamp" in data
        
        # Test round-trip
        restored = MarketDataEvent.from_dict(data)
        assert restored.symbol == event.symbol
        assert restored.price == event.price
```

### Integration Tests
```python
# tests/integration/test_event_flow.py
import asyncio
import pytest
from src.core.redis.stream_manager import RedisStreamManager
from src.core.eventbus.bus import EventBus
from src.core.pipeline.processor import EventProcessor
from src.core.events import MarketDataEvent

@pytest.mark.asyncio
async def test_end_to_end_event_flow():
    # Setup
    redis_manager = RedisStreamManager()
    event_bus = EventBus()
    processor = EventProcessor(redis_manager, event_bus)
    
    received_events = []
    
    async def test_handler(event):
        received_events.append(event)
    
    try:
        # Start components
        await redis_manager.connect()
        await event_bus.start()
        event_bus.subscribe(test_handler, [EventType.MARKET_DATA])
        await processor.start()
        
        # Publish test event
        test_event = MarketDataEvent(
            symbol="BTC/USD",
            price=50000.0,
            volume=100
        )
        
        await redis_manager.publish_event(test_event)
        
        # Wait for processing
        await asyncio.sleep(0.5)
        
        # Verify
        assert len(received_events) == 1
        assert received_events[0].symbol == "BTC/USD"
        assert received_events[0].price == 50000.0
        
    finally:
        # Cleanup
        await processor.stop()
        await event_bus.stop()
        await redis_manager.disconnect()
```

### Performance Tests
```python
# tests/performance/test_throughput.py
import asyncio
import time
from src.core.eventbus.bus import EventBus
from src.core.events import MarketDataEvent

async def test_event_bus_throughput():
    event_bus = EventBus()
    events_processed = 0
    
    async def counting_handler(event):
        nonlocal events_processed
        events_processed += 1
    
    await event_bus.start()
    event_bus.subscribe(counting_handler, [EventType.MARKET_DATA])
    
    # Publish 10,000 events
    start_time = time.time()
    
    for i in range(10000):
        event = MarketDataEvent(
            symbol="BTC/USD",
            price=50000.0 + i,
            volume=100
        )
        await event_bus.publish(event)
    
    # Wait for processing
    await asyncio.sleep(2.0)
    
    duration = time.time() - start_time
    throughput = events_processed / duration
    
    print(f"Processed {events_processed} events in {duration:.2f}s")
    print(f"Throughput: {throughput:.0f} events/second")
    
    assert throughput > 1000  # Should handle >1000 events/second
    
    await event_bus.stop()
```

## Deployment Considerations

### Configuration Management
```yaml
# config/event_engine.yaml
redis:
  url: "${REDIS_URL:redis://localhost:6379}"
  max_retries: 3
  retry_delay: 1.0
  stream_max_length: 100000

event_bus:
  max_queue_size: 10000
  enable_metrics: true
  idempotency_window: 300
  handler_timeout: 5.0
  circuit_breaker:
    failure_threshold: 5
    reset_time: 60

processor:
  batch_size: 100
  checkpoint_interval: 60
  consumer_name: "${HOSTNAME:processor_1}"

monitoring:
  metrics_port: 9090
  log_level: "${LOG_LEVEL:INFO}"
```

### Docker Deployment
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY config/ ./config/

# Set environment
ENV PYTHONPATH=/app
ENV LOG_LEVEL=INFO

# Health check
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import redis; r = redis.from_url('redis://localhost:6379'); r.ping()"

# Run event engine
CMD ["python", "-m", "src.core.main"]
```

### Monitoring Setup
```yaml
# docker-compose.yml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis-data:/data
    ports:
      - "6379:6379"
  
  event-engine:
    build: .
    environment:
      - REDIS_URL=redis://redis:6379
      - LOG_LEVEL=INFO
    depends_on:
      - redis
    volumes:
      - ./config:/app/config
      - ./silver_cache/logs:/app/logs
  
  prometheus:
    image: prom/prometheus
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
  
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana

volumes:
  redis-data:
  grafana-data:
```

## Security Considerations

1. **Redis Security**
   - Enable Redis AUTH with strong passwords
   - Use TLS for Redis connections in production
   - Implement network isolation between components

2. **Event Validation**
   - Strict input validation on all event fields
   - Type checking and bounds validation
   - Sanitization of string inputs

3. **Access Control**
   - Component-level authentication for event publishing
   - Read-only access for monitoring tools
   - Audit logging for all administrative actions

4. **Data Protection**
   - Encryption at rest for Redis persistence
   - Sensitive data masking in logs
   - GDPR compliance for event retention

## Conclusion

This event-driven architecture provides a robust foundation for the Silvertine trading platform. Key benefits include:

- **High Performance**: Sub-100ms event processing with asyncio
- **Reliability**: At-least-once delivery with Redis Streams
- **Scalability**: Horizontal scaling via consumer groups
- **Observability**: Comprehensive metrics and monitoring
- **Maintainability**: Clean separation of concerns with clear interfaces

The design supports all requirements while providing room for future enhancements and optimizations.