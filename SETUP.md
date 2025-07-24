# Silvertine Trading System - Setup Guide

## Quick Setup

**One-command setup** (recommended):
```bash
./setup-silvertine.sh
```

This comprehensive script will:
- ✅ Install all system dependencies 
- ✅ Set up Poetry package manager
- ✅ Compile and install TA-Lib C library
- ✅ Install all Python dependencies  
- ✅ Configure Redis server
- ✅ Create development configuration files
- ✅ Set up IDE configuration (VSCode/Pylance)
- ✅ Create runtime directories
- ✅ Validate the complete installation

## Manual Setup Options

If you prefer manual control:

```bash
# Skip system dependency installation (if already installed)
./setup-silvertine.sh --skip-system

# Skip validation tests (for faster setup)
./setup-silvertine.sh --skip-validation

# Show help
./setup-silvertine.sh --help
```

## System Requirements

- **OS**: Ubuntu 20.04+, macOS 10.15+, or similar Linux distribution
- **Python**: 3.10 or higher
- **Memory**: 4GB RAM minimum, 8GB recommended
- **Disk**: 2GB free space for dependencies
- **Network**: Internet connection for downloading dependencies

## What Gets Installed

### System Dependencies
- Build tools (gcc, make, autotools)
- Python development headers
- Redis server
- SQLite database
- SSL/TLS libraries

### Python Dependencies  
- **Core Framework**: FastAPI, asyncio, Pydantic
- **Data Processing**: NumPy, Pandas, TA-Lib
- **Trading**: Interactive Brokers API, Binance connector
- **UI**: Textual (TUI), PySide6 (GUI), Plotly (charts)
- **Infrastructure**: Redis, SQLite, WebSockets
- **Development**: pytest, mypy, ruff, black

### Configuration Files
- Development environment settings
- Exchange API configurations (templates)
- Risk management parameters
- IDE settings (VS Code, Pylance)

## IDE Setup

After running the setup script:

### VS Code
1. Restart VS Code
2. Press `Ctrl+Shift+P` (Cmd+Shift+P on macOS)
3. Type "Python: Select Interpreter"
4. Choose the Poetry virtual environment path (displayed after setup)

### PyCharm
1. Go to File → Settings → Project → Python Interpreter
2. Click the gear icon → Add
3. Select "Poetry Environment" → Existing Environment
4. Point to the Poetry virtual environment path

### Other IDEs
- The setup creates `pyrightconfig.json` for LSP-compatible editors
- Virtual environment path: `~/.cache/pypoetry/virtualenvs/silvertine-*/`

## Validation

Test your installation:

```bash
# Test Python environment
poetry run python -c "import silvertine; print('✓ Project ready')"

# Test TA-Lib (may take time to compile)
poetry run python -c "import talib; print('✓ TA-Lib functions:', len(talib.get_functions()))"

# Test imports resolution
poetry run python -c "import loguru; print('✓ Loguru import working')"

# Run test suite
poetry run pytest tests/unit/ -v
```

## Development Workflow

```bash
# Activate Poetry shell
poetry shell

# Run linting and formatting
poetry run ruff check . --fix
poetry run black .

# Type checking
poetry run mypy silvertine

# Run tests
poetry run pytest

# Start development server
poetry run python -m silvertine
```

## Configuration

### Environment Settings
Edit `config/environments/development.yaml` for:
- Database connections
- Redis settings  
- API endpoints
- Logging levels

### Exchange APIs
Configure in `config/exchanges/`:
- `binance_testnet.yaml` - Binance API credentials
- `interactive_brokers.yaml` - IB Gateway settings

### Security
- Never commit API keys to version control
- Use `.env` files for sensitive configuration
- Set appropriate file permissions (600) for config files

## Troubleshooting

### TA-Lib Issues
If TA-Lib import fails:
```bash
# Check if C library is installed
ldconfig -p | grep ta_lib

# Reinstall if needed
sudo rm -rf /usr/local/lib/libta_lib*
sudo rm -rf /usr/local/include/ta_lib.h
./install-ta-lib.sh
```

### Redis Issues
```bash
# Check Redis status
redis-cli ping

# Start Redis (Ubuntu)
sudo systemctl start redis-server

# Start Redis (macOS)
brew services start redis
```

### IDE Import Issues
```bash
# Regenerate IDE configuration
poetry env info --path  # Copy this path
# Update .vscode/settings.json with correct path
```

### Permission Issues
```bash
# Fix Poetry permissions
poetry config virtualenvs.create true
poetry config virtualenvs.in-project false

# Recreate virtual environment
poetry env remove python
poetry install
```

## Performance Optimization

For production deployment:
- Use Redis cluster for high availability
- Configure PostgreSQL instead of SQLite for better performance
- Set up proper monitoring and logging
- Use reverse proxy (nginx) for API endpoints

## Support

- 📖 Check `README.md` for architecture details
- 🐛 Report issues via project issue tracker  
- 📚 Review code documentation in `docs/`
- 🔧 Configuration examples in `config/`

---

**Next Steps**: After successful setup, see the main `README.md` for development guidance and trading strategies.