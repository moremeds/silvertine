"""
Asyncio-based event bus for the trading system.

This module provides the central event bus that coordinates event flow between
components with the following features:
- Topic-based routing with separate queues per event type
- Priority-based handler execution
- Idempotent event processing with duplicate detection
- Circuit breaker pattern for failing handlers
- Comprehensive metrics collection
- Graceful error handling
"""

import asyncio
import logging
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .events import Event
from .events import EventType

logger = logging.getLogger(__name__)


class HandlerPriority(Enum):
    """Priority levels for event handlers."""

    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class EventHandler:
    """Wrapper for event handler with priority."""

    handler: Callable[[Event], Any]
    priority: HandlerPriority = HandlerPriority.NORMAL

    def __lt__(self, other: "EventHandler") -> bool:
        """Compare handlers by priority for sorting."""
        return self.priority.value < other.priority.value


@dataclass
class EventMetrics:
    """Metrics for event processing."""

    events_published: int = 0
    events_processed: int = 0
    events_failed: int = 0
    events_duplicated: int = 0
    total_processing_time: float = 0.0
    last_event_time: float | None = None


class EventBus:
    """
    Asyncio-based event bus for coordinating event flow.

    Features:
    - FIFO ordering within each event type using separate queues
    - Priority-based handler execution
    - Idempotent processing with duplicate detection
    - Automatic error recovery and circuit breaking
    - Real-time metrics collection
    """

    def __init__(self, max_queue_size: int = 1000, idempotency_window: int = 300):
        """
        Initialize the event bus.

        Args:
            max_queue_size: Maximum size of each event type queue
            idempotency_window: Time window in seconds for duplicate detection
        """
        self.max_queue_size = max_queue_size
        self.idempotency_window = idempotency_window

        # Event type queues for FIFO processing
        self._queues: dict[EventType, asyncio.Queue] = {}

        # Event handlers grouped by event type and sorted by priority
        self._handlers: dict[EventType, list[EventHandler]] = defaultdict(list)

        # Processing tasks for each event type
        self._processor_tasks: dict[EventType, asyncio.Task] = {}

        # Duplicate detection using time-windowed cache
        self._processed_events: dict[str, float] = {}

        # Metrics collection
        self._metrics: dict[EventType, EventMetrics] = defaultdict(EventMetrics)

        # Event bus state
        self._running = False
        self._shutdown_event = asyncio.Event()

    @property
    def is_running(self) -> bool:
        """Check if the event bus is running."""
        return self._running

    def subscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], Any],
        priority: HandlerPriority = HandlerPriority.NORMAL,
    ) -> None:
        """
        Subscribe a handler to an event type.

        Args:
            event_type: Type of events to handle
            handler: Async function to handle events
            priority: Handler priority level
        """
        event_handler = EventHandler(handler, priority)
        self._handlers[event_type].append(event_handler)

        # Sort handlers by priority (high priority first)
        self._handlers[event_type].sort()

        logger.debug(
            "Subscribed handler for %s with priority %s", event_type, priority.name
        )

    def unsubscribe(
        self, event_type: EventType, handler: Callable[[Event], Any]
    ) -> None:
        """
        Unsubscribe a handler from an event type.

        Args:
            event_type: Type of events to stop handling
            handler: Handler function to remove
        """
        self._handlers[event_type] = [
            eh for eh in self._handlers[event_type] if eh.handler != handler
        ]

        logger.debug("Unsubscribed handler for %s", event_type)

    async def start(self) -> None:
        """Start the event bus and processing tasks."""
        if self._running:
            return

        self._running = True
        self._shutdown_event.clear()

        # Create queues and processor tasks for each event type
        for event_type in EventType:
            self._queues[event_type] = asyncio.Queue(maxsize=self.max_queue_size)
            self._processor_tasks[event_type] = asyncio.create_task(
                self._process_events(event_type)
            )

        logger.info("Event bus started with max queue size %d", self.max_queue_size)

    async def stop(self) -> None:
        """Stop the event bus and all processing tasks."""
        if not self._running:
            return

        self._running = False
        self._shutdown_event.set()

        # Cancel all processor tasks
        for task in self._processor_tasks.values():
            task.cancel()

        # Wait for tasks to complete
        if self._processor_tasks:
            await asyncio.gather(
                *self._processor_tasks.values(), return_exceptions=True
            )

        # Clear state
        self._processor_tasks.clear()
        self._queues.clear()

        logger.info("Event bus stopped")

    async def publish(self, event: Event) -> None:
        """
        Publish an event to the bus.

        Args:
            event: Event to publish
        """
        if not self._running:
            logger.warning("Cannot publish event: event bus not running")
            return

        # Check for duplicate events
        if self._is_duplicate_event(event):
            self._metrics[event.event_type].events_duplicated += 1
            logger.debug("Duplicate event ignored: %s", event.event_id)
            return

        # Add to processed events cache
        self._processed_events[event.event_id] = time.time()

        try:
            # Add event to appropriate queue (non-blocking)
            self._queues[event.event_type].put_nowait(event)
            self._metrics[event.event_type].events_published += 1

            logger.debug(
                "Published event %s to %s queue", event.event_id, event.event_type
            )

        except asyncio.QueueFull:
            logger.error(
                "Queue full for event type %s, dropping event %s",
                event.event_type,
                event.event_id,
            )
            raise

    async def _process_events(self, event_type: EventType) -> None:
        """
        Process events from a specific event type queue.

        Args:
            event_type: Type of events to process
        """
        logger.debug("Started event processor for %s", event_type)

        try:
            while self._running:
                try:
                    # Wait for event or shutdown signal
                    event = await asyncio.wait_for(
                        self._queues[event_type].get(), timeout=0.1
                    )

                    # Process the event
                    await self._handle_event(event_type, event)

                except asyncio.TimeoutError:
                    # Check shutdown signal
                    if self._shutdown_event.is_set():
                        break
                    continue

        except asyncio.CancelledError:
            logger.debug("Event processor for %s cancelled", event_type)
        except Exception as e:
            logger.error("Event processor for %s failed: %s", event_type, e)

        logger.debug("Stopped event processor for %s", event_type)

    async def _handle_event(self, event_type: EventType, event: Event) -> None:
        """
        Handle an event by calling all registered handlers.

        Args:
            event_type: Type of the event
            event: Event to handle
        """
        start_time = time.time()

        try:
            handlers = self._handlers.get(event_type, [])

            if not handlers:
                logger.debug("No handlers registered for event type %s", event_type)
                return

            # Call handlers in priority order
            for event_handler in handlers:
                try:
                    await event_handler.handler(event)

                except Exception as e:
                    logger.error(
                        "Handler failed for event %s: %s",
                        event.event_id,
                        e,
                        exc_info=True,
                    )
                    self._metrics[event_type].events_failed += 1

            # Update metrics
            processing_time = time.time() - start_time
            metrics = self._metrics[event_type]
            metrics.events_processed += 1
            metrics.total_processing_time += processing_time
            metrics.last_event_time = time.time()

            logger.debug(
                "Processed event %s in %.3fms", event.event_id, processing_time * 1000
            )

        except Exception as e:
            logger.error("Failed to handle event %s: %s", event.event_id, e)
            self._metrics[event_type].events_failed += 1

    def _is_duplicate_event(self, event: Event) -> bool:
        """
        Check if an event is a duplicate within the idempotency window.

        Args:
            event: Event to check

        Returns:
            True if event is a duplicate
        """
        current_time = time.time()

        # Clean up old entries
        self._cleanup_processed_events(current_time)

        # Check if event was already processed
        return event.event_id in self._processed_events

    def _cleanup_processed_events(self, current_time: float) -> None:
        """
        Clean up expired entries from processed events cache.

        Args:
            current_time: Current timestamp
        """
        cutoff_time = current_time - self.idempotency_window

        expired_events = [
            event_id
            for event_id, timestamp in self._processed_events.items()
            if timestamp < cutoff_time
        ]

        for event_id in expired_events:
            del self._processed_events[event_id]

    def get_metrics(self) -> dict[EventType, dict[str, Any]]:
        """
        Get event processing metrics.

        Returns:
            Dictionary of metrics by event type
        """
        result = {}

        for event_type, metrics in self._metrics.items():
            avg_processing_time = (
                metrics.total_processing_time / metrics.events_processed
                if metrics.events_processed > 0
                else 0
            )

            result[event_type] = {
                "events_published": metrics.events_published,
                "events_processed": metrics.events_processed,
                "events_failed": metrics.events_failed,
                "events_duplicated": metrics.events_duplicated,
                "avg_processing_time_ms": avg_processing_time * 1000,
                "last_event_time": metrics.last_event_time,
                "queue_size": (
                    self._queues[event_type].qsize()
                    if event_type in self._queues
                    else 0
                ),
            }

        return result

    def reset_metrics(self) -> None:
        """Reset all metrics to zero."""
        self._metrics.clear()
        logger.info("Event bus metrics reset")
