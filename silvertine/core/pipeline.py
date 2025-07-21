"""
Event processing pipeline that bridges Redis Streams and asyncio event bus.

This module provides the EventProcessor class that coordinates event flow between
Redis Streams (persistence layer) and the asyncio event bus (in-memory processing).

Key features:
- Bidirectional event flow: Redis → EventBus → Redis
- Backpressure handling and flow control
- Event transformation and validation
- Graceful shutdown with pending event handling
- Performance monitoring and metrics
"""

import asyncio
import logging
import time

from .event.event_bus import EventBus
from .event.events import Event
from .event.events import EventType
from .redis.redis_streams import RedisStreamManager

logger = logging.getLogger(__name__)


class PipelineConfig:
    """Configuration for the event processing pipeline."""

    def __init__(
        self,
        batch_size: int = 10,
        max_pending_events: int = 1000,
        process_interval: float = 0.1,
        backpressure_threshold: float = 0.8,
        enable_persistence: bool = True,
        enable_replay: bool = True,
    ):
        """
        Initialize pipeline configuration.

        Args:
            batch_size: Number of events to process in each batch
            max_pending_events: Maximum number of unprocessed events
            process_interval: Interval between processing cycles (seconds)
            backpressure_threshold: Threshold for backpressure activation (0.0-1.0)
            enable_persistence: Whether to persist events to Redis Streams
            enable_replay: Whether to enable event replay functionality
        """
        self.batch_size = batch_size
        self.max_pending_events = max_pending_events
        self.process_interval = process_interval
        self.backpressure_threshold = backpressure_threshold
        self.enable_persistence = enable_persistence
        self.enable_replay = enable_replay


class PipelineMetrics:
    """Metrics collection for pipeline performance."""

    def __init__(self):
        self.events_ingested = 0
        self.events_processed = 0
        self.events_failed = 0
        self.events_persisted = 0
        self.backpressure_events = 0
        self.processing_time_total = 0.0
        self.last_activity: float | None = None
        self.start_time = time.time()

    @property
    def uptime(self) -> float:
        """Get pipeline uptime in seconds."""
        return time.time() - self.start_time

    @property
    def events_per_second(self) -> float:
        """Calculate events processed per second."""
        if self.uptime > 0:
            return self.events_processed / self.uptime
        return 0.0

    @property
    def average_processing_time(self) -> float:
        """Calculate average processing time per event."""
        if self.events_processed > 0:
            return self.processing_time_total / self.events_processed
        return 0.0

    def to_dict(self) -> dict[str, int | float | None]:
        """Convert metrics to dictionary."""
        return {
            "events_ingested": self.events_ingested,
            "events_processed": self.events_processed,
            "events_failed": self.events_failed,
            "events_persisted": self.events_persisted,
            "backpressure_events": self.backpressure_events,
            "uptime_seconds": self.uptime,
            "events_per_second": self.events_per_second,
            "avg_processing_time_ms": self.average_processing_time * 1000,
            "last_activity": self.last_activity,
        }


class EventProcessor:
    """
    Event processing pipeline that coordinates between Redis Streams and EventBus.

    Responsibilities:
    - Ingest events from external sources and route to event bus
    - Persist events from event bus to Redis Streams
    - Handle backpressure and flow control
    - Provide event replay and recovery capabilities
    - Monitor pipeline performance and health
    """

    def __init__(
        self,
        event_bus: EventBus,
        redis_manager: RedisStreamManager,
        config: PipelineConfig,
    ):
        """
        Initialize the event processor.

        Args:
            event_bus: AsyncIO event bus for in-memory processing
            redis_manager: Redis streams manager for persistence
            config: Pipeline configuration
        """
        self.event_bus = event_bus
        self.redis_manager = redis_manager
        self.config = config

        # Pipeline state
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._pending_events: dict[EventType, list[Event]] = {}
        self._processing_tasks: list[asyncio.Task] = []

        # Metrics and monitoring
        self.metrics = PipelineMetrics()

        # Initialize pending events storage
        for event_type in EventType:
            self._pending_events[event_type] = []

    @property
    def is_running(self) -> bool:
        """Check if the pipeline is running."""
        return self._running

    @property
    def pending_event_count(self) -> int:
        """Get total number of pending events."""
        return sum(len(events) for events in self._pending_events.values())

    @property
    def is_backpressure_active(self) -> bool:
        """Check if backpressure is currently active."""
        utilization = self.pending_event_count / self.config.max_pending_events
        return utilization >= self.config.backpressure_threshold

    async def start(self) -> None:
        """Start the event processing pipeline."""
        if self._running:
            logger.warning("Pipeline is already running")
            return

        logger.info("Starting event processing pipeline")

        # Ensure dependencies are started
        if not self.event_bus.is_running:
            await self.event_bus.start()

        if not self.redis_manager.is_connected:
            await self.redis_manager.connect()

        # Create Redis streams if persistence is enabled
        if self.config.enable_persistence:
            await self.redis_manager.create_streams()

        # Start processing tasks
        self._running = True
        self._shutdown_event.clear()

        # Start ingestion task (Redis → EventBus)
        ingestion_task = asyncio.create_task(self._ingestion_loop())
        self._processing_tasks.append(ingestion_task)

        # Start persistence task (EventBus → Redis)
        if self.config.enable_persistence:
            persistence_task = asyncio.create_task(self._persistence_loop())
            self._processing_tasks.append(persistence_task)

        # Subscribe to event bus for outbound events
        for event_type in EventType:
            self.event_bus.subscribe(event_type, self._handle_outbound_event)

        logger.info(
            "Pipeline started with batch_size=%d, max_pending=%d",
            self.config.batch_size,
            self.config.max_pending_events,
        )

    async def stop(self) -> None:
        """Stop the event processing pipeline gracefully."""
        if not self._running:
            logger.warning("Pipeline is not running")
            return

        logger.info("Stopping event processing pipeline")

        # Signal shutdown
        self._running = False
        self._shutdown_event.set()

        # Cancel all processing tasks
        for task in self._processing_tasks:
            task.cancel()

        # Wait for tasks to complete
        if self._processing_tasks:
            await asyncio.gather(*self._processing_tasks, return_exceptions=True)

        # Process any remaining pending events
        await self._flush_pending_events()

        # Unsubscribe from event bus
        for event_type in EventType:
            try:
                self.event_bus.unsubscribe(event_type, self._handle_outbound_event)
            except Exception as e:
                logger.warning("Failed to unsubscribe from %s: %s", event_type, e)

        # Clear state
        self._processing_tasks.clear()
        for event_type in EventType:
            self._pending_events[event_type].clear()

        logger.info("Pipeline stopped")

    async def ingest_event(self, event: Event) -> None:
        """
        Ingest an event from external source into the pipeline.

        Args:
            event: Event to ingest

        Raises:
            RuntimeError: If pipeline is not running
            ValueError: If backpressure threshold is exceeded
        """
        if not self._running:
            raise RuntimeError("Pipeline is not running")

        # Check backpressure
        if self.is_backpressure_active:
            self.metrics.backpressure_events += 1
            logger.warning(
                "Backpressure active, rejecting event %s (pending: %d/%d)",
                event.event_id,
                self.pending_event_count,
                self.config.max_pending_events,
            )
            raise ValueError("Pipeline backpressure active")

        # Add to pending events
        self._pending_events[event.event_type].append(event)
        self.metrics.events_ingested += 1
        self.metrics.last_activity = time.time()

        logger.debug(
            "Ingested event %s of type %s (pending: %d)",
            event.event_id,
            event.event_type,
            self.pending_event_count,
        )

    async def replay_events(
        self, event_type: EventType, start_time, end_time, max_events: int = 1000
    ) -> list[Event]:
        """
        Replay events from Redis Streams.

        Args:
            event_type: Type of events to replay
            start_time: Start time for replay
            end_time: End time for replay
            max_events: Maximum number of events to replay

        Returns:
            List of replayed events
        """
        if not self.config.enable_replay:
            raise RuntimeError("Event replay is disabled")

        if not self.redis_manager.is_connected:
            raise RuntimeError("Redis manager is not connected")

        logger.info(
            "Replaying events of type %s from %s to %s (max: %d)",
            event_type,
            start_time,
            end_time,
            max_events,
        )

        events_with_ids = await self.redis_manager.replay_events(
            event_type, start_time, end_time, max_events
        )

        events = [event for event, _ in events_with_ids]

        logger.info("Replayed %d events of type %s", len(events), event_type)
        return events

    async def _ingestion_loop(self) -> None:
        """Process ingested events and route to event bus."""
        logger.debug("Starting ingestion loop")

        try:
            while self._running:
                try:
                    # Process events from Redis Streams if enabled
                    if self.config.enable_persistence:
                        await self._consume_from_redis()

                    # Process pending events to event bus
                    await self._process_pending_events()

                    # Wait before next cycle
                    await asyncio.sleep(self.config.process_interval)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error("Error in ingestion loop: %s", e, exc_info=True)
                    await asyncio.sleep(1.0)  # Back off on error

        except asyncio.CancelledError:
            logger.debug("Ingestion loop cancelled")
        except Exception as e:
            logger.error("Ingestion loop failed: %s", e, exc_info=True)

        logger.debug("Ingestion loop stopped")

    async def _persistence_loop(self) -> None:
        """Handle persistence of events to Redis Streams."""
        logger.debug("Starting persistence loop")

        try:
            while self._running:
                try:
                    # This loop primarily handles acknowledgments and cleanup
                    # Actual persistence happens in _handle_outbound_event
                    await asyncio.sleep(self.config.process_interval)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error("Error in persistence loop: %s", e, exc_info=True)
                    await asyncio.sleep(1.0)  # Back off on error

        except asyncio.CancelledError:
            logger.debug("Persistence loop cancelled")
        except Exception as e:
            logger.error("Persistence loop failed: %s", e, exc_info=True)

        logger.debug("Persistence loop stopped")

    async def _consume_from_redis(self) -> None:
        """Consume events from Redis Streams."""
        try:
            # Consume from all event types
            events_with_ids = await self.redis_manager.consume_events(
                list(EventType), count=self.config.batch_size
            )

            for event, message_id in events_with_ids:
                # Route to event bus
                await self.event_bus.publish(event)

                # Acknowledge message
                await self.redis_manager.acknowledge_message(
                    event.event_type, message_id
                )

                self.metrics.events_processed += 1

        except Exception as e:
            logger.error("Failed to consume from Redis: %s", e)

    async def _process_pending_events(self) -> None:
        """Process pending events and route to event bus."""
        start_time = time.time()
        events_processed = 0

        try:
            for event_type in EventType:
                pending = self._pending_events[event_type]
                if not pending:
                    continue

                # Process batch of events
                batch_size = min(len(pending), self.config.batch_size)
                batch = pending[:batch_size]

                for event in batch:
                    try:
                        # Route to event bus
                        await self.event_bus.publish(event)
                        events_processed += 1
                        self.metrics.events_processed += 1

                    except Exception as e:
                        logger.error(
                            "Failed to process event %s: %s", event.event_id, e
                        )
                        self.metrics.events_failed += 1

                # Remove processed events from pending
                self._pending_events[event_type] = pending[batch_size:]

        except Exception as e:
            logger.error("Error processing pending events: %s", e)

        # Update metrics
        processing_time = time.time() - start_time
        self.metrics.processing_time_total += processing_time

        if events_processed > 0:
            self.metrics.last_activity = time.time()
            logger.debug(
                "Processed %d events in %.3fms",
                events_processed,
                processing_time * 1000,
            )

    async def _handle_outbound_event(self, event: Event) -> None:
        """Handle events published to the event bus for persistence."""
        if not self.config.enable_persistence:
            return

        try:
            # Persist to Redis Streams
            await self.redis_manager.publish_event(event)
            self.metrics.events_persisted += 1

            logger.debug("Persisted event %s to Redis", event.event_id)

        except Exception as e:
            logger.error("Failed to persist event %s: %s", event.event_id, e)

    async def _flush_pending_events(self) -> None:
        """Process all remaining pending events during shutdown."""
        total_pending = self.pending_event_count
        if total_pending == 0:
            return

        logger.info("Flushing %d pending events during shutdown", total_pending)

        start_time = time.time()
        try:
            await self._process_pending_events()
        except Exception as e:
            logger.error("Error flushing pending events: %s", e)

        flush_time = time.time() - start_time
        remaining = self.pending_event_count

        logger.info(
            "Flushed %d/%d pending events in %.3fs (%d remaining)",
            total_pending - remaining,
            total_pending,
            flush_time,
            remaining,
        )

    def get_metrics(self) -> dict[str, int | float | None]:
        """Get pipeline performance metrics."""
        return self.metrics.to_dict()

    def reset_metrics(self) -> None:
        """Reset all pipeline metrics."""
        self.metrics = PipelineMetrics()
        logger.info("Pipeline metrics reset")
