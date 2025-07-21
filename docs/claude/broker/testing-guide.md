# Broker Interface Testing Guide

## Overview

This guide provides comprehensive testing strategies for the Silvertine modular broker interface, ensuring reliability, performance, and correctness across all broker implementations.

## Testing Framework Setup

### Dependencies
```bash
# Install testing dependencies
poetry add --group dev pytest pytest-asyncio pytest-cov pytest-benchmark
poetry add --group dev pytest-mock aioresponses
poetry add --group dev pytest-timeout pytest-repeat
```

### Test Configuration
```python
# tests/conftest.py
import pytest
import asyncio
from src.core.eventbus import EventBus
from src.exchanges.paper import PaperTradingBroker

@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def event_bus():
    """Create and start event bus"""
    bus = EventBus()
    await bus.start()
    yield bus
    await bus.stop()

@pytest.fixture
async def paper_broker(event_bus):
    """Create paper trading broker"""
    broker = PaperTradingBroker(event_bus)
    await broker.initialize()
    yield broker
    await broker.shutdown()
```

## Unit Testing

### AbstractBroker Tests

```python
# tests/unit/test_abstract_broker.py
import pytest
from unittest.mock import Mock, AsyncMock
from src.exchanges.ibroker import AbstractBroker, BrokerPosition, BrokerBalance

class MockBroker(AbstractBroker):
    """Mock implementation for testing abstract methods"""
    
    async def connect(self):
        self._connection_state = ConnectionState.CONNECTED
    
    async def disconnect(self):
        self._connection_state = ConnectionState.DISCONNECTED
    
    async def is_connected(self):
        return self._connection_state == ConnectionState.CONNECTED
    
    async def place_order(self, order):
        return f"MOCK_{order.order_id}"
    
    # ... implement other abstract methods

class TestAbstractBroker:
    
    def test_broker_position_calculations(self):
        """Test position P&L calculations"""
        position = BrokerPosition(
            symbol="BTC/USD",
            quantity=2.5,
            average_price=40000.0,
            current_price=45000.0
        )
        
        assert position.market_value == 112500.0
        assert position.cost_basis == 100000.0
        
        # Calculate unrealized P&L
        position.unrealized_pnl = position.quantity * (
            position.current_price - position.average_price
        )
        assert position.unrealized_pnl == 12500.0
    
    def test_broker_balance_margin(self):
        """Test balance margin calculations"""
        balance = BrokerBalance(
            currency="USD",
            available=50000.0,
            total=100000.0,
            margin_used=30000.0
        )
        
        assert balance.margin_available == 20000.0
    
    @pytest.mark.asyncio
    async def test_event_subscription(self, event_bus):
        """Test broker subscribes to order events"""
        broker = MockBroker(event_bus)
        await broker.initialize()
        
        # Verify subscription
        assert len(event_bus._handlers[EventType.ORDER]) > 0
    
    @pytest.mark.asyncio
    async def test_order_tracking(self, event_bus):
        """Test internal order tracking"""
        broker = MockBroker(event_bus)
        await broker.initialize()
        
        # Create test order
        order = OrderEvent(
            order_id="TEST001",
            symbol="BTC/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1.0
        )
        
        # Simulate order handling
        await broker._handle_order_event(order)
        
        assert "TEST001" in broker._active_orders
        assert broker._metrics['orders_placed'] == 1
    
    @pytest.mark.asyncio
    async def test_fill_event_publishing(self, event_bus):
        """Test broker publishes fill events correctly"""
        broker = MockBroker(event_bus)
        
        # Track published events
        published_events = []
        
        async def capture_event(event):
            published_events.append(event)
        
        event_bus.subscribe(capture_event, [EventType.FILL])
        
        # Publish fill
        await broker._publish_fill_event(
            order_id="TEST001",
            symbol="BTC/USD",
            executed_quantity=1.0,
            executed_price=50000.0,
            commission=50.0
        )
        
        # Verify
        assert len(published_events) == 1
        fill = published_events[0]
        assert fill.order_id == "TEST001"
        assert fill.executed_price == 50000.0
        assert fill.commission == 50.0
    
    def test_metrics_collection(self):
        """Test performance metrics tracking"""
        broker = MockBroker(Mock())
        
        # Simulate activity
        broker._metrics['orders_placed'] = 100
        broker._metrics['orders_filled'] = 95
        broker._metrics['orders_rejected'] = 5
        broker._metrics['total_latency'] = 45.0  # seconds
        
        metrics = broker.get_metrics()
        
        assert metrics['orders_placed'] == 100
        assert metrics['orders_filled'] == 95
        assert metrics['average_latency_ms'] == 450.0  # 45s/100 * 1000
```

### Paper Trading Tests

```python
# tests/unit/test_paper_trading.py
import pytest
from datetime import datetime
from src.exchanges.paper import (
    PaperTradingBroker, PaperTradingConfig, SlippageModel
)

class TestPaperTrading:
    
    @pytest.fixture
    def config(self):
        return PaperTradingConfig(
            initial_balance=100000.0,
            latency_ms=10,
            slippage_model=SlippageModel.PERCENTAGE,
            slippage_value=0.001,
            commission_rate=0.001
        )
    
    @pytest.mark.asyncio
    async def test_market_order_execution(self, event_bus, config):
        """Test market order executes with slippage"""
        broker = PaperTradingBroker(event_bus, config)
        await broker.initialize()
        
        # Set market price
        market_event = MarketDataEvent(
            symbol="BTC/USD",
            price=50000.0,
            volume=100
        )
        await event_bus.publish(market_event)
        await asyncio.sleep(0.1)
        
        # Place order
        order = OrderEvent(
            order_id="MKT001",
            symbol="BTC/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1.0
        )
        
        broker_order_id = await broker.place_order(order)
        assert broker_order_id == "PAPER_MKT001"
        
        # Wait for execution
        await asyncio.sleep(0.1)
        
        # Check position
        positions = await broker.get_positions()
        assert "BTC/USD" in positions
        position = positions["BTC/USD"]
        assert position.quantity == 1.0
        # Price should include slippage (0.1% for buy side)
        assert position.average_price > 50000.0
        assert position.average_price <= 50050.0
    
    @pytest.mark.asyncio
    async def test_limit_order_execution(self, event_bus, config):
        """Test limit order waits for price"""
        broker = PaperTradingBroker(event_bus, config)
        await broker.initialize()
        
        # Place limit order above market
        order = OrderEvent(
            order_id="LMT001",
            symbol="BTC/USD",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=1.0,
            price=49000.0  # Below market
        )
        
        await broker.place_order(order)
        
        # Publish high price - should not execute
        await event_bus.publish(MarketDataEvent(
            symbol="BTC/USD", price=50000.0
        ))
        await asyncio.sleep(0.1)
        
        positions = await broker.get_positions()
        assert "BTC/USD" not in positions
        
        # Publish low price - should execute
        await event_bus.publish(MarketDataEvent(
            symbol="BTC/USD", price=48900.0
        ))
        await asyncio.sleep(0.2)
        
        positions = await broker.get_positions()
        assert "BTC/USD" in positions
        assert positions["BTC/USD"].average_price == 49000.0
    
    def test_slippage_models(self, config):
        """Test different slippage model calculations"""
        broker = PaperTradingBroker(None, config)
        
        # Test percentage slippage
        config.slippage_model = SlippageModel.PERCENTAGE
        config.slippage_value = 0.001  # 0.1%
        
        slipped_price = broker._apply_slippage(
            50000.0, OrderSide.BUY, 1.0
        )
        assert slipped_price == 50050.0  # 0.1% higher for buy
        
        slipped_price = broker._apply_slippage(
            50000.0, OrderSide.SELL, 1.0
        )
        assert slipped_price == 49950.0  # 0.1% lower for sell
        
        # Test market impact
        config.slippage_model = SlippageModel.MARKET_IMPACT
        
        # Small order - minimal impact
        slipped_price = broker._apply_slippage(
            50000.0, OrderSide.BUY, 0.1
        )
        assert slipped_price < 50005.0
        
        # Large order - more impact
        slipped_price = broker._apply_slippage(
            50000.0, OrderSide.BUY, 100.0
        )
        assert slipped_price > 50050.0
    
    @pytest.mark.asyncio
    async def test_partial_fills(self, event_bus):
        """Test partial fill simulation"""
        config = PaperTradingConfig(
            partial_fill_probability=1.0  # Always partial fill
        )
        broker = PaperTradingBroker(event_bus, config)
        await broker.initialize()
        
        # Track fills
        fills = []
        
        async def track_fills(event):
            if isinstance(event, FillEvent):
                fills.append(event)
        
        event_bus.subscribe(track_fills, [EventType.FILL])
        
        # Place order
        order = OrderEvent(
            order_id="PARTIAL001",
            symbol="BTC/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=10.0
        )
        
        await broker.place_order(order)
        await asyncio.sleep(0.5)
        
        # Should have multiple fills
        assert len(fills) > 1
        total_filled = sum(f.executed_quantity for f in fills)
        assert abs(total_filled - 10.0) < 0.0001
    
    @pytest.mark.asyncio
    async def test_position_pnl_tracking(self, event_bus, config):
        """Test P&L calculation and tracking"""
        broker = PaperTradingBroker(event_bus, config)
        await broker.initialize()
        
        # Buy position
        await event_bus.publish(MarketDataEvent(
            symbol="BTC/USD", price=50000.0
        ))
        
        buy_order = OrderEvent(
            order_id="BUY001",
            symbol="BTC/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=2.0
        )
        await broker.place_order(buy_order)
        await asyncio.sleep(0.1)
        
        # Update price - unrealized profit
        await event_bus.publish(MarketDataEvent(
            symbol="BTC/USD", price=55000.0
        ))
        
        positions = await broker.get_positions()
        position = positions["BTC/USD"]
        assert position.quantity == 2.0
        assert position.current_price == 55000.0
        expected_pnl = 2.0 * (55000.0 - position.average_price)
        assert abs(position.unrealized_pnl - expected_pnl) < 100  # Small difference OK
        
        # Sell half - realize some profit
        sell_order = OrderEvent(
            order_id="SELL001",
            symbol="BTC/USD",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=1.0
        )
        await broker.place_order(sell_order)
        await asyncio.sleep(0.1)
        
        positions = await broker.get_positions()
        position = positions["BTC/USD"]
        assert position.quantity == 1.0  # Half remaining
```

## Integration Testing

### Broker Integration Tests

```python
# tests/integration/test_broker_integration.py
import pytest
import asyncio
from unittest.mock import patch

class TestBrokerIntegration:
    
    @pytest.mark.asyncio
    async def test_event_flow_integration(self, event_bus):
        """Test complete event flow from order to fill"""
        broker = PaperTradingBroker(event_bus)
        await broker.initialize()
        
        # Track all events
        events = []
        
        async def track_event(event):
            events.append((event.event_type, event))
        
        event_bus.subscribe(track_event, [
            EventType.ORDER,
            EventType.FILL,
            EventType.MARKET_DATA
        ])
        
        # Publish market data
        await event_bus.publish(MarketDataEvent(
            symbol="ETH/USD",
            price=3000.0
        ))
        
        # Create and publish order (simulating strategy)
        order = OrderEvent(
            order_id="INT001",
            symbol="ETH/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=5.0,
            strategy_id="test_strategy"
        )
        await event_bus.publish(order)
        
        # Wait for processing
        await asyncio.sleep(0.2)
        
        # Verify event sequence
        event_types = [e[0] for e in events]
        assert EventType.MARKET_DATA in event_types
        assert EventType.ORDER in event_types
        assert EventType.FILL in event_types
        
        # Verify fill details
        fills = [e[1] for e in events if e[0] == EventType.FILL]
        assert len(fills) == 1
        fill = fills[0]
        assert fill.symbol == "ETH/USD"
        assert fill.executed_quantity == 5.0
    
    @pytest.mark.asyncio
    async def test_multiple_brokers(self, event_bus):
        """Test multiple brokers operating simultaneously"""
        # Create two paper brokers with different configs
        config1 = PaperTradingConfig(
            initial_balance=100000.0,
            commission_rate=0.001
        )
        config2 = PaperTradingConfig(
            initial_balance=50000.0,
            commission_rate=0.002
        )
        
        broker1 = PaperTradingBroker(event_bus, config1)
        broker2 = PaperTradingBroker(event_bus, config2)
        
        await broker1.initialize()
        await broker2.initialize()
        
        # Both should have different balances
        info1 = await broker1.get_account_info()
        info2 = await broker2.get_account_info()
        
        assert info1.balances["USD"].total == 100000.0
        assert info2.balances["USD"].total == 50000.0
```

### Exchange-Specific Tests

```python
# tests/integration/test_binance_integration.py
import pytest
from aioresponses import aioresponses

class TestBinanceIntegration:
    
    @pytest.mark.asyncio
    async def test_binance_connection(self, event_bus):
        """Test Binance broker connection"""
        with aioresponses() as mocked:
            # Mock API responses
            mocked.get(
                'https://testnet.binance.vision/api/v3/time',
                payload={'serverTime': 1234567890}
            )
            mocked.post(
                'https://testnet.binance.vision/api/v3/userDataStream',
                payload={'listenKey': 'test_key_123'}
            )
            
            config = {
                'api_key': 'test_key',
                'api_secret': 'test_secret',
                'testnet': True
            }
            
            broker = BinanceBroker(event_bus, config)
            await broker.connect()
            
            assert await broker.is_connected()
    
    @pytest.mark.asyncio
    async def test_binance_order_placement(self, event_bus):
        """Test order placement with mocked Binance API"""
        with aioresponses() as mocked:
            # Mock order response
            mocked.post(
                'https://testnet.binance.vision/api/v3/order',
                payload={
                    'orderId': 12345,
                    'clientOrderId': 'TEST001',
                    'status': 'NEW'
                }
            )
            
            broker = BinanceBroker(event_bus, {'testnet': True})
            
            order = OrderEvent(
                order_id="TEST001",
                symbol="BTC/USDT",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=0.001,
                price=50000.0
            )
            
            broker_order_id = await broker.place_order(order)
            assert broker_order_id == "12345"
```

## Performance Testing

### Latency Benchmarks

```python
# tests/performance/test_broker_latency.py
import pytest
import time
import statistics

class TestBrokerPerformance:
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_order_placement_latency(self, event_bus, benchmark):
        """Benchmark order placement latency"""
        broker = PaperTradingBroker(event_bus)
        await broker.initialize()
        
        # Warm up
        for _ in range(10):
            order = create_random_order()
            await broker.place_order(order)
        
        # Benchmark
        latencies = []
        
        async def place_order():
            order = create_random_order()
            start = time.perf_counter()
            await broker.place_order(order)
            end = time.perf_counter()
            latencies.append((end - start) * 1000)  # ms
        
        # Run benchmark
        result = await benchmark(place_order)
        
        # Analyze results
        avg_latency = statistics.mean(latencies)
        p99_latency = statistics.quantiles(latencies, n=100)[98]
        
        assert avg_latency < 100  # <100ms average
        assert p99_latency < 500  # <500ms p99
    
    @pytest.mark.asyncio
    async def test_concurrent_orders(self, event_bus):
        """Test handling many concurrent orders"""
        broker = PaperTradingBroker(event_bus)
        await broker.initialize()
        
        # Create many orders
        orders = []
        for i in range(100):
            order = OrderEvent(
                order_id=f"CONC{i:03d}",
                symbol="BTC/USD",
                side=OrderSide.BUY if i % 2 == 0 else OrderSide.SELL,
                order_type=OrderType.MARKET,
                quantity=0.1
            )
            orders.append(order)
        
        # Place all orders concurrently
        start = time.perf_counter()
        tasks = [broker.place_order(order) for order in orders]
        results = await asyncio.gather(*tasks)
        end = time.perf_counter()
        
        # All should succeed
        assert len(results) == 100
        assert all(r.startswith("PAPER_") for r in results)
        
        # Should complete quickly
        total_time = end - start
        assert total_time < 5.0  # <5 seconds for 100 orders
    
    @pytest.mark.asyncio
    async def test_position_update_performance(self, event_bus):
        """Test position calculation performance"""
        broker = PaperTradingBroker(event_bus)
        await broker.initialize()
        
        # Create many positions
        for i in range(50):
            symbol = f"STOCK{i}"
            broker._positions[symbol] = BrokerPosition(
                symbol=symbol,
                quantity=100,
                average_price=100.0 + i,
                current_price=100.0 + i
            )
            broker._last_prices[symbol] = 100.0 + i
        
        # Benchmark position updates
        start = time.perf_counter()
        
        for _ in range(100):
            positions = await broker.get_positions()
            # Update all prices
            for symbol in broker._positions:
                broker._last_prices[symbol] *= 1.001
        
        end = time.perf_counter()
        
        # Should handle many positions efficiently
        assert (end - start) < 1.0  # <1 second for 100 updates
```

## Stress Testing

### Connection Reliability

```python
# tests/stress/test_connection_reliability.py
import pytest
import random

class TestConnectionReliability:
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_reconnection_logic(self, event_bus):
        """Test broker reconnection under network issues"""
        
        class FlakyBroker(MockBroker):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.connection_attempts = 0
            
            async def connect(self):
                self.connection_attempts += 1
                # Fail first 2 attempts
                if self.connection_attempts < 3:
                    raise ConnectionError("Network error")
                await super().connect()
        
        broker = FlakyBroker(event_bus)
        
        # Should eventually connect
        await broker.initialize()
        assert await broker.is_connected()
        assert broker.connection_attempts == 3
    
    @pytest.mark.asyncio
    @pytest.mark.repeat(10)
    async def test_random_disconnections(self, event_bus):
        """Test handling random disconnections"""
        broker = PaperTradingBroker(event_bus)
        await broker.initialize()
        
        # Simulate random disconnections
        for _ in range(5):
            if random.random() > 0.5:
                broker._connection_state = ConnectionState.ERROR
                await asyncio.sleep(0.1)
                await broker.connect()  # Reconnect
            
            # Try to place order
            order = create_random_order()
            try:
                await broker.place_order(order)
            except Exception:
                # Should handle gracefully
                pass
        
        # Should end in good state
        assert await broker.is_connected()
```

## Testing Best Practices

### Test Organization
```
tests/
├── unit/                    # Fast, isolated tests
│   ├── test_abstract_broker.py
│   ├── test_paper_trading.py
│   ├── test_broker_events.py
│   └── test_data_structures.py
├── integration/             # Component interaction tests
│   ├── test_broker_integration.py
│   ├── test_event_flow.py
│   └── test_exchange_apis.py
├── performance/            # Benchmark tests
│   ├── test_broker_latency.py
│   └── test_throughput.py
├── stress/                 # Load and reliability tests
│   ├── test_connection_reliability.py
│   └── test_high_load.py
└── fixtures/              # Shared test data
    ├── sample_orders.py
    └── mock_responses.py
```

### Continuous Integration

```yaml
# .github/workflows/test-brokers.yml
name: Broker Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Install Poetry
      uses: snok/install-poetry@v1
    
    - name: Install dependencies
      run: poetry install
    
    - name: Run unit tests
      run: poetry run pytest tests/unit -v --cov=src.exchanges
    
    - name: Run integration tests
      run: poetry run pytest tests/integration -v
    
    - name: Run performance tests
      run: poetry run pytest tests/performance -v --benchmark-only
    
    - name: Upload coverage
      uses: codecov/codecov-action@v2
```

### Testing Checklist

#### For Each Broker Implementation
- [ ] Unit tests for all public methods
- [ ] Integration tests with event bus
- [ ] Error handling for all failure modes
- [ ] Performance benchmarks meet targets
- [ ] Stress tests pass reliably
- [ ] Mock external dependencies
- [ ] Test configuration validation
- [ ] Test metric collection
- [ ] Test health monitoring
- [ ] Documentation examples work

#### Before Release
- [ ] All tests passing
- [ ] Coverage > 90%
- [ ] No performance regressions
- [ ] Security review completed
- [ ] API compatibility verified
- [ ] Documentation updated
- [ ] Integration tests with real APIs (sandbox)
- [ ] Multi-broker coordination tested
- [ ] Failover scenarios tested
- [ ] Memory leak tests passed

## Debugging Failed Tests

### Common Issues

1. **Async Timeout**
   ```python
   # Increase timeout for slow operations
   @pytest.mark.timeout(30)
   async def test_slow_operation():
       pass
   ```

2. **Event Race Conditions**
   ```python
   # Wait for events to propagate
   await asyncio.sleep(0.1)  # Allow event processing
   ```

3. **Mock Data Issues**
   ```python
   # Ensure mocks return proper types
   mock_response = {
       'orderId': 12345,  # Not '12345' string
       'status': 'FILLED'
   }
   ```

4. **Resource Cleanup**
   ```python
   # Always cleanup in finally blocks
   try:
       await broker.connect()
       # test code
   finally:
       await broker.disconnect()
   ```

## Conclusion

Comprehensive testing ensures the broker interface is reliable, performant, and production-ready. Follow this guide to maintain high quality standards across all broker implementations.