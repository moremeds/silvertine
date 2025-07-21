# Modular Broker Interface Implementation Plan

## Quick Start Guide

This document provides an actionable implementation plan for Task 3: Create Modular Broker Interface, building on the existing event-driven architecture from Task 2.

## Implementation Overview

### Project Structure

```
src/
├── exchanges/              # Broker implementations
│   ├── __init__.py
│   ├── ibroker.py         # AbstractBroker interface
│   ├── factory.py         # BrokerFactory and registry
│   ├── paper/             # Paper trading implementation
│   │   ├── __init__.py
│   │   └── paper_broker.py
│   ├── binance/           # Binance implementation
│   │   ├── __init__.py
│   │   ├── binance_broker.py
│   │   └── binance_client.py
│   └── ib/                # Interactive Brokers implementation
│       ├── __init__.py
│       ├── ib_broker.py
│       └── ib_client.py
├── core/                  # Existing event system
│   └── events/
│       └── broker_events.py  # New broker-specific events
config/
├── exchanges/             # Broker configurations
│   ├── paper.yaml
│   ├── binance.yaml.example
│   └── interactive_brokers.yaml.example
```

## Phase-by-Phase Implementation

### Phase 1: AbstractBroker Base Class (Days 1-2)

#### Step 1.1: Create Base Interface
```bash
# Create directories
mkdir -p src/exchanges/{paper,binance,ib}
touch src/exchanges/__init__.py
touch src/exchanges/ibroker.py

# Install dependencies
poetry add aiohttp pydantic
poetry add --group dev pytest-asyncio pytest-benchmark
```

#### Step 1.2: Implement AbstractBroker
1. **Core Components**:
   - Data structures: `BrokerPosition`, `BrokerBalance`, `BrokerAccountInfo`
   - Connection management with state tracking
   - Event bus integration for order handling
   - Metrics collection framework

2. **Key Methods**:
   ```python
   # Order Management
   async def place_order(order: OrderEvent) -> str
   async def cancel_order(order_id: str) -> bool
   async def modify_order(...) -> bool
   
   # Position Management
   async def get_positions() -> Dict[str, BrokerPosition]
   async def get_position(symbol: str) -> Optional[BrokerPosition]
   
   # Account Management
   async def get_account_info() -> BrokerAccountInfo
   async def get_balance(currency: str) -> Dict[str, BrokerBalance]
   ```

3. **Event Integration**:
   - Subscribe to `OrderEvent` from strategies
   - Publish `FillEvent` on execution
   - Handle order status updates

#### Step 1.3: Create Broker-Specific Events
```python
# src/core/events/broker_events.py
@dataclass
class OrderUpdateEvent(Event):
    """Order status update event"""
    event_type: EventType = EventType.ORDER_UPDATE
    order_id: str
    broker_order_id: str
    status: OrderStatus
    filled_quantity: float = 0.0
    remaining_quantity: float = 0.0
    average_fill_price: float = 0.0
    update_time: datetime = field(default_factory=datetime.utcnow)

@dataclass
class PositionUpdateEvent(Event):
    """Position change event"""
    event_type: EventType = EventType.POSITION_UPDATE
    symbol: str
    quantity: float
    average_price: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
```

#### Step 1.4: Write Unit Tests
```python
# tests/unit/test_abstract_broker.py
class TestAbstractBroker:
    async def test_event_subscription(self):
        """Test broker subscribes to order events"""
        pass
    
    async def test_fill_event_publishing(self):
        """Test broker publishes fill events"""
        pass
    
    async def test_metrics_collection(self):
        """Test performance metrics"""
        pass
```

### Phase 2: Paper Trading Simulator (Days 3-5)

#### Step 2.1: Implement PaperTradingBroker
1. **Configuration System**:
   ```python
   @dataclass
   class PaperTradingConfig:
       initial_balance: float = 100000.0
       latency_ms: int = 50
       slippage_model: SlippageModel = SlippageModel.PERCENTAGE
       slippage_value: float = 0.0005
       commission_rate: float = 0.001
   ```

2. **Order Execution Engine**:
   - Market order immediate execution
   - Limit order price monitoring
   - Stop order trigger watching
   - Partial fill simulation

3. **Slippage Models**:
   - Fixed amount slippage
   - Percentage-based slippage
   - Market impact model (size-dependent)

4. **Position Tracking**:
   - Real-time P&L calculation
   - Commission tracking
   - Execution history storage

#### Step 2.2: Market Data Integration
```python
async def _handle_market_data(self, event: MarketDataEvent):
    """Update prices for order execution"""
    self._last_prices[event.symbol] = event.price
    
    # Check pending limit orders
    await self._check_limit_orders(event.symbol, event.price)
    
    # Check stop orders
    await self._check_stop_orders(event.symbol, event.price)
```

#### Step 2.3: Testing Paper Trading
```python
# tests/integration/test_paper_trading.py
async def test_realistic_execution():
    """Test order execution with slippage and commission"""
    broker = PaperTradingBroker(event_bus, config)
    
    # Place market order
    order = OrderEvent(
        symbol="BTC/USD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=1.0
    )
    
    # Verify execution with slippage
    fill = await wait_for_fill(order.order_id)
    assert fill.executed_price > market_price  # Buy-side slippage
    assert fill.commission > 0
```

### Phase 3: Binance Exchange Adapter (Week 2)

#### Step 3.1: API Client Setup
```bash
# Install Binance library
poetry add python-binance
# Or use ccxt for multi-exchange support
poetry add ccxt
```

#### Step 3.2: Implement BinanceBroker
1. **REST API Integration**:
   ```python
   class BinanceClient:
       async def place_order(self, symbol: str, side: str, 
                           order_type: str, **kwargs) -> Dict:
           """Place order via REST API with rate limiting"""
           await self.rate_limiter.acquire()
           # Implementation
   ```

2. **WebSocket Streams**:
   ```python
   async def _connect_user_stream(self):
       """Connect to user data stream for real-time updates"""
       self.listen_key = await self._get_listen_key()
       self.user_ws = await self._create_websocket(
           f"{self.ws_url}/{self.listen_key}",
           self._handle_user_message
       )
   ```

3. **Order Type Mapping**:
   ```python
   ORDER_TYPE_MAP = {
       OrderType.MARKET: 'MARKET',
       OrderType.LIMIT: 'LIMIT',
       OrderType.STOP: 'STOP_LOSS',
       OrderType.STOP_LIMIT: 'STOP_LOSS_LIMIT'
   }
   ```

4. **Rate Limiting**:
   ```python
   class RateLimiter:
       def __init__(self, requests_per_minute: int):
           self.rpm = requests_per_minute
           self.tokens = TokenBucket(rpm, rpm/60)
       
       async def acquire(self):
           await self.tokens.acquire()
   ```

#### Step 3.3: Error Handling
- Connection failures with exponential backoff
- Order rejection handling
- WebSocket reconnection logic
- API error code mapping

### Phase 4: Interactive Brokers Adapter (Week 3)

#### Step 4.1: IB Setup
```bash
# Install IB library
poetry add ib_insync
```

#### Step 4.2: Implement IBBroker
1. **Connection Management**:
   ```python
   async def connect(self):
       """Connect to IB Gateway/TWS"""
       await self.ib.connectAsync(
           host=self.host,
           port=self.port,
           clientId=self.client_id
       )
       self._setup_event_handlers()
   ```

2. **Contract Management**:
   ```python
   async def _get_contract(self, symbol: str) -> Contract:
       """Convert symbol to IB contract"""
       # Handle different asset types
       if '/' in symbol:  # Forex
           base, quote = symbol.split('/')
           return Forex(base + quote)
       # More mappings...
   ```

3. **Multi-Asset Support**:
   - Stocks (STK)
   - Forex (CASH)
   - Futures (FUT)
   - Options (OPT)
   - Crypto (CRYPTO)

4. **Order Management**:
   - Order ID tracking
   - Complex order types (bracket, trailing)
   - Commission reporting

### Phase 5: Broker Factory (Week 4, Days 1-2)

#### Step 5.1: Configuration System
```yaml
# config/exchanges/broker_template.yaml
broker_type: ${BROKER_TYPE}
enabled: ${ENABLED:true}

credentials:
  api_key: ${API_KEY}
  api_secret: ${API_SECRET}

connection:
  host: ${HOST:localhost}
  port: ${PORT:7497}

trading:
  default_order_type: limit
  max_slippage: 0.001

risk_limits:
  max_position_size: ${MAX_POSITION:1000}
  max_order_value: ${MAX_ORDER:10000}
```

#### Step 5.2: Factory Implementation
```python
class BrokerFactory:
    async def create_broker(self, name: str) -> AbstractBroker:
        """Create broker from configuration"""
        config = await self._load_config(name)
        broker_class = BrokerRegistry.get(config.broker_type)
        
        broker = broker_class(self.event_bus, config)
        await broker.initialize()
        
        return broker
```

### Phase 6: Health Monitoring (Week 4, Days 3-4)

#### Step 6.1: Metrics Collection
```python
class BrokerMetrics:
    def __init__(self):
        self.order_latencies = []
        self.fill_rates = {}
        self.connection_uptime = 0
        self.error_counts = defaultdict(int)
    
    def record_order_latency(self, latency_ms: float):
        self.order_latencies.append(latency_ms)
    
    def get_average_latency(self) -> float:
        return sum(self.order_latencies) / len(self.order_latencies)
```

#### Step 6.2: Health Monitoring
```python
class BrokerHealthMonitor:
    async def check_broker_health(self, broker: AbstractBroker) -> float:
        """Calculate health score 0-1"""
        # Check connection
        connected = await broker.is_connected()
        if not connected:
            return 0.0
        
        # Check metrics
        metrics = broker.get_metrics()
        score = self._calculate_health_score(metrics)
        
        return score
```

### Phase 7: Integration Testing (Week 4, Day 5)

#### Step 7.1: End-to-End Tests
```python
# tests/integration/test_broker_e2e.py
async def test_multi_broker_operation():
    """Test multiple brokers operating simultaneously"""
    factory = BrokerFactory(event_bus)
    
    # Create brokers
    paper = await factory.create_broker('paper')
    binance = await factory.create_broker('binance_testnet')
    
    # Place orders on both
    # Verify execution
    # Check positions
```

#### Step 7.2: Performance Benchmarks
```python
# tests/performance/test_broker_latency.py
@pytest.mark.benchmark
async def test_order_latency(benchmark):
    """Benchmark order placement latency"""
    broker = PaperTradingBroker(event_bus)
    
    async def place_order():
        order = create_test_order()
        await broker.place_order(order)
    
    result = benchmark(place_order)
    assert result < 0.1  # <100ms
```

## Development Workflow

### Daily Development Process
1. **Morning**:
   - Review overnight test results
   - Check broker API updates/changes
   - Plan day's implementation tasks

2. **Implementation**:
   - Write tests first (TDD)
   - Implement feature
   - Run unit tests
   - Update documentation

3. **Testing**:
   - Run integration tests
   - Check performance benchmarks
   - Verify error handling

4. **End of Day**:
   - Commit code with descriptive message
   - Update task progress in TaskMaster
   - Log any blockers or issues

### Testing Strategy

#### Unit Tests (Target: 90% coverage)
- Individual broker methods
- Event handling logic
- Data structure validation
- Error scenarios

#### Integration Tests
- Event flow testing
- Multi-broker coordination
- Real API testing (sandbox)
- WebSocket reliability

#### Performance Tests
- Latency measurements
- Throughput testing
- Memory usage profiling
- Concurrent operation tests

### Configuration Management

#### Environment Setup
```bash
# .env.example
# Binance Testnet
BINANCE_TESTNET_API_KEY=your_testnet_key
BINANCE_TESTNET_SECRET=your_testnet_secret

# Interactive Brokers
IB_HOST=127.0.0.1
IB_PORT=7497
IB_CLIENT_ID=1

# Paper Trading
PAPER_INITIAL_BALANCE=100000
PAPER_BASE_CURRENCY=USD
```

#### Configuration Validation
```python
# src/exchanges/config_validator.py
def validate_broker_config(config: Dict) -> None:
    """Validate broker configuration"""
    required_fields = ['broker_type', 'enabled']
    
    for field in required_fields:
        if field not in config:
            raise ValueError(f"Missing required field: {field}")
    
    # Broker-specific validation
    if config['broker_type'] == 'binance':
        validate_binance_config(config)
```

## Key Implementation Notes

### Event-Driven Integration
1. **Subscribe to Events**:
   - `OrderEvent` from strategies
   - `MarketDataEvent` for price updates

2. **Publish Events**:
   - `FillEvent` on execution
   - `OrderUpdateEvent` on status changes
   - `PositionUpdateEvent` on position changes

### Error Handling Patterns
```python
async def place_order_with_retry(self, order: OrderEvent) -> str:
    """Place order with retry logic"""
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            return await self.place_order(order)
        except RateLimitError:
            await asyncio.sleep(2 ** attempt)
        except ConnectionError:
            await self.reconnect()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(1)
```

### Performance Optimization
1. **Connection Pooling**:
   - Reuse HTTP sessions
   - Maintain WebSocket connections
   - Connection health checks

2. **Caching**:
   - Contract definitions
   - Account information (with TTL)
   - Order book snapshots

3. **Batch Operations**:
   - Group position queries
   - Batch order status checks
   - Aggregate metrics updates

## Success Criteria

### Functional Requirements
- All 5 subtasks completed
- Paper trading with realistic execution
- Binance testnet integration working
- IB paper trading functional
- Factory pattern with dynamic loading

### Performance Requirements
- Order latency < 500ms
- 100+ concurrent orders supported
- Real-time position updates
- WebSocket stability >99%

### Quality Requirements
- 90% test coverage
- Comprehensive error handling
- Production-ready logging
- Configuration validation
- Health monitoring active

## Next Steps

After completing the broker interface:

1. **Integration with Trading Engine** (Task 5)
   - Connect strategies to broker system
   - Order routing logic
   - Position management

2. **Risk Management Integration** (Task 8)
   - Pre-trade risk checks
   - Position limits enforcement
   - Real-time P&L monitoring

3. **TUI Integration** (Task 7)
   - Display broker status
   - Show positions and orders
   - Manual order entry

4. **Production Deployment**
   - Security audit
   - Performance optimization
   - Monitoring setup