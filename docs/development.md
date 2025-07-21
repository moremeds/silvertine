# Silvertine Development Guide

This guide covers development workflow, best practices, and contribution guidelines for the Silvertine trading system.

## Development Workflow

### Getting Started

1. **Fork and Clone**
```bash
git clone <your-fork-url>
cd silvertine
git remote add upstream <original-repo-url>
```

2. **Setup Development Environment**
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
make install-dev

# Setup pre-commit hooks
make pre-commit

# Verify setup
make dev-check
```

3. **Configure Development Environment**
```bash
# Copy configuration templates
cp config/environments/development.yaml.example config/environments/development.yaml
cp .env.example .env

# Start Redis for development
redis-server

# Run tests to verify setup
make test
```

### TaskMaster Integration

Silvertine uses TaskMaster for comprehensive project management:

```bash
# View current development priorities
task-master list

# Get next available task
task-master next

# View detailed task information
task-master show <id>

# Update task progress
task-master update-task --id=<id> --prompt="implementation progress"

# Mark subtask status
task-master set-status --id=<id.subtask> --status=done
```

### Development Commands

```bash
# Code quality
make format              # Format code with black and isort
make lint               # Run linting with ruff
make typecheck          # Run mypy type checking

# Testing
make test               # Run all tests
make test-unit          # Run unit tests only
make test-integration   # Run integration tests only
make test-cov           # Run tests with coverage report

# Development
make run                # Start the trading system
make clean              # Clean up build artifacts
```

## Code Standards

### Python Style Guide

**Formatting**: Use Black with 88-character line limit
```bash
black src/ tests/
```

**Import Organization**: Use isort with Black profile
```python
# Standard library imports
import asyncio
import logging
from typing import Dict, List, Optional

# Third-party imports
import redis
from fastapi import FastAPI
from pydantic import BaseModel

# Local imports
from src.core.events import Event
from src.strategies.base import AbstractStrategy
```

**Type Hints**: Mandatory for all public functions
```python
async def process_event(event: Event) -> Optional[Signal]:
    """Process market data event and generate trading signal."""
    pass
```

**Docstrings**: Use Google style docstrings
```python
def calculate_position_size(
    portfolio_value: float,
    risk_percent: float,
    entry_price: float,
    stop_loss: float
) -> float:
    """Calculate position size based on risk management rules.
    
    Args:
        portfolio_value: Total portfolio value in base currency
        risk_percent: Risk percentage (0.02 = 2%)
        entry_price: Intended entry price
        stop_loss: Stop loss price
        
    Returns:
        Position size in base currency
        
    Raises:
        ValueError: If risk parameters are invalid
    """
    pass
```

### Configuration Management

**No Magic Numbers**: All constants must be externalized
```python
# Bad
if price_change > 0.05:  # Magic number
    
# Good
if price_change > config.risk.max_price_change_threshold:
```

**Environment Variables**: Use for sensitive data
```python
# config/environments/development.yaml
database:
  url: "${DATABASE_URL}"  # Injected from environment

# .env file
DATABASE_URL=sqlite:///silver_cache/sqlite/silvertine_dev.db
```

**Validation**: All configuration must be validated at startup
```python
from pydantic import BaseModel, Field

class RiskConfig(BaseModel):
    max_position_percent: float = Field(gt=0, le=100)
    stop_loss_percent: float = Field(gt=0, le=50)
```

## Testing Standards

### Test-Driven Development (TDD)

1. **Write Test First**: Write failing test before implementation
2. **Minimal Implementation**: Write minimal code to make test pass
3. **Refactor**: Improve code while keeping tests green

**Example TDD Cycle**:
```python
# 1. Write failing test
def test_position_size_calculation():
    calculator = PositionSizeCalculator(config)
    size = calculator.calculate(
        portfolio_value=10000,
        risk_percent=0.02,
        entry_price=100,
        stop_loss=95
    )
    assert size == 400.0  # Test fails - function doesn't exist

# 2. Minimal implementation
class PositionSizeCalculator:
    def calculate(self, portfolio_value, risk_percent, entry_price, stop_loss):
        risk_amount = portfolio_value * risk_percent
        price_risk = entry_price - stop_loss
        return risk_amount / price_risk * entry_price

# 3. Refactor and add error handling
```

### Test Organization

**Directory Structure**:
```
tests/
├── unit/                   # Unit tests (fast, isolated)
│   ├── test_events.py
│   ├── test_strategies.py
│   └── test_risk.py
├── integration/            # Integration tests (slower, real dependencies)
│   ├── test_broker_integration.py
│   ├── test_event_flow.py
│   └── test_api_endpoints.py
├── performance/            # Performance benchmarks
│   ├── test_event_latency.py
│   └── test_throughput.py
└── fixtures/               # Test data and mocks
    ├── market_data.json
    └── test_strategies.py
```

**Test Categories**:
```python
import pytest

@pytest.mark.unit
def test_signal_generation():
    """Fast unit test with mocks."""
    pass

@pytest.mark.integration
def test_end_to_end_flow():
    """Integration test with real Redis."""
    pass

@pytest.mark.slow
def test_long_running_operation():
    """Test that takes significant time."""
    pass

@pytest.mark.broker
def test_binance_connection():
    """Test requiring broker connection."""
    pass
```

**Running Tests**:
```bash
# All tests
pytest

# Unit tests only
pytest -m unit

# Skip slow tests
pytest -m "not slow"

# With coverage
pytest --cov=src --cov-report=html
```

### Async Testing

**Use pytest-asyncio** for async test functions:
```python
import pytest

@pytest.mark.asyncio
async def test_async_event_processing():
    event_bus = EventBus()
    event = MarketDataEvent(symbol="BTCUSDT", price=45000)
    
    await event_bus.publish(event)
    received_events = await event_bus.get_events()
    
    assert len(received_events) == 1
    assert received_events[0].symbol == "BTCUSDT"
```

**Mock External Services**:
```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_broker_order_placement():
    with patch('src.brokers.binance.BinanceClient') as mock_client:
        mock_client.return_value.place_order = AsyncMock(return_value="order_123")
        
        broker = BinanceBroker(mock_client.return_value)
        order_id = await broker.place_order(order)
        
        assert order_id == "order_123"
        mock_client.return_value.place_order.assert_called_once()
```

## Architecture Guidelines

### Event-Driven Design

**Event Types**: Use dataclasses for events
```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class MarketDataEvent:
    symbol: str
    price: float
    volume: float
    timestamp: datetime
    bid: Optional[float] = None
    ask: Optional[float] = None
```

**Event Handlers**: Use async functions
```python
async def handle_market_data(event: MarketDataEvent) -> None:
    """Handle incoming market data event."""
    # Update internal state
    # Generate signals if needed
    # Publish new events
    pass
```

**Event Bus**: Central nervous system
```python
class EventBus:
    async def publish(self, event: Event) -> None:
        """Publish event to all subscribers."""
        pass
    
    def subscribe(self, event_type: Type, handler: Callable) -> None:
        """Subscribe to specific event types."""
        pass
```

### Strategy Framework

**Abstract Base Class**:
```python
from abc import ABC, abstractmethod

class AbstractStrategy(ABC):
    @abstractmethod
    async def on_bar(self, bar: MarketData) -> Optional[Signal]:
        """Process new market data bar."""
        pass
    
    @abstractmethod
    async def on_signal(self, signal: Signal) -> Optional[Order]:
        """Convert signal to order."""
        pass
    
    @abstractmethod
    async def on_fill(self, fill: FillEvent) -> None:
        """Handle order execution."""
        pass
```

**Strategy Implementation**:
```python
class MovingAverageCrossover(AbstractStrategy):
    def __init__(self, config: StrategyConfig):
        self.fast_period = config.fast_period
        self.slow_period = config.slow_period
        self.price_history = []
    
    async def on_bar(self, bar: MarketData) -> Optional[Signal]:
        self.price_history.append(bar.close)
        
        if len(self.price_history) < self.slow_period:
            return None
        
        fast_ma = self._calculate_ma(self.fast_period)
        slow_ma = self._calculate_ma(self.slow_period)
        
        if fast_ma > slow_ma:
            return Signal(symbol=bar.symbol, direction="buy", strength=0.8)
        elif fast_ma < slow_ma:
            return Signal(symbol=bar.symbol, direction="sell", strength=0.8)
        
        return None
```

### Error Handling

**Exception Hierarchy**:
```python
class SilvertineError(Exception):
    """Base exception for Silvertine trading system."""
    pass

class BrokerError(SilvertineError):
    """Errors related to broker operations."""
    pass

class RiskError(SilvertineError):
    """Errors related to risk management."""
    pass

class ConfigurationError(SilvertineError):
    """Errors related to configuration."""
    pass
```

**Error Handling Patterns**:
```python
import logging
from typing import Union

logger = logging.getLogger(__name__)

async def safe_broker_operation(operation: Callable) -> Union[Result, Error]:
    """Safely execute broker operation with error handling."""
    try:
        result = await operation()
        return Success(result)
    except BrokerConnectionError as e:
        logger.error(f"Broker connection failed: {e}")
        return ConnectionError(str(e))
    except BrokerOrderError as e:
        logger.warning(f"Order failed: {e}")
        return OrderError(str(e))
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return UnexpectedError(str(e))
```

## Performance Guidelines

### Async Best Practices

**Use asyncio.gather() for concurrent operations**:
```python
async def process_multiple_symbols(symbols: List[str]) -> List[MarketData]:
    tasks = [fetch_market_data(symbol) for symbol in symbols]
    return await asyncio.gather(*tasks)
```

**Avoid blocking operations in async functions**:
```python
# Bad
async def bad_function():
    time.sleep(1)  # Blocks event loop
    
# Good
async def good_function():
    await asyncio.sleep(1)  # Non-blocking
```

**Use connection pooling**:
```python
class BrokerClient:
    def __init__(self):
        self._session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=100)
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._session.close()
```

### Memory Management

**Use circular buffers for time series data**:
```python
from collections import deque

class PriceBuffer:
    def __init__(self, maxlen: int):
        self._buffer = deque(maxlen=maxlen)
    
    def append(self, price: float) -> None:
        self._buffer.append(price)
    
    def get_recent(self, n: int) -> List[float]:
        return list(self._buffer)[-n:]
```

**Implement data retention policies**:
```python
async def cleanup_old_data():
    """Remove data older than retention period."""
    cutoff_date = datetime.now() - timedelta(days=30)
    await database.delete_market_data(before=cutoff_date)
```

## Git Workflow

### Branch Strategy

**Main Branches**:
- `main`: Production-ready code
- `develop`: Integration branch for features

**Feature Branches**:
- `feature/task-<number>-description`: New features
- `bugfix/issue-description`: Bug fixes
- `hotfix/critical-issue`: Critical production fixes

### Commit Guidelines

**Conventional Commits**:
```bash
# Feature commits
feat(core): add event bus implementation
feat(strategy): implement moving average crossover

# Bug fixes
fix(broker): handle connection timeout properly
fix(risk): correct position size calculation

# Documentation
docs(api): update REST endpoint documentation
docs(readme): add installation instructions

# Refactoring
refactor(events): simplify event handler registration
refactor(config): improve configuration validation

# Tests
test(unit): add tests for risk management
test(integration): add broker connection tests
```

**Commit Message Format**:
```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Pull Request Process

1. **Create Feature Branch**:
```bash
git checkout -b feature/task-2-event-core
```

2. **Make Changes and Commit**:
```bash
git add .
git commit -m "feat(core): implement Redis Streams event bus"
```

3. **Update Task Progress**:
```bash
task-master update-task --id=2 --prompt="Implemented Redis Streams event bus with persistence and replay capability"
```

4. **Push and Create PR**:
```bash
git push origin feature/task-2-event-core
# Create pull request through GitHub/GitLab
```

5. **PR Requirements**:
- All tests passing
- Code coverage ≥75%
- No linting or type errors
- Updated documentation if needed
- TaskMaster progress updated

## Debugging and Profiling

### Logging

**Configure structured logging**:
```python
import structlog

logger = structlog.get_logger()

async def process_order(order: Order):
    logger.info(
        "Processing order",
        order_id=order.id,
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity
    )
```

**Log Levels**:
- `DEBUG`: Detailed debugging information
- `INFO`: General system information
- `WARNING`: Warning conditions
- `ERROR`: Error conditions
- `CRITICAL`: Critical system failures

### Performance Profiling

**Profile async code**:
```python
import cProfile
import asyncio

async def main():
    # Your async code here
    pass

if __name__ == "__main__":
    cProfile.run('asyncio.run(main())')
```

**Memory profiling**:
```python
from memory_profiler import profile

@profile
def memory_intensive_function():
    # Function to profile
    pass
```

## Contributing Guidelines

1. **Check Existing Issues**: Look for existing issues or create new ones
2. **Follow TaskMaster**: Use TaskMaster for task tracking and progress
3. **Write Tests**: Maintain 75% test coverage minimum
4. **Documentation**: Update documentation for public APIs
5. **Code Review**: Address all review comments promptly
6. **Performance**: Consider performance impact of changes

## See Also

- [Architecture Documentation](architecture.md) - System architecture overview
- [API Documentation](api.md) - REST API and WebSocket endpoints
- [Deployment Guide](deployment.md) - Production deployment instructions