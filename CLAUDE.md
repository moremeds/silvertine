# Silvertine - Claude Code Instructions

**AI Assistant Instructions for the Silvertine Quantitative Trading System**

This document provides comprehensive guidance for Claude Code when working with the Silvertine codebase, ensuring consistent development practices and architectural alignment.

## Project Overview

**Silvertine** is a lightweight, event-driven quantitative trading and backtesting system designed for medium-to-low frequency trading strategies. Built for individual traders and small teams, it emphasizes simplicity, reliability, and real-time performance.

### Core Features
- **Event-driven architecture** with asyncio-based event bus for high-performance operation
- **Multi-exchange support** (Binance testnet + Interactive Brokers paper trading)
- **Real-time TUI interface** using Rich library for live monitoring and control
- **Paper trading** with realistic order simulation and slippage modeling
- **Extensible strategy framework** with moving average crossover as reference implementation

## Architecture Principles

### Event-Driven Core
The system uses a publish-subscribe event bus with four core event types:
- `MarketDataEvent`: Real-time price updates
- `OrderEvent`: Order creation/modification requests  
- `FillEvent`: Order execution confirmations
- `SignalEvent`: Strategy-generated trading signals

### Component Structure
```
Data Engine → Event Bus → Trading Engine
     ↓            ↓            ↓
Market Data → Strategy Engine → Risk Engine
     ↓            ↓            ↓
    TUI ← Real-time Updates ← Position Tracking
```

### Technology Stack
**Core Infrastructure**:
- **Runtime**: Python 3.11+ with asyncio for high-performance concurrency
- **Event System**: Redis Streams for event persistence and replay capability
- **Caching**: Redis for market data caching and session management
- **Database**: SQLite for trade history and configuration storage

**User Interface & API**:
- **TUI**: Rich library for sophisticated terminal interface with advanced text rendering
- **Web Interface**: FastAPI backend with React frontend for browser access
- **API**: FastAPI with WebSocket support for real-time updates
- **Authentication**: JWT-based API authentication system

**Data & Integration**:
- **Market Data**: WebSocket connections for real-time feeds
- **Brokers**: Binance testnet and Interactive Brokers paper trading
- **Monitoring**: Prometheus metrics with Grafana dashboards

**Deployment & Operations**:
- **Containerization**: Docker for consistent deployment environments
- **CI/CD**: Automated testing and deployment pipelines
- **Security**: TLS encryption, rate limiting, audit logging

## TaskMaster Integration

This project uses TaskMaster for project management:

### Key TaskMaster Commands
```bash
# Project Setup
task-master init                                    # Initialize Task Master in current project
task-master parse-prd .taskmaster/docs/prd.txt      # Generate tasks from PRD document
task-master models --setup                        # Configure AI models interactively

# Daily Development Workflow
task-master list                                   # Show all tasks with status
task-master next                                   # Get next available task to work on
task-master show <id>                             # View detailed task information (e.g., task-master show 1.2)
task-master set-status --id=<id> --status=done    # Mark task complete

# Task Management
task-master add-task --prompt="description" --research        # Add new task with AI assistance
task-master expand --id=<id> --research --force              # Break task into subtasks
task-master update-task --id=<id> --prompt="changes"         # Update specific task
task-master update --from=<id> --prompt="changes"            # Update multiple tasks from ID onwards
task-master update-subtask --id=<id> --prompt="notes"        # Add implementation notes to subtask

# Analysis & Planning
task-master analyze-complexity --research          # Analyze task complexity
task-master complexity-report                      # View complexity analysis
task-master expand --all --research               # Expand all eligible tasks

# Dependencies & Organization
task-master add-dependency --id=<id> --depends-on=<id>       # Add task dependency
task-master move --from=<id> --to=<id>                       # Reorganize task hierarchy
task-master validate-dependencies                            # Check for dependency issues
task-master generate                                         # Update task markdown files (usually auto-called)
```

### Project Structure in TaskMaster
Current tasks are stored in `.taskmaster/tasks/tasks.json` with the following comprehensive task structure:

**Core Infrastructure (Tasks 1-4)**:
- **Task 1**: Setup Project Repository
- **Task 2**: Implement Event-Driven Core Engine (with Redis Streams)
- **Task 3**: Create Modular Broker Interface
- **Task 4**: Build Multi-Source Data Aggregation System

**Trading System (Tasks 5-8)**:
- **Task 5**: Develop Strategy Development Framework
- **Task 6**: Implement High-Precision Backtesting Engine
- **Task 7**: Develop TUI Interface with Rich Library
- **Task 8**: Create Risk Management System

**Integration & Operations (Tasks 9-15)**:
- **Task 9**: Implement RESTful API Design
- **Task 10**: Conduct Performance Testing and Optimization
- **Task 11**: Establish Comprehensive Testing Infrastructure (TDD with 75% coverage)
- **Task 12**: Deployment and Infrastructure Automation (Docker, CI/CD, Monitoring)
- **Task 13**: Implement Security and Compliance Infrastructure (JWT, encryption, audit)
- **Task 14**: Configuration Management System
- **Task 15**: Create Web-Based User Interface

**Historical Detailed Tasks**: The original detailed project breakdown with 15 tasks and 67 subtasks (101-304 numbering) is preserved in `scrapyard/tasks.json` for reference, including:
- **Pre-MVP Phase**: Technical validation (tasks 101-107)
- **TUI MVP Phase**: Core implementation (tasks 201-209)  
- **Exchange Connectivity**: Live trading integration (tasks 301-304)

**Archive Management**: Deprecated tasks and obsolete code are moved to `scrapyard/` for reference. 

## Development Workflow

### Current Phase: Core Development
**Active Development**: Reference current tasks from `.taskmaster/tasks/tasks.json` and individual `tasks/task_{id}.txt` files for detailed development priorities and status.

**Development Principles**:
- Test-driven development (TDD) with tests written before implementation
- Continuous integration mindset with frequent validation
- Clean architecture with clear separation of concerns
- Performance-first design with latency optimization

### Performance Requirements
- **Latency**: Event processing < 100ms, order execution < 500ms
- **Throughput**: 1000 events/second minimum
- **Stability**: 24-hour continuous operation without intervention
- **Memory**: < 1GB for MVP system

### Testing Strategy
**Multi-layered testing approach following TDD principles:**

- **Unit Tests**: Individual component validation with 75% target coverage
  - Write tests first before implementation
  - Mock/simulated data permitted with API specification alignment
  - Focus on edge cases and error conditions
  
- **Integration Tests**: Component interaction verification
  - Use real data sources (no mocked data)
  - Test event bus message flow
  - Validate broker interface compatibility
  - **Mandatory Logging**: All integration test runs logged to `cache/logs/integration_tests/`
  - **Log Format**: Structured JSON logs with timestamps, test results, and system state
  
- **Stability Tests**: Extended runtime validation (8-24 hours)
  - Memory leak detection
  - Connection recovery testing
  - Error handling under load
  
- **Performance Tests**: Latency and throughput benchmarks
  - Event processing timing
  - Order execution latency
  - System resource utilization

### Data Management Rules
**Strict separation of code, configuration, and runtime data:**

- **Configuration Location**: All configuration files must be stored in the `config/` directory
  - Environment-specific settings → `config/environments/`
  - Exchange API configurations → `config/exchanges/`
  - Strategy parameters → `config/strategies/`
  - Risk management settings → `config/risk/`
  - Logging configuration → `config/logging/`
  - Database connections → `config/database/`
  - Security and authentication → `config/security/`

- **Output Location**: All generated files must be stored in the `cache/` directory
  - SQLite databases and cached market data → `cache/sqlite/`
  - Application and trading logs → `cache/logs/`
  - Temporary files and working data → `cache/temp/`
  - Redis data persistence → `cache/redis/`
  
- **Configuration Management**: 
  - **No Magic Numbers**: All constants, thresholds, and parameters must be externalized to configuration files
  - **Environment Variables**: Support environment variable injection for sensitive data
  - **Validation**: All configuration must be validated at startup with clear error messages
  - **Templates**: Provide `.example` files for all sensitive configurations
  
- **Version Control**: Runtime-generated files must NOT be committed to the repository
  - Ensure `cache/` directory is properly excluded in `.gitignore`
  - Include `config/` templates but exclude sensitive credential files
  - Only source code and configuration templates are version controlled
  
- **File Naming**: Use ISO timestamps and descriptive names for log files
  - Example: `cache/logs/trading_2024-01-15_14-30-00.log`
  
- **Data Retention**: Implement automated cleanup policies
  - Market data: 30-day rolling window
  - Trade history: Permanent storage with compression
  - System logs: 7-day rotation with archive compression

### Progress Tracking System

**Session Recovery and Task Continuity**: To handle interruptions during complex development sessions, all task progress is automatically tracked in the cache directory.

**Progress Tracking Structure**:
```
cache/progress/
├── session_progress.json          # Current session state and task progress
├── task_snapshots/               # Snapshots at key milestones
│   ├── 2025-01-20_architecture_update.json
│   └── 2025-01-20_naming_conventions.json
└── recovery/                     # Quick recovery information
    ├── last_session.json
    └── context_notes.md
```

**Automatic Progress Tracking**:
- **Session State**: Current task, completed tasks, pending items
- **File Modifications**: Track which files were changed and why
- **Key Decisions**: Record architectural decisions and reasoning
- **Context Preservation**: Maintain session context for seamless resumption
- **Milestone Snapshots**: Automatic snapshots at major completion points

**Recovery Workflow**:
1. **Check Progress**: Read `cache/progress/session_progress.json` for current state
2. **Review Context**: Check `context_notes.md` for session background
3. **Validate Changes**: Verify completed tasks against file modifications
4. **Resume Work**: Continue from the exact point of interruption

**Progress Management Commands**:

**Resume Session**: When user says "resume" - Display current progress and provide context for continuation
```bash
# Claude Code will automatically:
# 1. Check cache/progress/session_progress.json for current state
# 2. Display completed tasks and current position
# 3. Show key decisions and context from last session
# 4. Identify next immediate tasks
# 5. Validate file modifications against progress records
```

**Cleanup Progress**: When user says "cleanup progress" - Remove old progress files
```bash
# Claude Code will automatically:
# 1. Remove session files older than 2 days
# 2. Clean task snapshots beyond retention policy (7 days, max 10 files)
# 3. Preserve important recovery files (last session summary)
# 4. Update progress_config.json with cleanup timestamp
```

**Automatic Cleanup Triggers**:
- **Age-based**: Progress files older than 2 days (configurable)
- **Git Commit**: When code is committed, cleanup session progress
- **Manual**: User command "cleanup progress"
- **Count-based**: Keep maximum 10 task snapshots, remove oldest

**Manual Progress Commands**:
```bash
# Check current progress
cat cache/progress/session_progress.json | jq '.current_task'

# View completed tasks
cat cache/progress/session_progress.json | jq '.completed_tasks'

# Check key decisions made
cat cache/progress/session_progress.json | jq '.context.key_decisions'

# View retention policy
cat cache/progress/progress_config.json | jq '.retention_policy'
```

**Progress File Format**:
```json
{
  "session_id": "claude_code_2025_01_20",
  "last_updated": "2025-01-20T15:30:00Z",
  "current_task": "Task description",
  "completed_tasks": [...],
  "pending_tasks": [...],
  "context": {
    "files_modified": [...],
    "key_decisions": [...],
    "next_steps": [...]
  }
}
```

## Key Design Patterns

### Strategy Pattern (AbstractStrategy)
**Purpose**: Modular, swappable trading algorithms with consistent interface

```python
class AbstractStrategy:
    async def on_bar(self, bar: MarketData) -> Optional[Signal]:
        """Process new market data bar and generate trading signals"""
        pass
    
    async def on_signal(self, signal: Signal) -> Optional[Order]:
        """Convert trading signal to executable order"""
        pass
    
    async def on_fill(self, fill: FillEvent) -> None:
        """Handle order execution updates"""
        pass
```

### Broker Pattern (AbstractBroker)
**Purpose**: Unified interface for different exchanges and brokers

```python
class AbstractBroker:
    async def place_order(self, order: Order) -> str:
        """Place order, return order ID"""
        pass
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel existing order"""
        pass
    
    async def get_positions(self) -> List[Position]:
        """Get current positions"""
        pass
    
    async def get_account_info(self) -> AccountInfo:
        """Get account balance and status"""
        pass
```

### Observer Pattern (Event Bus)
**Purpose**: Loose coupling between components through event-driven communication

```python
class EventBus:
    async def publish(self, event: Event) -> None:
        """Publish event to all subscribers"""
        pass
    
    def subscribe(self, event_type: Type, handler: Callable) -> None:
        """Subscribe to specific event types"""
        pass
```

## Exchange Configuration

### Binance Testnet
**Development Environment**: Safe testing with simulated trading

- **Configuration Location**: `config/exchanges/binance_testnet.yaml`
- **Features**: WebSocket market data, REST API trading, order book data
- **Rate Limits**: All limits configured in `config/exchanges/` (no hardcoded values)
- **Authentication**: Environment variable injection for credentials
  - Template: `config/exchanges/binance_testnet.yaml.example`
  - Credentials: `BINANCE_TESTNET_API_KEY`, `BINANCE_TESTNET_SECRET_KEY`

### Interactive Brokers
**Paper Trading Environment**: Professional-grade simulation

- **Configuration Location**: `config/exchanges/interactive_brokers.yaml`
- **Connection**: IB Gateway or TWS application (configured in exchange config)
- **Features**: Real-time market data subscription, order routing, portfolio tracking
- **Authentication**: All connection parameters externalized to configuration
  - Template: `config/exchanges/interactive_brokers.yaml.example`
- **API**: Interactive Brokers Python API (ib_insync recommended)

## Risk Management

### Risk Controls
**Multi-layered risk protection system with externalized configuration:**

- **Configuration Location**: `config/risk/risk_management.yaml`
- **Position Limits**: All size limits per strategy and asset externalized (no magic numbers)
- **Stop Orders**: Stop-loss and take-profit thresholds configured in `config/risk/`
- **Drawdown Monitoring**: Maximum drawdown thresholds and alert levels in configuration
- **Emergency Controls**: Immediate stop functionality accessible via TUI (`Ctrl+C`)
- **Portfolio Exposure**: Risk exposure limits defined in `config/risk/portfolio.yaml`
- **Leverage Limits**: All leverage constraints externalized to configuration files

### Performance Metrics
**Real-time performance tracking with configurable thresholds:**

- **Configuration Location**: `config/monitoring/performance.yaml`
- **P&L Calculation**: Real-time profit and loss across all positions
- **Risk Metrics**: VaR, Sharpe ratio, maximum drawdown (all thresholds in config)
- **Exposure Monitoring**: Current market exposure by asset and strategy
- **Performance Alerts**: All alert thresholds externalized to `config/monitoring/alerts.yaml`
- **Trade Analytics**: Win rate, holding time, profit factor metrics (no hardcoded values)

## TUI Interface Layout

### Dashboard Panels
**Real-time monitoring interface with Textual framework:**

- **Market Data Panel**: 
  - Real-time price feeds for active symbols
  - Ability to add custom tickers for tracking
  - Direct order placement interface
  - Order book depth visualization
  
- **Positions Panel**: 
  - Current holdings with real-time P&L
  - Position size and market value
  - Unrealized gains/losses
  
- **Strategy Panel**: 
  - Active strategies and their status
  - Recent signals and execution status
  - Strategy-specific metrics
  
- **System Logs Panel**: 
  - Event processing messages
  - Error handling and warnings
  - Performance metrics updates
  
- **Control Panel**: 
  - System start/stop controls
  - Emergency stop functionality
  - Connection status indicators

### Keyboard Shortcuts
**Quick access controls for trading operations:**

- `Ctrl+C`: Emergency stop all trading and exit
- `s`: Start trading system
- `q`: Quit application gracefully
- `r`: Restart exchange connections
- `p`: Pause/resume trading
- `Tab`: Navigate between panels
- `Enter`: Activate selected control

## Project Status & Task Management

### TaskMaster Workflow
**Comprehensive project tracking using TaskMaster AI:**

- **Primary Tracker**: Use TaskMaster as the authoritative task management system
- **Progress Updates**: Always update task information and progress details
- **Completion Protocol**: Never mark tasks as completed without explicit instruction
- **Documentation**: Maintain detailed implementation notes in subtasks

### Current Development Status
**Comprehensive 15-task roadmap tracked in `.taskmaster/tasks/tasks.json` and individual `task_{id}.txt` files:**

**Phase 1: Core Infrastructure (Tasks 1-4)**
- Repository setup, event-driven engine with Redis Streams
- Modular broker interface and multi-source data aggregation

**Phase 2: Trading Capabilities (Tasks 5-8)**  
- Strategy framework, backtesting engine, TUI interface with Rich library, risk management

**Phase 3: Integration & Production (Tasks 9-15)**
- RESTful API, performance optimization, comprehensive testing
- Security infrastructure, deployment automation, configuration management
- Web-based user interface for browser access

### Historical Reference
**Detailed task breakdown preserved in `scrapyard/tasks.json`:**

- **Pre-MVP Phase**: Technical validation (tasks 101-107) - 2 weeks
- **TUI MVP Phase**: Core implementation (tasks 201-209) - 3-4 weeks  
- **Exchange Connectivity**: Live trading integration (tasks 301-304) - 1 week

### Development Guidelines
**Best practices for AI-assisted development:**

- Use TaskMaster commands to view current priorities and dependencies
- Update task progress with implementation details and architectural decisions
- Follow TDD methodology with comprehensive test coverage (75% target)
- Maintain clean separation between source code, configuration, and runtime data
- **Configuration Management**: All settings must be externalized to `config/` directory with no magic numbers in code
- **Environment Variables**: Support environment variable injection for all sensitive configurations
- **Configuration Validation**: Validate all configuration at startup with descriptive error messages
- **Dependency Management**: Use Poetry exclusively for all dependency and environment management
- **Integration Testing**: Always log comprehensive test execution details to `cache/logs/integration_tests/`
- Prioritize performance (sub-100ms event processing) and reliability
- Implement security by design with encryption and audit logging
- Use Redis Streams for event persistence and replay capability
- Design for horizontal scaling and monitoring with Prometheus/Grafana

---

## Important Instructions

**Development Constraints:**
- Do only what has been explicitly requested
- NEVER create files unless absolutely necessary
- ALWAYS prefer editing existing files over creating new ones
- NEVER proactively create documentation files unless explicitly requested
- NEVER use emojis in any code, documentation, or output
- Focus on achieving the specific goal with minimal file creation

## Dependency Management

**Use Poetry for all dependency and project management:**
- **Primary Tool**: Poetry manages all dependencies, virtual environments, and project lifecycle
- **Installation**: `poetry install` to install all dependencies and create virtual environment
- **Adding Dependencies**: 
  - Production: `poetry add <package>`
  - Development: `poetry add --group dev <package>`
  - Broker-specific: `poetry add --group brokers <package>`
  - Monitoring: `poetry add --group monitoring <package>`
- **Activation**: `poetry shell` to activate virtual environment
- **Execution**: `poetry run <command>` to run commands in poetry environment
- **Lock File**: `poetry.lock` ensures reproducible builds across environments
- **NEVER use pip or requirements.txt** - Poetry manages everything through pyproject.toml

## Integration Testing Requirements

**Comprehensive logging for integration tests:**
- **Test Execution Logs**: All integration test runs must be logged to `cache/logs/integration_tests/`
- **Log File Format**: `integration_test_YYYY-MM-DD_HH-MM-SS.log`
- **Required Log Content**:
  - Test execution start/end timestamps
  - Individual test case results (pass/fail/skip)
  - Error messages and stack traces for failures
  - External service connection attempts (Redis, brokers, databases)
  - Performance metrics (execution time, resource usage)
  - System state before and after test execution
- **Log Retention**: Keep integration test logs for 30 days minimum
- **Real-time Logging**: Stream logs to console during test execution for immediate feedback
- **Structured Logging**: Use JSON format for easy parsing and analysis

## Project Structure Reference

The following is the recommended directory structure following interface-first architecture principles:

```
/home/ubuntu/projects/silvertine/
├── .gitignore
├── Makefile
├── pyproject.toml
├── README.md
├── requirements.txt
├── requirements-dev.txt
|
├── config/                     # Configuration management
│   ├── __init__.py
│   ├── settings.py             # Main configuration module
│   ├── environments/           # Environment-specific settings
│   │   ├── development.yaml.example
│   │   ├── production.yaml.example
│   │   └── testing.yaml.example
│   ├── exchanges/              # Exchange API configurations
│   │   ├── binance_testnet.yaml.example
│   │   └── interactive_brokers.yaml.example
│   ├── strategies/             # Strategy parameters
│   │   └── moving_average.yaml.example
│   ├── risk/                   # Risk management settings
│   │   ├── risk_management.yaml.example
│   │   └── portfolio.yaml.example
│   └── logging/                # Logging configuration
│       └── logging.yaml
|
├── cache/                      # Runtime data (gitignored)
│   ├── sqlite/                 # SQLite databases
│   ├── logs/                   # Application logs
│   │   └── integration_tests/  # Integration test logs
│   ├── temp/                   # Temporary files
│   └── redis/                  # Redis persistence
|
├── docs/                       # Project documentation
│   ├── api.md                  # API documentation
│   ├── architecture.md         # System architecture
│   ├── development.md          # Development guide
│   └── deployment.md           # Deployment instructions
|
├── notebooks/                  # Research and analysis
│   ├── data_analysis.ipynb
│   └── strategy_backtesting.ipynb
|
├── scripts/                    # Utility scripts
│   ├── data_downloader.py
│   └── run_backtest.py
|
├── src/                        # Core application code
│   ├── __init__.py
│   │
│   ├── core/                   # Core engine and event system
│   │   ├── __init__.py
│   │   ├── events.py           # Event base classes and types
│   │   ├── event_bus.py        # Asyncio event bus implementation
│   │   └── engine.py           # Main trading engine
│   │
│   ├── exchanges/              # Exchange integrations
│   │   ├── __init__.py
│   │   ├── ibroker.py          # AbstractBroker interface
│   │   ├── binance/            # Binance implementation
│   │   │   ├── __init__.py
│   │   │   ├── binance_client.py
│   │   │   └── binance_broker.py
│   │   ├── ib/                 # Interactive Brokers implementation
│   │   │   ├── __init__.py
│   │   │   ├── ib_client.py
│   │   │   └── ib_broker.py
│   │   ├── oke/                # OKEx implementation (future)
│   │   │   ├── __init__.py
│   │   │   ├── oke_client.py
│   │   │   └── oke_broker.py
│   │   └── paper/              # Paper trading implementation
│   │       ├── __init__.py
│   │       └── paper_broker.py
│   │
│   ├── data/                   # Data aggregation system
│   │   ├── __init__.py
│   │   ├── idata_source.py     # AbstractDataSource interface
│   │   ├── sources/            # Data source implementations
│   │   │   ├── __init__.py
│   │   │   ├── binance_data_source.py
│   │   │   ├── ib_data_source.py
│   │   │   └── oke_data_source.py
│   │   ├── cache.py            # Redis caching layer
│   │   ├── quality.py          # Data quality validation
│   │   └── aggregator.py       # Multi-source aggregation
│   │
│   │
│   ├── strategies/             # Trading strategies
│   │   ├── __init__.py
│   │   ├── istrategy.py        # AbstractStrategy interface
│   │   ├── moving_average/     # Moving average strategy
│   │   │   ├── __init__.py
│   │   │   └── moving_average_strategy.py
│   │   └── utils/              # Strategy utilities
│   │       ├── __init__.py
│   │       ├── indicators.py
│   │       └── signals.py
│   │
│   ├── risk/                   # Risk management system
│   │   ├── __init__.py
│   │   ├── irisk_manager.py    # Risk management interfaces
│   │   ├── position_limits.py  # Position size controls
│   │   ├── stop_loss.py        # Stop-loss mechanisms
│   │   └── portfolio.py        # Portfolio risk monitoring
│   │
│   ├── backtesting/            # Backtesting engine
│   │   ├── __init__.py
│   │   ├── engine.py           # Backtesting engine
│   │   ├── cost_model.py       # Transaction cost modeling
│   │   └── performance.py      # Performance analytics
│   │
│   ├── ui/                     # User interfaces
│   │   ├── __init__.py
│   │   ├── tui/                # Terminal UI (Rich library)
│   │   │   ├── __init__.py
│   │   │   ├── dashboard.py
│   │   │   └── components/
│   │   └── web/                # Web UI (FastAPI + React)
│   │       ├── __init__.py
│   │       ├── api/
│   │       └── frontend/
│   │
│   ├── api/                    # REST API endpoints
│   │   ├── __init__.py
│   │   ├── auth.py             # Authentication
│   │   ├── trading.py          # Trading endpoints
│   │   ├── system.py           # System management
│   │   └── websocket.py        # WebSocket handlers
│   │
│   └── utils/                  # Common utilities
│       ├── __init__.py
│       ├── logger.py           # Logging utilities
│       ├── config.py           # Configuration helpers
│       └── performance.py      # Performance monitoring
|
└── tests/                      # Test suite
    ├── __init__.py
    ├── unit/                   # Unit tests
    │   ├── __init__.py
    │   ├── test_events.py
    │   ├── test_strategies.py
    │   ├── test_exchanges.py
    │   └── test_risk.py
    ├── integration/            # Integration tests
    │   ├── __init__.py
    │   ├── test_event_flow.py
    │   ├── test_broker_integration.py
    │   └── test_data_pipeline.py
    ├── performance/            # Performance tests
    │   ├── __init__.py
    │   ├── test_latency.py
    │   └── test_throughput.py
    └── fixtures/               # Test data and mocks
        ├── __init__.py
        ├── market_data.json
        └── test_configs.py
```

### Project Structure Guidelines

**Interface-First Architecture**: Each module follows a consistent pattern where abstract interfaces are defined at the module root using the `i` prefix convention (e.g., `ibroker.py`, `istrategy.py`), with concrete implementations organized in subdirectories.

**Key Structure Principles**:

1. **Abstract Interfaces at Module Root**: Base classes and interfaces are defined using the `i` prefix convention at each module's root level:
   - `ibroker.py` for `AbstractBroker` interface
   - `istrategy.py` for `AbstractStrategy` interface  
   - `idata_source.py` for `AbstractDataSource` interface
   - `irisk_manager.py` for risk management interfaces

2. **Implementation Subdirectories**: Concrete implementations use descriptive names that clearly identify their purpose:
   - `exchanges/binance/binance_broker.py`, `exchanges/ib/ib_broker.py` for specific broker implementations
   - `data/sources/binance_data_source.py`, `data/sources/ib_data_source.py` for data provider implementations
   - `strategies/moving_average/moving_average_strategy.py` for specific strategy implementations
   - `ui/tui/`, `ui/web/` for different interface types

3. **Configuration Management**: All configuration files are centralized in `config/` with environment-specific subdirectories and templates marked with `.example` suffix.

4. **Testing Organization**: Tests are strictly separated by type:
   - `tests/unit/` for fast, isolated tests (following your requirement)
   - `tests/integration/` for component interaction tests (following your requirement)
   - `tests/performance/` for benchmarking and performance validation

5. **Runtime Data Isolation**: All generated files are stored in `cache/` directory, which is excluded from version control to maintain clean separation between source code and runtime data.

6. **Documentation Structure**: Technical documentation is organized in `docs/` with specific files for API, architecture, development workflow, and deployment procedures.


