"""
Redis Streams integration for event persistence and replay.

This module provides the RedisStreamManager class for managing Redis Streams
operations including:
- Event publishing with automatic stream creation
- Event consumption with consumer groups
- Connection management with retry logic
- Event replay functionality
- Stream monitoring and information
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

import redis.asyncio as redis
from pydantic import BaseModel
from pydantic import Field
from redis.exceptions import ConnectionError
from redis.exceptions import ResponseError

from ..event.events import Event
from ..event.events import EventType

logger = logging.getLogger(__name__)


class StreamConfig(BaseModel):
    """Configuration for Redis Streams."""

    url: str = Field(..., description="Redis connection URL")
    max_len: int = Field(default=10000, description="Maximum stream length")
    consumer_group: str = Field(
        default="default_group", description="Consumer group name"
    )
    consumer_name: str = Field(default="default_consumer", description="Consumer name")
    block_timeout: int = Field(
        default=1000, description="Block timeout in milliseconds"
    )

    def get_stream_name(self, event_type: EventType) -> str:
        """Generate stream name for event type."""
        return f"events:{event_type.value}"


class RedisStreamManager:
    """
    Manages Redis Streams for event persistence and consumption.

    Provides high-level interface for:
    - Publishing events to appropriate streams
    - Consuming events with consumer groups
    - Connection management with automatic retry
    - Event replay and historical data access
    """

    def __init__(self, config: StreamConfig):
        """Initialize the Redis Stream Manager."""
        self.config = config
        self.redis: redis.Redis | None = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if Redis connection is active."""
        return self._connected

    async def connect(self) -> None:
        """Establish connection to Redis."""
        try:
            self.redis = redis.from_url(
                self.config.url,
                decode_responses=False,  # We'll handle encoding ourselves
                retry_on_timeout=True,
                health_check_interval=30,
            )
            await self.redis.ping()
            self._connected = True
            logger.info("Connected to Redis at %s", self.config.url)

        except ConnectionError as e:
            logger.error("Failed to connect to Redis: %s", e)
            self._connected = False
            raise

    async def connect_with_retry(
        self, max_retries: int = 3, base_delay: float = 1.0
    ) -> None:
        """Connect to Redis with exponential backoff retry."""
        for attempt in range(max_retries + 1):
            try:
                await self.connect()
                return
            except ConnectionError as e:
                if attempt == max_retries:
                    logger.error("Failed to connect after %d attempts", max_retries)
                    raise

                delay = base_delay * (2**attempt)
                logger.warning(
                    "Connection attempt %d failed, retrying in %.1fs: %s",
                    attempt + 1,
                    delay,
                    e,
                )
                await asyncio.sleep(delay)

    async def create_streams(self) -> None:
        """Create streams and consumer groups for all event types."""
        if not self.redis:
            raise RuntimeError("Not connected to Redis")

        for event_type in EventType:
            stream_name = self.config.get_stream_name(event_type)

            try:
                await self.redis.xgroup_create(
                    name=stream_name,
                    groupname=self.config.consumer_group,
                    id="0",
                    mkstream=True,
                )
                logger.info(
                    "Created stream %s with group %s",
                    stream_name,
                    self.config.consumer_group,
                )

            except ResponseError as e:
                if "BUSYGROUP" in str(e):
                    logger.debug(
                        "Consumer group already exists for stream %s", stream_name
                    )
                else:
                    logger.error("Failed to create stream %s: %s", stream_name, e)
                    raise

    async def publish_event(self, event: Event) -> str:
        """
        Publish an event to its appropriate stream.

        Args:
            event: The event to publish

        Returns:
            Message ID from Redis
        """
        if not self.redis:
            raise RuntimeError("Not connected to Redis")

        stream_name = self.config.get_stream_name(event.event_type)

        # Serialize event to JSON
        event_data = event.model_dump_json()

        # Prepare fields for Redis stream
        fields = {
            "event_type": event.event_type.value,
            "event_data": event_data,
            "timestamp": event.timestamp.isoformat(),
        }

        try:
            message_id = await self.redis.xadd(
                name=stream_name,
                fields=fields,
                maxlen=self.config.max_len,
                approximate=True,
            )

            logger.debug(
                "Published event %s to stream %s with ID %s",
                event.event_id,
                stream_name,
                message_id,
            )
            return message_id.decode() if isinstance(message_id, bytes) else message_id

        except Exception as e:
            logger.error("Failed to publish event to stream %s: %s", stream_name, e)
            raise

    async def consume_events(
        self, event_types: list[EventType], count: int = 10
    ) -> list[tuple[Event, str]]:
        """
        Consume events from specified streams.

        Args:
            event_types: List of event types to consume from
            count: Maximum number of events to consume

        Returns:
            List of (event, message_id) tuples
        """
        if not self.redis:
            raise RuntimeError("Not connected to Redis")

        # Build streams dict for XREADGROUP
        streams = {
            self.config.get_stream_name(event_type): ">" for event_type in event_types
        }

        try:
            response = await self.redis.xreadgroup(
                groupname=self.config.consumer_group,
                consumername=self.config.consumer_name,
                streams=streams,
                count=count,
                block=self.config.block_timeout,
            )

            events = []

            for stream_data in response:
                stream_name = stream_data[0].decode()
                messages = stream_data[1]

                for message_id, fields in messages:
                    try:
                        # Decode message fields
                        decoded_fields = {
                            k.decode(): v.decode() if isinstance(v, bytes) else v
                            for k, v in fields.items()
                        }

                        # Deserialize event data
                        event_data = json.loads(decoded_fields["event_data"])
                        event = self._deserialize_event(event_data)

                        message_id_str = (
                            message_id.decode()
                            if isinstance(message_id, bytes)
                            else message_id
                        )
                        events.append((event, message_id_str))

                    except Exception as e:
                        logger.error(
                            "Failed to deserialize event from stream %s, message %s: %s",
                            stream_name,
                            message_id,
                            e,
                        )
                        continue

            logger.debug(
                "Consumed %d events from %d streams", len(events), len(event_types)
            )
            return events

        except Exception as e:
            logger.error("Failed to consume events: %s", e)
            raise

    async def acknowledge_message(self, event_type: EventType, message_id: str) -> None:
        """Acknowledge a processed message."""
        if not self.redis:
            raise RuntimeError("Not connected to Redis")

        stream_name = self.config.get_stream_name(event_type)

        try:
            await self.redis.xack(stream_name, self.config.consumer_group, message_id)
            logger.debug(
                "Acknowledged message %s in stream %s", message_id, stream_name
            )

        except Exception as e:
            logger.error(
                "Failed to acknowledge message %s in stream %s: %s",
                message_id,
                stream_name,
                e,
            )
            raise

    async def replay_events(
        self,
        event_type: EventType,
        start_time: datetime,
        end_time: datetime,
        count: int = 1000,
    ) -> list[tuple[Event, str]]:
        """
        Replay events from a specific time range.

        Args:
            event_type: Type of events to replay
            start_time: Start time for replay
            end_time: End time for replay
            count: Maximum number of events to return

        Returns:
            List of (event, message_id) tuples
        """
        if not self.redis:
            raise RuntimeError("Not connected to Redis")

        stream_name = self.config.get_stream_name(event_type)

        # Convert timestamps to Redis stream IDs
        start_id = f"{int(start_time.timestamp() * 1000)}-0"
        end_id = f"{int(end_time.timestamp() * 1000)}-999"

        try:
            response = await self.redis.xrange(
                stream_name, min=start_id, max=end_id, count=count
            )

            events = []

            for message_id, fields in response:
                try:
                    # Decode message fields
                    decoded_fields = {
                        k.decode(): v.decode() if isinstance(v, bytes) else v
                        for k, v in fields.items()
                    }

                    # Deserialize event data
                    event_data = json.loads(decoded_fields["event_data"])
                    event = self._deserialize_event(event_data)

                    message_id_str = (
                        message_id.decode()
                        if isinstance(message_id, bytes)
                        else message_id
                    )
                    events.append((event, message_id_str))

                except Exception as e:
                    logger.error(
                        "Failed to deserialize event from replay, message %s: %s",
                        message_id,
                        e,
                    )
                    continue

            logger.info(
                "Replayed %d events from stream %s between %s and %s",
                len(events),
                stream_name,
                start_time,
                end_time,
            )
            return events

        except Exception as e:
            logger.error("Failed to replay events from stream %s: %s", stream_name, e)
            raise

    async def get_stream_info(self, event_type: EventType) -> dict[str, Any]:
        """Get information about a stream."""
        if not self.redis:
            raise RuntimeError("Not connected to Redis")

        stream_name = self.config.get_stream_name(event_type)

        try:
            info = await self.redis.xinfo_stream(stream_name)

            # Decode byte keys/values to strings/ints
            decoded_info = {}
            for key, value in info.items():
                decoded_key = key.decode() if isinstance(key, bytes) else key
                if isinstance(value, bytes):
                    try:
                        decoded_value = int(value)
                    except ValueError:
                        decoded_value = value.decode()
                else:
                    decoded_value = value
                decoded_info[decoded_key] = decoded_value

            return decoded_info

        except Exception as e:
            logger.error("Failed to get stream info for %s: %s", stream_name, e)
            raise

    async def close(self) -> None:
        """Close Redis connection."""
        if self.redis:
            await self.redis.aclose()
            self._connected = False
            logger.info("Closed Redis connection")

    def _deserialize_event(self, event_data: dict[str, Any]) -> Event:
        """Deserialize event data to appropriate Event class."""
        from ..event.events import FillEvent
        from ..event.events import MarketDataEvent
        from ..event.events import OrderEvent
        from ..event.events import SignalEvent

        event_type = EventType(event_data["event_type"])

        # Map event types to their classes
        event_classes = {
            EventType.MARKET_DATA: MarketDataEvent,
            EventType.ORDER: OrderEvent,
            EventType.FILL: FillEvent,
            EventType.SIGNAL: SignalEvent,
        }

        event_class = event_classes.get(event_type)
        if not event_class:
            raise ValueError(f"Unknown event type: {event_type}")

        # Handle timestamp parsing
        if "timestamp" in event_data and isinstance(event_data["timestamp"], str):
            event_data["timestamp"] = datetime.fromisoformat(event_data["timestamp"])

        return event_class(**event_data)
