# Silvertine

**A lightweight, event-driven quantitative trading and backtesting system**

Silvertine is designed for medium-to-low frequency trading strategies, built for individual traders and small teams who need professional-grade capabilities with an emphasis on simplicity, reliability, and real-time performance.

## Features

### Core Capabilities
- **Event-Driven Architecture**: High-performance asyncio-based event bus for real-time operation
- **Multi-Exchange Support**: Integrated support for Binance testnet and Interactive Brokers paper trading
- **Rich TUI Interface**: Live monitoring and control using Rich library for sophisticated terminal interface
- **Paper Trading**: Realistic order simulation with slippage modeling and market impact
- **Extensible Strategy Framework**: Modular design for easy strategy development and testing

### Technical Features
- **Redis Streams Integration**: Event persistence and replay capability for system recovery
- **Configuration-Driven**: All parameters externalized with no magic numbers in code
- **Comprehensive Testing**: 75% test coverage target with TDD methodology
- **Performance Optimized**: Sub-100ms event processing, <500ms order execution
- **Security by Design**: JWT authentication, TLS encryption, audit logging

## Technology Stack

### Core Infrastructure
- **Runtime**: Python 3.11+ with asyncio for high-performance concurrency
- **Event System**: Redis Streams for event persistence and replay capability
- **Caching**: Redis for market data caching and session management
- **Database**: SQLite for trade history and configuration storage

### User Interface & API
- **TUI**: Rich library for sophisticated terminal interface with advanced text rendering
- **Web Interface**: FastAPI backend with React frontend for browser access
- **API**: FastAPI with WebSocket support for real-time updates
- **Authentication**: JWT-based API authentication system

### Data & Integration
- **Market Data**: WebSocket connections for real-time feeds
- **Brokers**: Binance and Interactive Brokers paper trading
- **Monitoring**: Prometheus metrics with Grafana dashboards

### Deployment & Operations
- **Containerization**: Docker for consistent deployment environments
- **CI/CD**: Automated testing and deployment pipelines
- **Security**: TLS encryption, rate limiting, audit logging

## Quick Start

### Prerequisites
- Python 3.11 or higher
- Redis server
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd silvertine
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies using Poetry**
   ```bash
   # Install Poetry (if not already installed)
   curl -sSL https://install.python-poetry.org | python3 -
   
   # Install project dependencies
   poetry install
   
   # Activate virtual environment
   poetry shell
   ```

4. **Set up configuration**
   ```bash
   # Copy example configurations
   cp config/environments/development.yaml.example config/environments/development.yaml
   cp config/exchanges/binance_testnet.yaml.example config/exchanges/binance_testnet.yaml
   cp .env.example .env
   
   # Edit configuration files with your settings
   # Add API keys to .env file
   ```

5. **Initialize the system**
   ```bash
   # Start Redis (if not running)
   redis-server
   
   # Run initial setup
   python -m src.main --setup
   ```

### Basic Usage

1. **Start the trading system**
   ```bash
   python -m src.main
   ```

2. **TUI Interface Controls**
   - `s`: Start trading system
   - `p`: Pause/resume trading
   - `r`: Restart connections
   - `Ctrl+C`: Emergency stop and exit
   - `Tab`: Navigate between panels

3. **Run tests**
   ```bash
   make test
   # or
   pytest tests/
   ```

## Project Structure

**Interface-First Architecture**: Each module defines abstract interfaces at the root level with concrete implementations in subdirectories.

```
silvertine/
├── src/                        # Core application code
│   ├── core/                   # Core engine and event system
│   │   ├── events.py           # Event base classes and types
│   │   ├── event_bus.py        # Asyncio event bus implementation
│   │   └── engine.py           # Main trading engine
│   ├── exchanges/              # Exchange integrations
│   │   ├── ibroker.py          # AbstractBroker interface
│   │   ├── binance/            # Binance implementation
│   │   │   ├── binance_client.py
│   │   │   └── binance_broker.py
│   │   ├── ib/                 # Interactive Brokers implementation
│   │   │   ├── ib_client.py
│   │   │   └── ib_broker.py
│   │   └── paper/              # Paper trading implementation
│   │       └── paper_broker.py
│   ├── data/                   # Data aggregation system
│   │   ├── idata_source.py     # AbstractDataSource interface
│   │   ├── sources/            # Data source implementations
│   │   │   ├── binance_data_source.py
│   │   │   └── ib_data_source.py
│   │   ├── cache.py            # Redis caching layer
│   │   └── aggregator.py       # Multi-source aggregation
│   ├── strategies/             # Trading strategies
│   │   ├── istrategy.py        # AbstractStrategy interface
│   │   ├── moving_average/     # Moving average strategy
│   │   │   └── moving_average_strategy.py
│   │   └── utils/              # Strategy utilities
│   ├── risk/                   # Risk management system
│   │   ├── irisk_manager.py    # Risk management interfaces
│   │   ├── position_limits.py  # Position size controls
│   │   └── portfolio.py        # Portfolio risk monitoring
│   ├── ui/                     # User interfaces
│   │   ├── tui/                # Terminal UI (Rich library)
│   │   └── web/                # Web UI (FastAPI + React)
│   └── api/                    # REST API endpoints
├── tests/                      # Test suite
│   ├── unit/                   # Unit tests (fast, isolated)
│   ├── integration/            # Integration tests (real dependencies)
│   ├── performance/            # Performance benchmarks
│   └── fixtures/               # Test data and mocks
├── config/                     # Configuration management
│   ├── settings.py             # Main configuration module
│   ├── environments/           # Environment-specific settings
│   ├── exchanges/              # Exchange API configurations
│   ├── strategies/             # Strategy parameters
│   ├── risk/                   # Risk management settings
│   └── logging/                # Logging configuration
├── cache/                      # Runtime data (gitignored)
│   ├── sqlite/                 # SQLite databases
│   ├── logs/                   # Application logs
│   ├── progress/               # Session progress tracking
│   └── temp/                   # Temporary files
└── docs/                       # Project documentation
    ├── architecture.md         # System architecture
    ├── api.md                  # API documentation
    ├── development.md          # Development guide
    └── deployment.md           # Deployment instructions
```

## Development Workflow

### TaskMaster Integration
This project uses TaskMaster for comprehensive project management:

```bash
# View current tasks
task-master list

# Get next available task
task-master next

# View detailed task information
task-master show <id>

# Update task progress
task-master update-task --id=<id> --prompt="progress notes"
```

### Progress Tracking & Session Recovery
Silvertine includes an intelligent progress tracking system for session continuity:

**Resume Sessions**: When returning to work, simply say "resume" to Claude Code to get:
- Current session state and completed tasks
- Key architectural decisions made
- Files modified and context
- Next immediate tasks to work on

**Automatic Cleanup**: Progress files are automatically managed:
- Session progress cleaned after 2 days
- Automatic cleanup on git commits
- Manual cleanup with "cleanup progress" command
- Important snapshots preserved for 7 days

**Progress Structure**:
```bash
cache/progress/
├── session_progress.json      # Current session state
├── task_snapshots/           # Major milestone snapshots
└── recovery/                 # Quick recovery information
```

### Development Commands
```bash
# Code formatting and linting
make format              # Format code with black
make lint               # Run linting with ruff
make typecheck          # Run mypy type checking

# Testing
make test               # Run test suite
make test-cov           # Run tests with coverage
make test-integration   # Run integration tests

# Development setup (using Poetry)
poetry install          # Install dependencies
poetry install --with dev  # Install with development dependencies
make pre-commit         # Install pre-commit hooks

# Session management
# Say "resume" to Claude Code to restore session context
# Say "cleanup progress" to clean old progress files
```

### Configuration Management
- All configuration files are stored in the `config/` directory
- Use `.example` files as templates for your configurations
- Never commit sensitive credentials - use environment variables
- All parameters must be externalized (no magic numbers in code)

## Performance Requirements

- **Latency**: Event processing < 100ms, order execution < 500ms
- **Throughput**: 1000+ events/second minimum
- **Stability**: 24-hour continuous operation capability
- **Memory**: < 1GB for MVP system

## Security

- **API Authentication**: JWT-based authentication system
- **Encryption**: TLS 1.3 for all external communications
- **Audit Logging**: Comprehensive logging of all trading activities
- **Secret Management**: Environment variable injection for sensitive data
- **Rate Limiting**: Built-in protection against API abuse

## Documentation

For detailed documentation, see the `/docs` directory:

- [Architecture Guide](docs/architecture.md) - System design and components
- [API Documentation](docs/api.md) - REST API and WebSocket endpoints
- [Deployment Guide](docs/deployment.md) - Production deployment instructions
- [Development Guide](docs/development.md) - Development workflow and best practices

## Contributing

1. **Follow Interface-First Architecture**: Define abstract interfaces at module root using `i` prefix (e.g., `ibroker.py`)
2. **Use Descriptive Naming**: Avoid generic names like `broker.py`, use specific names like `binance_broker.py`
3. **TaskMaster Integration**: Follow the development workflow using TaskMaster for task management
4. **Test Organization**: Place unit tests in `tests/unit/`, integration tests in `tests/integration/`
5. **TDD Methodology**: Write tests before implementation, maintain 75% test coverage
6. **Configuration Management**: All settings externalized to `config/` directory with `.example` templates
7. **Poetry Usage**: Use Poetry for dependency management, avoid pip/requirements.txt
8. **Progress Tracking**: Use session tracking system for complex development sessions
9. **Code Standards**: Follow established coding standards enforced by pre-commit hooks

## License

[License information to be added]

## Support

For issues and questions:
- Check the documentation in `/docs`
- Review current tasks with `task-master list`
- Create GitHub issues for bugs or feature requests