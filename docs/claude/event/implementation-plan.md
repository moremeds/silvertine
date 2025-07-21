# Event-Driven Core Implementation Plan

## Quick Start Guide

This document provides an actionable implementation plan for Task 2: Implement Event-Driven Core Engine.

## Project Structure

```
src/
├── core/
│   ├── __init__.py
│   ├── events/
│   │   ├── __init__.py
│   │   ├── base.py          # Abstract Event class
│   │   ├── market_data.py   # MarketDataEvent
│   │   ├── order.py         # OrderEvent
│   │   ├── fill.py          # FillEvent
│   │   └── signal.py        # SignalEvent
│   ├── redis/
│   │   ├── __init__.py
│   │   └── stream_manager.py # Redis Streams integration
│   ├── eventbus/
│   │   ├── __init__.py
│   │   └── bus.py           # Asyncio event bus
│   ├── pipeline/
│   │   ├── __init__.py
│   │   └── processor.py     # Event processing pipeline
│   └── monitoring/
│       ├── __init__.py
│       └── monitor.py       # Event monitoring & replay
├── config/
│   └── event_engine.yaml    # Configuration
└── tests/
    ├── unit/
    ├── integration/
    └── performance/
```

## Implementation Steps

### Step 1: Setup Development Environment

```bash
# Create directories
mkdir -p src/core/{events,redis,eventbus,pipeline,monitoring}
mkdir -p tests/{unit,integration,performance}
mkdir -p config

# Install dependencies
poetry add redis[hiredis] pydantic python-dotenv prometheus-client
poetry add --group dev pytest pytest-asyncio pytest-cov pytest-benchmark
```

### Step 2: Implement Base Event Classes (Subtask 2.1)

1. Create `src/core/events/base.py`:
   - Abstract `Event` class with validation
   - `EventType` enum
   - Serialization/deserialization methods

2. Create concrete event classes:
   - `MarketDataEvent` in `market_data.py`
   - `OrderEvent` in `order.py`
   - `FillEvent` in `fill.py`
   - `SignalEvent` in `signal.py`

3. Write unit tests in `tests/unit/test_events.py`

### Step 3: Implement Redis Streams Integration (Subtask 2.2)

1. Create `src/core/redis/stream_manager.py`:
   - Connection management with retry logic
   - Stream creation and consumer groups
   - Event publishing (XADD)
   - Event consumption (XREADGROUP)
   - Replay functionality (XRANGE)

2. Write integration tests in `tests/integration/test_redis_streams.py`

### Step 4: Build Asyncio Event Bus (Subtask 2.3)

1. Create `src/core/eventbus/bus.py`:
   - Priority-based handler registration
   - Separate queues per event type
   - Idempotency checking
   - Circuit breaker pattern
   - Metrics collection

2. Write unit tests in `tests/unit/test_event_bus.py`

### Step 5: Develop Event Processing Pipeline (Subtask 2.4)

1. Create `src/core/pipeline/processor.py`:
   - Bridge between Redis Streams and Event Bus
   - Event transformation and validation
   - Checkpoint management
   - Backpressure handling

2. Write integration tests in `tests/integration/test_event_flow.py`

### Step 6: Implement Monitoring & Replay (Subtask 2.5)

1. Create `src/core/monitoring/monitor.py`:
   - Real-time metrics collection
   - Event replay with speed control
   - Audit trail generation
   - Event flow visualization

2. Write tests in `tests/unit/test_monitoring.py`

## Key Design Decisions

### 1. Event Ordering
- Separate queues per event type ensure FIFO ordering
- Redis Streams maintain order within each stream
- Consumer groups provide horizontal scaling

### 2. Reliability
- At-least-once delivery via explicit acknowledgments
- Idempotency through event ID tracking
- Circuit breakers isolate failing handlers

### 3. Performance
- Target < 100ms event processing latency
- Batch processing for efficiency
- Asyncio for concurrent handler execution

### 4. Scalability
- Multiple consumer instances via Redis consumer groups
- Configurable queue sizes and batch processing
- Resource monitoring and backpressure control

## Testing Strategy

### Unit Tests (Coverage Target: 90%)
- Event validation and serialization
- Event bus handler registration and routing
- Circuit breaker behavior
- Idempotency checking

### Integration Tests
- End-to-end event flow
- Redis connection resilience
- Multi-consumer coordination
- Checkpoint recovery

### Performance Tests
- Throughput: >1000 events/second
- Latency: <100ms p99
- Memory usage under load
- Concurrent handler execution

## Configuration

```yaml
# config/event_engine.yaml
redis:
  url: "redis://localhost:6379"
  max_retries: 3
  retry_delay: 1.0
  stream_max_length: 100000

event_bus:
  max_queue_size: 10000
  idempotency_window: 300
  handler_timeout: 5.0
  circuit_breaker:
    failure_threshold: 5
    reset_time: 60

processor:
  batch_size: 100
  checkpoint_interval: 60
```

## Development Workflow

1. **Start Redis**:
   ```bash
   docker run -d -p 6379:6379 redis:7-alpine
   ```

2. **Run Tests**:
   ```bash
   poetry run pytest tests/unit -v
   poetry run pytest tests/integration -v
   poetry run pytest tests/performance -v --benchmark-only
   ```

3. **Check Coverage**:
   ```bash
   poetry run pytest --cov=src.core --cov-report=html
   ```

4. **Run Linting**:
   ```bash
   poetry run black src tests
   poetry run isort src tests
   poetry run mypy src
   ```

## Monitoring & Debugging

### Key Metrics to Track
- Event processing rate per type
- Queue sizes and backpressure
- Handler execution times
- Circuit breaker states
- Redis connection health

### Debug Commands
```python
# Get event flow metrics
metrics = await monitor.get_event_flow_metrics()

# Replay events for debugging
await monitor.replay_events(
    event_type=EventType.MARKET_DATA,
    start_time=datetime(2024, 1, 1),
    speed_multiplier=10.0
)

# Check handler health
bus_metrics = event_bus.get_metrics()
```

## Next Steps

After completing the event-driven core:

1. **Integration with Data Sources** (Task 4)
   - Connect market data feeds to publish events
   - Implement data validation and normalization

2. **Strategy Framework** (Task 5)
   - Subscribe strategies to market data events
   - Publish signal events from strategies

3. **Risk Management** (Task 8)
   - Subscribe to order and signal events
   - Implement position and risk limit checks

4. **TUI Interface** (Task 7)
   - Subscribe to all event types for display
   - Show real-time event flow metrics

## Success Criteria

- All 5 subtasks completed with tests
- Event processing latency < 100ms
- At-least-once delivery guaranteed
- Horizontal scaling via consumer groups
- Comprehensive monitoring and replay
- 90%+ test coverage
- Production-ready error handling