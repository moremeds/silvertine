"""
BrokerFactory implementation for dynamic broker creation and management.

This module implements the factory pattern for creating broker instances with
configuration validation, environment variable substitution, and lifecycle management.
"""

import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from ..core.event.event_bus import EventBus
from .iexchange import AbstractBroker


class BrokerRegistry:
    """Registry for broker implementations with automatic discovery."""

    _brokers: dict[str, type[AbstractBroker]] = {}

    @classmethod
    def register(cls, broker_type: str, broker_class: type[AbstractBroker]) -> None:
        """
        Register a broker implementation.

        Args:
            broker_type: Unique identifier for the broker type
            broker_class: Broker class to register
        """
        cls._brokers[broker_type] = broker_class

    @classmethod
    def get(cls, broker_type: str) -> type[AbstractBroker]:
        """
        Get a registered broker class.

        Args:
            broker_type: Broker type identifier

        Returns:
            Broker class

        Raises:
            ValueError: If broker type not found
        """
        if broker_type not in cls._brokers:
            raise ValueError(f"Unknown broker type: {broker_type}")
        return cls._brokers[broker_type]

    @classmethod
    def list_available(cls) -> list[str]:
        """
        List all available broker types.

        Returns:
            List of registered broker type identifiers
        """
        return list(cls._brokers.keys())

    @classmethod
    def auto_register(cls, broker_type: str) -> Callable:
        """
        Decorator for automatic broker registration.

        Args:
            broker_type: Broker type identifier

        Returns:
            Class decorator function
        """
        def decorator(broker_class: type[AbstractBroker]) -> type[AbstractBroker]:
            cls.register(broker_type, broker_class)
            return broker_class
        return decorator


class BrokerFactory:
    """
    Factory for creating and managing broker instances.

    Provides configuration validation, environment variable substitution,
    lifecycle management, and broker registry integration.
    """

    def __init__(self, event_bus: EventBus):
        """
        Initialize the broker factory.

        Args:
            event_bus: Event bus for broker communication
        """
        self.event_bus = event_bus
        self._brokers: dict[str, AbstractBroker] = {}

    async def create_broker(
        self,
        broker_name: str,
        config: dict[str, Any]
    ) -> AbstractBroker:
        """
        Create a new broker instance.

        Args:
            broker_name: Unique name for the broker instance
            config: Broker configuration dictionary

        Returns:
            Configured broker instance

        Raises:
            ValueError: If configuration invalid or broker name exists
        """
        # Validate broker name uniqueness
        if broker_name in self._brokers:
            raise ValueError(f"Broker with name '{broker_name}' already exists")

        # Validate configuration
        self._validate_config(config)

        # Substitute environment variables
        config_with_env = self._substitute_env_vars(config)

        # Get broker class from registry
        broker_type = config_with_env["broker_type"]
        broker_class = BrokerRegistry.get(broker_type)

        # Create broker instance - handle different constructor patterns
        broker_config = config_with_env.get("config", {})
        broker = await self._create_broker_instance(
            broker_class, broker_name, broker_config
        )

        # Store broker instance
        self._brokers[broker_name] = broker

        # Initialize broker
        await broker.initialize()

        return broker

    def get_broker(self, broker_name: str) -> AbstractBroker | None:
        """
        Get an existing broker by name.

        Args:
            broker_name: Name of the broker

        Returns:
            Broker instance or None if not found
        """
        return self._brokers.get(broker_name)

    def list_brokers(self) -> list[str]:
        """
        List all created broker names.

        Returns:
            List of broker names
        """
        return list(self._brokers.keys())

    async def remove_broker(self, broker_name: str) -> bool:
        """
        Remove and shutdown a broker.

        Args:
            broker_name: Name of broker to remove

        Returns:
            True if broker was removed, False if not found
        """
        if broker_name not in self._brokers:
            return False

        broker = self._brokers[broker_name]

        # Shutdown broker gracefully
        await broker.shutdown()

        # Remove from registry
        del self._brokers[broker_name]

        return True

    async def shutdown_all(self) -> None:
        """Shutdown all managed brokers."""
        for broker_name in list(self._brokers.keys()):
            await self.remove_broker(broker_name)

    async def create_from_config_file(self, config_path: str) -> AbstractBroker:
        """
        Create broker from YAML configuration file.

        Args:
            config_path: Path to YAML configuration file

        Returns:
            Configured broker instance

        Raises:
            FileNotFoundError: If config file not found
            ValueError: If configuration invalid
        """
        # Read configuration file
        with open(config_path) as file:
            config = yaml.safe_load(file)

        # Extract broker name from config or use filename
        broker_name = config.get("name") or Path(config_path).stem

        return await self.create_broker(broker_name, config)

    def _validate_config(self, config: dict[str, Any]) -> None:
        """
        Validate broker configuration.

        Args:
            config: Configuration dictionary to validate

        Raises:
            ValueError: If configuration invalid
        """
        # Required fields
        required_fields = ["broker_type", "name"]
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required field: {field}")

        # Validate broker configuration exists
        if "config" not in config:
            raise ValueError("Missing broker configuration")

        # Validate broker name format
        broker_name = config["name"]
        if not self._is_valid_broker_name(broker_name):
            raise ValueError(f"Invalid broker name: {broker_name}")

    def _is_valid_broker_name(self, name: str) -> bool:
        """
        Validate broker name format.

        Args:
            name: Broker name to validate

        Returns:
            True if name is valid
        """
        # Check basic requirements
        if not name or len(name) > 100:
            return False

        # Check format (alphanumeric, underscore, hyphen only)
        if not re.match(r'^[a-zA-Z0-9_-]+$', name):
            return False

        return True

    def _substitute_env_vars(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        Substitute environment variables in configuration.

        Args:
            config: Configuration dictionary

        Returns:
            Configuration with environment variables substituted

        Raises:
            ValueError: If required environment variable not found
        """
        import copy
        import json

        # Deep copy to avoid modifying original
        config_copy = copy.deepcopy(config)

        # Convert to JSON string for easy regex substitution
        config_str = json.dumps(config_copy)

        # Find all environment variable references
        env_pattern = r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}'
        matches = re.findall(env_pattern, config_str)

        # Substitute each environment variable
        for env_var in matches:
            if env_var not in os.environ:
                raise ValueError(f"Environment variable '{env_var}' not found")

            env_value = os.environ[env_var]
            config_str = config_str.replace(f"${{{env_var}}}", env_value)

        # Parse back to dictionary
        return json.loads(config_str)

    async def _create_broker_instance(
        self,
        broker_class: type[AbstractBroker],
        broker_name: str,
        broker_config: dict[str, Any]
    ) -> AbstractBroker:
        """
        Create broker instance handling different constructor patterns.

        Args:
            broker_class: Broker class to instantiate
            broker_name: Unique broker name
            broker_config: Broker-specific configuration

        Returns:
            Broker instance
        """
        # All brokers now follow the standard AbstractBroker constructor pattern
        broker = broker_class(
            event_bus=self.event_bus,
            broker_id=broker_name,
            config=broker_config
        )

        return broker
