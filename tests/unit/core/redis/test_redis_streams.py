"""
Unit tests for Redis Streams integration.
"""

import json
from datetime import datetime
from datetime import timezone
from decimal import Decimal
from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest
from redis.exceptions import ConnectionError
from redis.exceptions import ResponseError

from silvertine.core.event.events import EventType
from silvertine.core.event.events import MarketDataEvent
from silvertine.core.redis.redis_streams import RedisStreamManager
from silvertine.core.redis.redis_streams import StreamConfig


class TestRedisStreamManager:
    """Test the RedisStreamManager class."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True
        return mock_redis

    @pytest.fixture
    def stream_config(self):
        """Create a test stream configuration."""
        return StreamConfig(
            url="redis://localhost:6379",
            max_len=10000,
            consumer_group="test_group",
            consumer_name="test_consumer",
            block_timeout=1000,
        )

    @pytest.fixture
    async def stream_manager(self, mock_redis, stream_config):
        """Create a RedisStreamManager instance."""
        with patch(
            "silvertine.core.redis.redis_streams.redis.from_url", return_value=mock_redis
        ):
            manager = RedisStreamManager(stream_config)
            await manager.connect()
            return manager

    async def test_connection_establishment(self, stream_config):
        """Test Redis connection establishment."""
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True

        with patch(
            "silvertine.core.redis.redis_streams.redis.from_url", return_value=mock_redis
        ):
            manager = RedisStreamManager(stream_config)
            await manager.connect()

            assert manager.is_connected
            mock_redis.ping.assert_called_once()

    async def test_connection_failure(self, stream_config):
        """Test Redis connection failure handling."""
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = ConnectionError("Cannot connect")

        with patch(
            "silvertine.core.redis.redis_streams.redis.from_url", return_value=mock_redis
        ):
            manager = RedisStreamManager(stream_config)

            with pytest.raises(ConnectionError):
                await manager.connect()

    async def test_stream_creation(self, stream_manager, mock_redis):
        """Test creating streams for event types."""
        await stream_manager.create_streams()

        # Verify XGROUP CREATE was called for each event type
        expected_calls = len(EventType)
        assert mock_redis.xgroup_create.call_count == expected_calls

    async def test_stream_creation_group_exists(self, stream_manager, mock_redis):
        """Test handling when consumer group already exists."""
        mock_redis.xgroup_create.side_effect = ResponseError("BUSYGROUP")

        # Should not raise exception
        await stream_manager.create_streams()

    async def test_event_publishing(self, stream_manager, mock_redis):
        """Test publishing events to streams."""
        event = MarketDataEvent(
            symbol="BTCUSDT", price=Decimal("50000.00"), volume=Decimal("1.5")
        )

        mock_redis.xadd.return_value = "1234567890-0"

        message_id = await stream_manager.publish_event(event)

        assert message_id == "1234567890-0"
        mock_redis.xadd.assert_called_once()

        # Verify the call arguments
        call_args = mock_redis.xadd.call_args
        assert call_args is not None

        # Check keyword arguments
        kwargs = call_args.kwargs
        assert kwargs["name"] == "events:MARKET_DATA"
        assert "event_data" in kwargs["fields"]
        assert "event_type" in kwargs["fields"]

    async def test_event_consumption(self, stream_manager, mock_redis):
        """Test consuming events from streams."""
        # Mock XREADGROUP response
        mock_response = [
            [
                b"events:MARKET_DATA",
                [
                    [
                        b"1234567890-0",
                        {
                            b"event_type": b"MARKET_DATA",
                            b"event_data": json.dumps(
                                {
                                    "event_type": "MARKET_DATA",
                                    "symbol": "BTCUSDT",
                                    "price": "50000.00",
                                    "volume": "1.5",
                                }
                            ).encode(),
                        },
                    ]
                ],
            ]
        ]
        mock_redis.xreadgroup.return_value = mock_response

        events = await stream_manager.consume_events([EventType.MARKET_DATA])

        assert len(events) == 1
        event, message_id = events[0]
        assert isinstance(event, MarketDataEvent)
        assert event.symbol == "BTCUSDT"
        assert message_id == "1234567890-0"

    async def test_message_acknowledgment(self, stream_manager, mock_redis):
        """Test acknowledging processed messages."""
        await stream_manager.acknowledge_message(EventType.MARKET_DATA, "1234567890-0")

        mock_redis.xack.assert_called_once_with(
            "events:MARKET_DATA", "test_group", "1234567890-0"
        )

    async def test_replay_events(self, stream_manager, mock_redis):
        """Test replaying events from a specific time range."""
        mock_response = [
            [
                b"events:MARKET_DATA",
                [
                    [
                        b"1234567890-0",
                        {
                            b"event_type": b"MARKET_DATA",
                            b"event_data": json.dumps(
                                {
                                    "event_type": "MARKET_DATA",
                                    "symbol": "BTCUSDT",
                                    "price": "50000.00",
                                    "volume": "1.5",
                                }
                            ).encode(),
                        },
                    ]
                ],
            ]
        ]
        mock_redis.xrange.return_value = mock_response[0][1]

        start_time = datetime.now(timezone.utc)
        end_time = datetime.now(timezone.utc)

        events = await stream_manager.replay_events(
            EventType.MARKET_DATA, start_time, end_time
        )

        assert len(events) == 1
        event, message_id = events[0]
        assert isinstance(event, MarketDataEvent)
        assert message_id == "1234567890-0"

    async def test_connection_retry(self, stream_config):
        """Test connection retry mechanism."""
        mock_redis = AsyncMock()
        # First call fails, second succeeds
        mock_redis.ping.side_effect = [ConnectionError("Failed"), True]

        with patch(
            "silvertine.core.redis.redis_streams.redis.from_url", return_value=mock_redis
        ):
            manager = RedisStreamManager(stream_config)

            with patch("asyncio.sleep"):  # Speed up test
                await manager.connect_with_retry(max_retries=2)

            assert manager.is_connected
            assert mock_redis.ping.call_count == 2

    async def test_connection_retry_exhausted(self, stream_config):
        """Test behavior when connection retries are exhausted."""
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = ConnectionError("Always fails")

        with patch(
            "silvertine.core.redis.redis_streams.redis.from_url", return_value=mock_redis
        ):
            manager = RedisStreamManager(stream_config)

            with patch("asyncio.sleep"):  # Speed up test
                with pytest.raises(ConnectionError):
                    await manager.connect_with_retry(max_retries=2)

    async def test_stream_info(self, stream_manager, mock_redis):
        """Test getting stream information."""
        mock_redis.xinfo_stream.return_value = {
            b"length": 100,
            b"groups": 1,
            b"last-generated-id": b"1234567890-5",
        }

        info = await stream_manager.get_stream_info(EventType.MARKET_DATA)

        assert info["length"] == 100
        assert info["groups"] == 1
        mock_redis.xinfo_stream.assert_called_once_with("events:MARKET_DATA")

    async def test_close_connection(self, stream_manager, mock_redis):
        """Test closing Redis connection."""
        await stream_manager.close()

        mock_redis.aclose.assert_called_once()
        assert not stream_manager.is_connected


class TestStreamConfig:
    """Test the StreamConfig class."""

    def test_stream_config_creation(self):
        """Test creating a stream configuration."""
        config = StreamConfig(
            url="redis://localhost:6379",
            max_len=5000,
            consumer_group="trading_group",
            consumer_name="consumer_1",
            block_timeout=2000,
        )

        assert config.url == "redis://localhost:6379"
        assert config.max_len == 5000
        assert config.consumer_group == "trading_group"
        assert config.consumer_name == "consumer_1"
        assert config.block_timeout == 2000

    def test_stream_config_defaults(self):
        """Test stream configuration with default values."""
        config = StreamConfig(url="redis://localhost:6379")

        assert config.max_len == 10000
        assert config.consumer_group == "default_group"
        assert config.consumer_name == "default_consumer"
        assert config.block_timeout == 1000

    def test_stream_name_generation(self):
        """Test stream name generation for event types."""
        config = StreamConfig(url="redis://localhost:6379")

        assert config.get_stream_name(EventType.MARKET_DATA) == "events:MARKET_DATA"
        assert config.get_stream_name(EventType.ORDER) == "events:ORDER"
        assert config.get_stream_name(EventType.FILL) == "events:FILL"
        assert config.get_stream_name(EventType.SIGNAL) == "events:SIGNAL"
