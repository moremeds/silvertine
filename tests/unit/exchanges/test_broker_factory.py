"""
Test cases for BrokerFactory pattern.

Following TDD methodology - tests written before implementation to drive design.
"""

from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest

from silvertine.core.event.event_bus import EventBus
from silvertine.exchanges.factory import BrokerFactory
from silvertine.exchanges.factory import BrokerRegistry
from silvertine.exchanges.paper.paper_broker import PaperTradingBroker


@pytest.fixture
def event_bus():
    """Create event bus for testing."""
    return EventBus()


@pytest.fixture
def broker_factory(event_bus):
    """Create broker factory for testing."""
    return BrokerFactory(event_bus=event_bus)


@pytest.fixture
def test_config():
    """Create test broker configuration."""
    return {
        "broker_type": "paper",
        "name": "test_paper",
        "config": {
            "initial_balance": 100000.0,
            "latency_ms": 50,
            "slippage_model": "FIXED",
            "slippage_value": 0.001
        }
    }


class TestBrokerRegistry:
    """Test broker registration and discovery."""

    def test_register_broker_class(self):
        """Test registering a broker class."""
        # Clear registry first
        BrokerRegistry._brokers.clear()

        # Register paper trading broker
        BrokerRegistry.register("paper", PaperTradingBroker)

        assert "paper" in BrokerRegistry._brokers
        assert BrokerRegistry._brokers["paper"] == PaperTradingBroker

    def test_get_registered_broker(self):
        """Test getting a registered broker class."""
        # Clear and register
        BrokerRegistry._brokers.clear()
        BrokerRegistry.register("paper", PaperTradingBroker)

        broker_class = BrokerRegistry.get("paper")
        assert broker_class == PaperTradingBroker

    def test_get_nonexistent_broker(self):
        """Test getting a non-existent broker raises error."""
        # Clear registry
        BrokerRegistry._brokers.clear()

        with pytest.raises(ValueError, match="Unknown broker type: nonexistent"):
            BrokerRegistry.get("nonexistent")

    def test_list_available_brokers(self):
        """Test listing available broker types."""
        # Clear and register multiple
        BrokerRegistry._brokers.clear()
        BrokerRegistry.register("paper", PaperTradingBroker)
        BrokerRegistry.register("test", Mock)

        available = BrokerRegistry.list_available()
        assert set(available) == {"paper", "test"}

    def test_auto_registration_decorator(self):
        """Test auto-registration decorator works."""
        # Clear registry
        BrokerRegistry._brokers.clear()

        @BrokerRegistry.auto_register("test_auto")
        class TestBroker:
            pass

        assert "test_auto" in BrokerRegistry._brokers
        assert BrokerRegistry._brokers["test_auto"] == TestBroker


class TestBrokerFactory:
    """Test broker factory functionality."""

    def test_factory_initialization(self, event_bus):
        """Test factory initializes correctly."""
        factory = BrokerFactory(event_bus=event_bus)
        assert factory.event_bus == event_bus
        assert factory._brokers == {}

    @pytest.mark.asyncio
    async def test_create_paper_broker(self, broker_factory, test_config):
        """Test creating a paper trading broker."""
        # Register paper broker
        BrokerRegistry.register("paper", PaperTradingBroker)

        broker = await broker_factory.create_broker("test_paper", test_config)

        assert isinstance(broker, PaperTradingBroker)
        assert broker.broker_id == "test_paper"
        assert broker.config == test_config["config"]

    @pytest.mark.asyncio
    async def test_create_broker_invalid_type(self, broker_factory):
        """Test creating broker with invalid type raises error."""
        config = {"broker_type": "invalid", "name": "test", "config": {}}

        with pytest.raises(ValueError, match="Unknown broker type: invalid"):
            await broker_factory.create_broker("test", config)

    @pytest.mark.asyncio
    async def test_create_broker_missing_config(self, broker_factory):
        """Test creating broker with missing config raises error."""
        config = {"broker_type": "paper", "name": "test"}  # Missing config

        with pytest.raises(ValueError, match="Missing broker configuration"):
            await broker_factory.create_broker("test", config)

    @pytest.mark.asyncio
    async def test_create_broker_duplicate_name(self, broker_factory, test_config):
        """Test creating broker with duplicate name raises error."""
        # Register and create first broker
        BrokerRegistry.register("paper", PaperTradingBroker)
        await broker_factory.create_broker("test_paper", test_config)

        # Try to create duplicate
        with pytest.raises(ValueError, match="Broker with name 'test_paper' already exists"):
            await broker_factory.create_broker("test_paper", test_config)

    @pytest.mark.asyncio
    async def test_get_broker(self, broker_factory, test_config):
        """Test getting an existing broker."""
        # Register and create broker
        BrokerRegistry.register("paper", PaperTradingBroker)
        broker = await broker_factory.create_broker("test_paper", test_config)

        # Get broker
        retrieved = broker_factory.get_broker("test_paper")
        assert retrieved == broker

    def test_get_nonexistent_broker(self, broker_factory):
        """Test getting non-existent broker returns None."""
        broker = broker_factory.get_broker("nonexistent")
        assert broker is None

    def test_list_brokers(self, broker_factory):
        """Test listing broker names."""
        # Initially empty
        assert broker_factory.list_brokers() == []

        # Mock a broker
        broker_factory._brokers["test"] = Mock()
        assert broker_factory.list_brokers() == ["test"]

    @pytest.mark.asyncio
    async def test_remove_broker(self, broker_factory, test_config):
        """Test removing a broker."""
        # Register and create broker
        BrokerRegistry.register("paper", PaperTradingBroker)
        broker = await broker_factory.create_broker("test_paper", test_config)

        # Mock shutdown method
        broker.shutdown = AsyncMock()

        # Remove broker
        removed = await broker_factory.remove_broker("test_paper")
        assert removed is True
        assert "test_paper" not in broker_factory._brokers
        broker.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_nonexistent_broker(self, broker_factory):
        """Test removing non-existent broker returns False."""
        removed = await broker_factory.remove_broker("nonexistent")
        assert removed is False

    @pytest.mark.asyncio
    async def test_shutdown_all_brokers(self, broker_factory, test_config):
        """Test shutting down all brokers."""
        # Register and create multiple brokers
        BrokerRegistry.register("paper", PaperTradingBroker)
        broker1 = await broker_factory.create_broker("broker1", test_config)
        broker2 = await broker_factory.create_broker("broker2", test_config)

        # Mock shutdown methods
        broker1.shutdown = AsyncMock()
        broker2.shutdown = AsyncMock()

        # Shutdown all
        await broker_factory.shutdown_all()

        # Verify shutdowns called and brokers removed
        broker1.shutdown.assert_called_once()
        broker2.shutdown.assert_called_once()
        assert len(broker_factory._brokers) == 0

    @patch('yaml.safe_load')
    @patch('builtins.open', create=True)
    async def test_create_from_config_file(self, mock_open, mock_yaml, broker_factory):
        """Test creating broker from YAML configuration file."""
        # Mock file contents
        config_data = {
            "broker_type": "paper",
            "name": "file_broker",
            "config": {
                "initial_balance": 50000.0,
                "latency_ms": 25
            }
        }
        mock_yaml.return_value = config_data

        # Register paper broker
        BrokerRegistry.register("paper", PaperTradingBroker)

        # Create from config
        broker = await broker_factory.create_from_config_file("config.yaml")

        # Verify file operations
        mock_open.assert_called_once_with("config.yaml", 'r')
        mock_yaml.assert_called_once()

        # Verify broker creation
        assert isinstance(broker, PaperTradingBroker)
        assert broker.broker_id == "file_broker"

    @patch('yaml.safe_load')
    @patch('builtins.open', side_effect=FileNotFoundError)
    async def test_create_from_missing_config_file(self, mock_open, mock_yaml, broker_factory):
        """Test creating broker from missing config file raises error."""
        with pytest.raises(FileNotFoundError):
            await broker_factory.create_from_config_file("missing.yaml")


class TestConfigurationValidation:
    """Test configuration validation logic."""

    @pytest.mark.asyncio
    async def test_validate_paper_config(self, broker_factory):
        """Test validation of paper trading configuration."""
        # Valid config
        config = {
            "broker_type": "paper",
            "name": "test",
            "config": {
                "initial_balance": 100000.0,
                "latency_ms": 50,
                "slippage_model": "FIXED"
            }
        }

        # Should not raise
        BrokerRegistry.register("paper", PaperTradingBroker)
        broker = await broker_factory.create_broker("test", config)
        assert isinstance(broker, PaperTradingBroker)

    def test_validate_required_fields(self, broker_factory):
        """Test validation of required configuration fields."""
        # Missing broker_type
        config = {"name": "test", "config": {}}
        with pytest.raises(ValueError, match="Missing required field: broker_type"):
            broker_factory._validate_config(config)

        # Missing name
        config = {"broker_type": "paper", "config": {}}
        with pytest.raises(ValueError, match="Missing required field: name"):
            broker_factory._validate_config(config)

        # Missing config
        config = {"broker_type": "paper", "name": "test"}
        with pytest.raises(ValueError, match="Missing broker configuration"):
            broker_factory._validate_config(config)

    def test_validate_broker_name_format(self, broker_factory):
        """Test validation of broker name format."""
        # Valid names
        valid_configs = [
            {"broker_type": "paper", "name": "valid_name", "config": {}},
            {"broker_type": "paper", "name": "valid123", "config": {}},
            {"broker_type": "paper", "name": "Valid-Name_123", "config": {}}
        ]

        for config in valid_configs:
            broker_factory._validate_config(config)  # Should not raise

        # Invalid names
        invalid_configs = [
            {"broker_type": "paper", "name": "invalid name", "config": {}},  # Space
            {"broker_type": "paper", "name": "invalid@name", "config": {}},  # Special char
            {"broker_type": "paper", "name": "", "config": {}},  # Empty
            {"broker_type": "paper", "name": "a" * 101, "config": {}}  # Too long
        ]

        for config in invalid_configs:
            with pytest.raises(ValueError, match="Invalid broker name"):
                broker_factory._validate_config(config)


class TestEnvironmentVariableSubstitution:
    """Test environment variable substitution in configurations."""

    @patch.dict('os.environ', {'API_KEY': 'test_key', 'API_SECRET': 'test_secret'})
    def test_substitute_environment_variables(self, broker_factory):
        """Test substitution of environment variables in config."""
        config = {
            "broker_type": "binance",
            "name": "test",
            "config": {
                "api_key": "${API_KEY}",
                "api_secret": "${API_SECRET}",
                "testnet": True
            }
        }

        substituted = broker_factory._substitute_env_vars(config)

        assert substituted["config"]["api_key"] == "test_key"
        assert substituted["config"]["api_secret"] == "test_secret"
        assert substituted["config"]["testnet"] is True  # Non-env var unchanged

    def test_substitute_missing_environment_variable(self, broker_factory):
        """Test substitution with missing environment variable."""
        config = {
            "broker_type": "binance",
            "name": "test",
            "config": {
                "api_key": "${MISSING_KEY}",
                "testnet": True
            }
        }

        with pytest.raises(ValueError, match="Environment variable 'MISSING_KEY' not found"):
            broker_factory._substitute_env_vars(config)

    def test_no_substitution_needed(self, broker_factory):
        """Test config without environment variables."""
        config = {
            "broker_type": "paper",
            "name": "test",
            "config": {
                "initial_balance": 100000.0,
                "latency_ms": 50
            }
        }

        substituted = broker_factory._substitute_env_vars(config)
        assert substituted == config  # Should be unchanged
