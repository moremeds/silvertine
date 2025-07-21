"""
Monitoring and replay system for the event-driven trading engine.

This module provides comprehensive monitoring capabilities including:
- Real-time performance metrics collection
- System health checks and alerting
- Component status monitoring
- Event replay functionality
- Resource usage tracking
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone
from enum import Enum
from typing import Any

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from .event.event_bus import EventBus
from .event.events import Event
from .event.events import EventType
from .pipeline import EventProcessor
from .redis.redis_streams import RedisStreamManager

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels for system components."""

    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertLevel(Enum):
    """Alert severity levels."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class MonitoringConfig:
    """Configuration for system monitoring."""

    health_check_interval: float = 60.0  # seconds
    metrics_collection_interval: float = 5.0  # seconds
    alert_thresholds: dict[str, float] = field(
        default_factory=lambda: {
            "event_queue_size": 1000,
            "processing_latency_ms": 1000,
            "error_rate_percent": 5.0,
            "memory_usage_mb": 1000,
            "cpu_usage_percent": 80.0,
        }
    )
    enable_performance_logging: bool = True
    enable_health_checks: bool = True
    enable_resource_monitoring: bool = True


@dataclass
class PerformanceMetrics:
    """System performance metrics."""

    total_events_processed: int = 0
    total_processing_time: float = 0.0
    error_count: int = 0
    queue_sizes: dict[str, int] = field(default_factory=dict)
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    start_time: float = field(default_factory=time.time)

    @property
    def uptime_seconds(self) -> float:
        """Get system uptime in seconds."""
        return time.time() - self.start_time

    @property
    def events_per_second(self) -> float:
        """Calculate events processed per second."""
        if self.uptime_seconds > 0:
            return self.total_events_processed / self.uptime_seconds
        return 0.0

    @property
    def average_processing_time_ms(self) -> float:
        """Calculate average processing time per event in milliseconds."""
        if self.total_events_processed > 0:
            return (self.total_processing_time / self.total_events_processed) * 1000
        return 0.0

    @property
    def error_rate_percent(self) -> float:
        """Calculate error rate as percentage."""
        if self.total_events_processed > 0:
            return (self.error_count / self.total_events_processed) * 100
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_events_processed": self.total_events_processed,
            "total_processing_time": self.total_processing_time,
            "error_count": self.error_count,
            "queue_sizes": self.queue_sizes,
            "memory_usage_mb": self.memory_usage_mb,
            "cpu_usage_percent": self.cpu_usage_percent,
            "uptime_seconds": self.uptime_seconds,
            "events_per_second": self.events_per_second,
            "average_processing_time_ms": self.average_processing_time_ms,
            "error_rate_percent": self.error_rate_percent,
        }


@dataclass
class SystemHealth:
    """System health status information."""

    overall_status: HealthStatus
    component_health: dict[str, HealthStatus]
    active_alerts: list[str]
    last_check_time: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert health status to dictionary."""
        return {
            "overall_status": self.overall_status.value,
            "component_health": {k: v.value for k, v in self.component_health.items()},
            "active_alerts": self.active_alerts,
            "last_check_time": self.last_check_time.isoformat(),
        }


class SystemMonitor:
    """
    Comprehensive monitoring system for the event-driven trading engine.

    Provides:
    - Real-time performance metrics collection
    - System health monitoring and alerting
    - Component status tracking
    - Event replay capabilities
    - Resource usage monitoring
    """

    def __init__(
        self,
        event_bus: EventBus,
        redis_manager: RedisStreamManager,
        pipeline: EventProcessor,
        config: MonitoringConfig,
    ):
        """
        Initialize the system monitor.

        Args:
            event_bus: The event bus to monitor
            redis_manager: Redis streams manager to monitor
            pipeline: Event processing pipeline to monitor
            config: Monitoring configuration
        """
        self.event_bus = event_bus
        self.redis_manager = redis_manager
        self.pipeline = pipeline
        self.config = config

        # Monitoring state
        self._running = False
        self._monitoring_tasks: list[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()

        # Metrics collection
        self._performance_metrics = PerformanceMetrics()
        self._system_health = SystemHealth(
            overall_status=HealthStatus.HEALTHY,
            component_health={},
            active_alerts=[],
            last_check_time=datetime.now(timezone.utc),
        )

        logger.info("SystemMonitor initialized with config: %s", config)

    @property
    def is_running(self) -> bool:
        """Check if the monitor is running."""
        return self._running

    async def start(self) -> None:
        """Start the monitoring system."""
        if self._running:
            logger.warning("Monitor is already running")
            return

        logger.info("Starting system monitoring")

        self._running = True
        self._shutdown_event.clear()

        # Start monitoring tasks
        if self.config.enable_performance_logging:
            metrics_task = asyncio.create_task(self._metrics_collection_loop())
            self._monitoring_tasks.append(metrics_task)

        if self.config.enable_health_checks:
            health_task = asyncio.create_task(self._health_check_loop())
            self._monitoring_tasks.append(health_task)

        logger.info(
            "System monitoring started with %d tasks", len(self._monitoring_tasks)
        )

    async def stop(self) -> None:
        """Stop the monitoring system gracefully."""
        if not self._running:
            logger.warning("Monitor is not running")
            return

        logger.info("Stopping system monitoring")

        # Signal shutdown
        self._running = False
        self._shutdown_event.set()

        # Cancel all monitoring tasks
        for task in self._monitoring_tasks:
            task.cancel()

        # Wait for tasks to complete
        if self._monitoring_tasks:
            await asyncio.gather(*self._monitoring_tasks, return_exceptions=True)

        # Clear state
        self._monitoring_tasks.clear()

        logger.info("System monitoring stopped")

    async def get_performance_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics."""
        await self._collect_metrics()
        return self._performance_metrics

    async def get_system_health(self) -> SystemHealth:
        """Get current system health status."""
        await self._check_system_health()
        return self._system_health

    async def get_system_status(self) -> dict[str, Any]:
        """Get comprehensive system status summary."""
        metrics = await self.get_performance_metrics()
        health = await self.get_system_health()

        return {
            "performance_metrics": metrics.to_dict(),
            "system_health": health.to_dict(),
            "component_status": {
                "event_bus_running": self.event_bus.is_running,
                "redis_connected": self.redis_manager.is_connected,
                "pipeline_running": self.pipeline.is_running,
                "monitor_running": self.is_running,
            },
        }

    async def replay_events(
        self,
        event_type: EventType,
        start_time: datetime,
        end_time: datetime,
        max_events: int = 1000,
    ) -> list[Event]:
        """
        Replay events from the specified time range.

        Args:
            event_type: Type of events to replay
            start_time: Start time for replay
            end_time: End time for replay
            max_events: Maximum number of events to replay

        Returns:
            List of replayed events
        """
        logger.info(
            "Replaying events: type=%s, start=%s, end=%s, max=%d",
            event_type,
            start_time,
            end_time,
            max_events,
        )

        try:
            events = await self.pipeline.replay_events(
                event_type, start_time, end_time, max_events
            )

            logger.info("Successfully replayed %d events", len(events))
            return events

        except Exception as e:
            logger.error("Failed to replay events: %s", e)
            raise

    async def _metrics_collection_loop(self) -> None:
        """Main loop for collecting performance metrics."""
        logger.debug("Starting metrics collection loop")

        try:
            while self._running:
                try:
                    await self._collect_metrics()

                    if self.config.enable_performance_logging:
                        logger.debug(
                            "Metrics: events/sec=%.2f, error_rate=%.2f%%, queue_sizes=%s",
                            self._performance_metrics.events_per_second,
                            self._performance_metrics.error_rate_percent,
                            self._performance_metrics.queue_sizes,
                        )

                    await asyncio.sleep(self.config.metrics_collection_interval)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error("Error in metrics collection: %s", e, exc_info=True)
                    await asyncio.sleep(1.0)  # Back off on error

        except asyncio.CancelledError:
            logger.debug("Metrics collection loop cancelled")

        logger.debug("Metrics collection loop stopped")

    async def _health_check_loop(self) -> None:
        """Main loop for health checks and alerting."""
        logger.debug("Starting health check loop")

        try:
            while self._running:
                try:
                    await self._check_system_health()

                    # Log health status changes
                    if self._system_health.active_alerts:
                        logger.warning(
                            "Health check alerts: %s",
                            ", ".join(self._system_health.active_alerts),
                        )

                    await asyncio.sleep(self.config.health_check_interval)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error("Error in health check: %s", e, exc_info=True)
                    await asyncio.sleep(1.0)  # Back off on error

        except asyncio.CancelledError:
            logger.debug("Health check loop cancelled")

        logger.debug("Health check loop stopped")

    async def _collect_metrics(self) -> None:
        """Collect performance metrics from all components."""
        try:
            # Collect event bus metrics
            bus_metrics = self.event_bus.get_metrics()
            total_events = sum(
                metrics.get("events_processed", 0) for metrics in bus_metrics.values()
            )
            total_errors = sum(
                metrics.get("events_failed", 0) for metrics in bus_metrics.values()
            )

            # Collect queue sizes
            queue_sizes = {}
            for event_type, metrics in bus_metrics.items():
                queue_sizes[event_type.name] = metrics.get("queue_size", 0)

            # Collect pipeline metrics
            pipeline_metrics = self.pipeline.get_metrics()
            pipeline_events = pipeline_metrics.get("events_processed", 0)
            pipeline_errors = pipeline_metrics.get("events_failed", 0)

            # Update performance metrics
            self._performance_metrics.total_events_processed = int(
                total_events + (pipeline_events or 0)
            )
            self._performance_metrics.error_count = int(total_errors + (pipeline_errors or 0))
            self._performance_metrics.queue_sizes = queue_sizes

            # Collect system resource metrics if available
            if PSUTIL_AVAILABLE and self.config.enable_resource_monitoring:
                memory = psutil.virtual_memory()
                self._performance_metrics.memory_usage_mb = memory.used / (1024 * 1024)
                self._performance_metrics.cpu_usage_percent = psutil.cpu_percent()

        except Exception as e:
            logger.error("Failed to collect metrics: %s", e)
            raise

    async def _check_system_health(self) -> None:
        """Check system health and generate alerts."""
        component_health = {}
        active_alerts = []

        try:
            # Check event bus health
            try:
                if self.event_bus.is_running:
                    # Try to get metrics to verify health
                    self.event_bus.get_metrics()
                    component_health["event_bus"] = HealthStatus.HEALTHY
                else:
                    component_health["event_bus"] = HealthStatus.CRITICAL
                    active_alerts.append("Event bus is not running")
            except Exception as e:
                component_health["event_bus"] = HealthStatus.CRITICAL
                active_alerts.append(f"Event bus health check failed: {str(e)}")

            # Check Redis connection health
            if self.redis_manager.is_connected:
                component_health["redis_streams"] = HealthStatus.HEALTHY
            else:
                component_health["redis_streams"] = HealthStatus.CRITICAL
                active_alerts.append("Redis streams disconnected")

            # Check pipeline health
            if self.pipeline.is_running:
                component_health["pipeline"] = HealthStatus.HEALTHY
            else:
                component_health["pipeline"] = HealthStatus.CRITICAL
                active_alerts.append("Event processing pipeline is not running")

            # Check performance thresholds
            await self._check_performance_thresholds(active_alerts)

            # Determine overall health status
            overall_status = HealthStatus.HEALTHY
            if any(
                status == HealthStatus.CRITICAL for status in component_health.values()
            ):
                overall_status = HealthStatus.CRITICAL
            elif any(
                status == HealthStatus.WARNING for status in component_health.values()
            ):
                overall_status = HealthStatus.WARNING

            # Update system health
            self._system_health = SystemHealth(
                overall_status=overall_status,
                component_health=component_health,
                active_alerts=active_alerts,
                last_check_time=datetime.now(timezone.utc),
            )

        except Exception as e:
            logger.error("Failed to check system health: %s", e)
            # Set critical status on error
            self._system_health = SystemHealth(
                overall_status=HealthStatus.CRITICAL,
                component_health={"monitor": HealthStatus.CRITICAL},
                active_alerts=[f"Health check failed: {str(e)}"],
                last_check_time=datetime.now(timezone.utc),
            )

    async def _check_performance_thresholds(self, active_alerts: list[str]) -> None:
        """Check performance metrics against configured thresholds."""
        thresholds = self.config.alert_thresholds

        # Check queue sizes
        for queue_name, size in self._performance_metrics.queue_sizes.items():
            if size > thresholds.get("event_queue_size", float("inf")):
                active_alerts.append(f"High queue size in {queue_name}: {size}")

        # Check error rate
        if self._performance_metrics.error_rate_percent > thresholds.get(
            "error_rate_percent", 100
        ):
            active_alerts.append(
                f"High error rate: {self._performance_metrics.error_rate_percent:.2f}%"
            )

        # Check processing latency
        if self._performance_metrics.average_processing_time_ms > thresholds.get(
            "processing_latency_ms", float("inf")
        ):
            active_alerts.append(
                f"High processing latency: {self._performance_metrics.average_processing_time_ms:.2f}ms"
            )

        # Check resource usage if monitoring is enabled
        if self.config.enable_resource_monitoring:
            if self._performance_metrics.memory_usage_mb > thresholds.get(
                "memory_usage_mb", float("inf")
            ):
                active_alerts.append(
                    f"High memory usage: {self._performance_metrics.memory_usage_mb:.1f}MB"
                )

            if self._performance_metrics.cpu_usage_percent > thresholds.get(
                "cpu_usage_percent", 100
            ):
                active_alerts.append(
                    f"High CPU usage: {self._performance_metrics.cpu_usage_percent:.1f}%"
                )
