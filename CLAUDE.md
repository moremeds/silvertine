# Silvertine - Claude Code Instructions

**AI Assistant Instructions for the Silvertine Quantitative Trading System**

## Project Overview

**Silvertine** is a lightweight, event-driven quantitative trading system for medium-to-low frequency strategies.

**Core Features**: Event-driven architecture with asyncio event bus | Multi-exchange support (Binance testnet + Interactive Brokers) | Real-time TUI interface using Rich | Paper trading with realistic simulation | Extensible strategy framework

**Event Types**: `MarketDataEvent`, `OrderEvent`, `FillEvent`, `SignalEvent`

**Tech Stack**: Python 3.11+ with asyncio | Redis Streams for events | SQLite for storage | Rich/FastAPI for UI | WebSocket feeds | Docker deployment

## TaskMaster Integration

**Key Commands**:
- `task-master list/next/show <id>` - View tasks
- `task-master set-status --id=<id> --status=done` - Mark complete
- `task-master expand --id=<id> --research --force` - Break into subtasks
- `task-master update-task --id=<id> --prompt="changes"` - Update task

**Task Structure** (15 tasks in `.taskmaster/tasks/tasks.json`):
- **Core (1-4)**: Repository, Event Engine, Broker Interface, Data Aggregation
- **Trading (5-8)**: Strategy Framework, Backtesting, TUI, Risk Management  
- **Operations (9-15)**: API, Testing, Deployment, Security, Configuration, Web UI

## Development Workflow

**Current Phase**: Core Development - Reference `.taskmaster/tasks/tasks.json` for priorities

**Principles**: TDD (75% coverage) | Performance-first (<100ms events, <500ms orders) | Clean architecture | Configuration externalization

**Performance**: 1000 events/sec | <1GB memory | 24-hour stability

## Data Management Rules

**Configuration**: All config → `config/` directory (environments/, exchanges/, strategies/, risk/, logging/, database/, security/)
- No magic numbers in code
- Environment variable injection
- Validation at startup
- `.example` templates for sensitive configs

**Runtime Data**: All generated → `silver_cache/` directory (sqlite/, logs/, temp/, redis/, progress/)
- Version control: Only source code and config templates
- File naming: ISO timestamps (e.g., `trading_2024-01-15_14-30-00.log`)
- Retention: Market data 30d, trade history permanent, logs 7d rotation

**Progress Tracking**: Session state in `silver_cache/progress/session_progress.json`
- Auto-cleanup: 2 days age-based, git commit trigger, max 10 snapshots
- Recovery: Check progress → review context → validate changes → resume

## Design Patterns & Key Interfaces

**Strategy Pattern**:
```python
class AbstractStrategy:
    async def on_bar(self, bar: MarketData) -> Optional[Signal]: pass
    async def on_signal(self, signal: Signal) -> Optional[Order]: pass
    async def on_fill(self, fill: FillEvent) -> None: pass
```

**Broker Pattern**:
```python
class AbstractBroker:
    async def place_order(self, order: Order) -> str: pass
    async def cancel_order(self, order_id: str) -> bool: pass
    async def get_positions(self) -> List[Position]: pass
```

**Event Bus Pattern**:
```python
class EventBus:
    async def publish(self, event: Event) -> None: pass
    def subscribe(self, event_type: Type, handler: Callable) -> None: pass
```

## Exchange Configuration

**Binance Testnet**: `config/exchanges/binance_testnet.yaml` | WebSocket + REST API | Env vars: `BINANCE_TESTNET_API_KEY/SECRET_KEY`

**Interactive Brokers**: `config/exchanges/interactive_brokers.yaml` | IB Gateway/TWS | ib_insync API

## Risk Management & Monitoring

**Risk Controls**: `config/risk/` - Position limits, stop orders, drawdown monitoring, emergency controls (Ctrl+C)

**Performance Metrics**: `config/monitoring/` - Real-time P&L, VaR, Sharpe ratio, exposure monitoring

## TUI Interface

**Panels**: Market Data (real-time prices, order placement) | Positions (holdings, P&L) | Strategy (status, signals) | System Logs | Control Panel

**Shortcuts**: `Ctrl+C` emergency stop | `s` start | `q` quit | `r` restart connections | `p` pause/resume

## Testing Strategy

**Multi-layered TDD**:
- **Unit**: 75% coverage, tests first, mock/simulated data OK
- **Integration**: Real data sources, event flow testing, **mandatory logging** → `silver_cache/logs/integration_tests/`
- **Stability**: 8-24h runtime, memory leak detection
- **Performance**: Latency/throughput benchmarks

## Type Safety Guidelines

**Critical Rules**:
- **Constructor Consistency**: Match parent class signatures exactly
```python
def __init__(self, event_bus, broker_id: str = "default", config: Optional[Dict[str, Any]] = None):
    super().__init__(event_bus=event_bus, broker_id=broker_id, config=config)
```

**Interface Compliance**: Identical signatures for abstract methods | Async consistency | Type annotations required

**Common Issues & Solutions**:
- `sum()` empty iterables: `sum(...) or Decimal("0")`
- Dict variance: Use `Union` types for mixed values
- Optional arithmetic: `count + (pipeline_events or 0)`
- Event handlers: Use base `Event` type, cast internally

**Verification**: `poetry run ruff check . --fix` | `poetry run pytest tests/unit/ -v`

## Project Structure (Interface-First Architecture)

**Core Organization**:
```
silvertine/
├── core/              # Framework (event/, redis/, monitoring/, pipeline/)
├── exchanges/         # interfaces/ + implementations/ (binance/, interactive_brokers/, paper/)
├── data/              # interfaces/ + sources/ + aggregation/ + quality/ + storage/
├── strategies/        # interfaces/ + implementations/ + indicators/ + signals/
├── risk/              # interfaces/ + controls/ + monitoring/ + analysis/
├── backtesting/       # engine/ + models/ + analysis/
├── ui/                # tui/ + web/
├── api/               # rest/ + websocket/
└── utils/             # logging/ + config/ + datetime/ + performance/

tests/                 # Mirrors source structure exactly
config/                # All configuration with .example templates
silver_cache/          # All runtime data (gitignored)
```

**Structure Principles**: Interface segregation (`interfaces/` + `implementations/`) | Mirrored test structure | Logical grouping | Configuration hierarchy

## Development Constraints

**Critical Rules**:
- Do only what's explicitly requested
- NEVER create files unless absolutely necessary
- ALWAYS prefer editing existing files
- NEVER proactively create documentation
- NEVER use emojis
- Use Poetry exclusively for dependencies
- Focus on minimal file creation

## Dependency Management

**Poetry Commands**:
- `poetry install` - Install all dependencies
- `poetry add <package>` - Production deps
- `poetry add --group dev <package>` - Development deps
- `poetry shell` - Activate environment
- NEVER use pip or requirements.txt

## Codacy Integration

**Required Actions**:
- **After ANY file edit**: Run `codacy_cli_analyze` for edited files
- **After dependency install**: Run `codacy_cli_analyze` with tool="trivy" 
- **Repository setup**: Use `git remote -v` to determine provider (GitHub="gh", GitLab="gl", Bitbucket="bb")

---

**Important**: Maintain test-driven development, externalize all configuration, ensure type safety, and follow interface-first architecture principles.