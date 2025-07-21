"""
Unit tests for the monitoring and replay system.
"""

import asyncio
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from decimal import Decimal
from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest

from silvertine.core.event.event_bus import EventBus
from silvertine.core.event.events import EventType
from silvertine.core.event.events import MarketDataEvent
from silvertine.core.monitoring import HealthStatus
from silvertine.core.monitoring import MonitoringConfig
from silvertine.core.monitoring import PerformanceMetrics
from silvertine.core.monitoring import SystemHealth
from silvertine.core.monitoring import SystemMonitor
from silvertine.core.pipeline import EventProcessor
from silvertine.core.redis.redis_streams import RedisStreamManager


class TestMonitoringConfig:
    """Test the MonitoringConfig class."""

    def test_monitoring_config_creation(self):
        """Test creating a monitoring configuration."""
        config = MonitoringConfig(
            health_check_interval=30.0,
            metrics_collection_interval=10.0,
            alert_thresholds={
                "event_queue_size": 500,
                "processing_latency_ms": 1000,
                "error_rate_percent": 5.0,
            },
            enable_performance_logging=True,
            enable_health_checks=True,
        )

        assert config.health_check_interval == 30.0
        assert config.metrics_collection_interval == 10.0
        assert config.alert_thresholds["event_queue_size"] == 500
        assert config.enable_performance_logging is True
        assert config.enable_health_checks is True

    def test_monitoring_config_defaults(self):
        """Test monitoring configuration with default values."""
        config = MonitoringConfig()

        assert config.health_check_interval == 60.0
        assert config.metrics_collection_interval == 5.0
        assert "event_queue_size" in config.alert_thresholds
        assert config.enable_performance_logging is True
        assert config.enable_health_checks is True


class TestPerformanceMetrics:
    """Test the PerformanceMetrics class."""

    def test_performance_metrics_creation(self):
        """Test creating performance metrics."""
        metrics = PerformanceMetrics()

        assert metrics.total_events_processed == 0
        assert metrics.total_processing_time == 0.0
        assert metrics.error_count == 0
        assert metrics.queue_sizes == {}
        assert metrics.memory_usage_mb == 0.0
        assert metrics.cpu_usage_percent == 0.0
        assert isinstance(metrics.start_time, float)

    def test_performance_metrics_calculations(self):
        """Test performance metrics calculations."""
        metrics = PerformanceMetrics()

        # Simulate some processing
        metrics.total_events_processed = 1000
        metrics.total_processing_time = 10.0
        metrics.error_count = 5

        assert metrics.events_per_second > 0  # Based on uptime
        assert metrics.average_processing_time_ms == 10.0  # 10.0 / 1000 * 1000
        assert metrics.error_rate_percent == 0.5  # 5 / 1000 * 100

    def test_performance_metrics_to_dict(self):
        """Test converting performance metrics to dictionary."""
        metrics = PerformanceMetrics()
        metrics.total_events_processed = 100
        metrics.error_count = 2

        result = metrics.to_dict()

        assert "total_events_processed" in result
        assert "error_count" in result
        assert "events_per_second" in result
        assert "error_rate_percent" in result
        assert result["total_events_processed"] == 100
        assert result["error_count"] == 2


class TestSystemHealth:
    """Test the SystemHealth class."""

    def test_system_health_creation(self):
        """Test creating system health status."""
        health = SystemHealth(
            overall_status=HealthStatus.HEALTHY,
            component_health={
                "event_bus": HealthStatus.HEALTHY,
                "redis_streams": HealthStatus.WARNING,
                "pipeline": HealthStatus.HEALTHY,
            },
            active_alerts=[],
            last_check_time=datetime.now(timezone.utc),
        )

        assert health.overall_status == HealthStatus.HEALTHY
        assert health.component_health["event_bus"] == HealthStatus.HEALTHY
        assert health.component_health["redis_streams"] == HealthStatus.WARNING
        assert len(health.active_alerts) == 0

    def test_system_health_to_dict(self):
        """Test converting system health to dictionary."""
        health = SystemHealth(
            overall_status=HealthStatus.WARNING,
            component_health={"event_bus": HealthStatus.HEALTHY},
            active_alerts=["High queue size"],
            last_check_time=datetime.now(timezone.utc),
        )

        result = health.to_dict()

        assert "overall_status" in result
        assert "component_health" in result
        assert "active_alerts" in result
        assert result["overall_status"] == "WARNING"


class TestSystemMonitor:
    """Test the SystemMonitor class."""

    @pytest.fixture
    def mock_event_bus(self):
        """Create a mock event bus."""
        mock_bus = AsyncMock(spec=EventBus)
        mock_bus.is_running = True
        mock_bus.get_metrics.return_value = {
            EventType.MARKET_DATA: {
                "events_published": 100,
                "events_processed": 98,
                "events_failed": 2,
                "queue_size": 10,
            }
        }
        return mock_bus

    @pytest.fixture
    def mock_redis_manager(self):
        """Create a mock Redis stream manager."""
        mock_manager = AsyncMock(spec=RedisStreamManager)
        mock_manager.is_connected = True
        mock_manager.get_stream_info.return_value = {
            "length": 1000,
            "groups": 1,
            "last-generated-id": "1234567890-5",
        }
        return mock_manager

    @pytest.fixture
    def mock_pipeline(self):
        """Create a mock pipeline."""
        mock_pipeline = AsyncMock(spec=EventProcessor)
        mock_pipeline.is_running = True
        mock_pipeline.get_metrics.return_value = {
            "events_ingested": 150,
            "events_processed": 145,
            "events_failed": 5,
            "uptime_seconds": 3600.0,
            "events_per_second": 0.04,
        }
        return mock_pipeline

    @pytest.fixture
    def monitoring_config(self):
        """Create a test monitoring configuration."""
        return MonitoringConfig(
            health_check_interval=1.0,  # Fast for testing
            metrics_collection_interval=0.5,  # Fast for testing
            alert_thresholds={
                "event_queue_size": 50,
                "processing_latency_ms": 500,
                "error_rate_percent": 2.0,
            },
        )

    @pytest.fixture
    def system_monitor(
        self, mock_event_bus, mock_redis_manager, mock_pipeline, monitoring_config
    ):
        """Create a SystemMonitor instance."""
        return SystemMonitor(
            event_bus=mock_event_bus,
            redis_manager=mock_redis_manager,
            pipeline=mock_pipeline,
            config=monitoring_config,
        )

    async def test_monitor_creation(self, system_monitor):
        """Test creating a system monitor."""
        assert not system_monitor.is_running
        assert isinstance(system_monitor.config, MonitoringConfig)
        assert system_monitor.event_bus is not None
        assert system_monitor.redis_manager is not None
        assert system_monitor.pipeline is not None

    async def test_monitor_start_stop_lifecycle(self, system_monitor):
        """Test monitor start/stop lifecycle."""
        assert not system_monitor.is_running

        # Start monitor
        await system_monitor.start()
        assert system_monitor.is_running
        assert len(system_monitor._monitoring_tasks) >= 1

        # Stop monitor
        await system_monitor.stop()
        assert not system_monitor.is_running
        assert len(system_monitor._monitoring_tasks) == 0

    async def test_performance_metrics_collection(self, system_monitor):
        """Test collection of performance metrics."""
        await system_monitor.start()

        # Give monitoring time to collect metrics
        await asyncio.sleep(0.1)

        metrics = await system_monitor.get_performance_metrics()

        assert isinstance(metrics, PerformanceMetrics)
        assert metrics.total_events_processed > 0
        assert "MARKET_DATA" in metrics.queue_sizes

        await system_monitor.stop()

    async def test_health_check_execution(self, system_monitor):
        """Test health check execution."""
        await system_monitor.start()

        # Give monitoring time to perform health checks
        await asyncio.sleep(0.1)

        health = await system_monitor.get_system_health()

        assert isinstance(health, SystemHealth)
        assert health.overall_status in [
            HealthStatus.HEALTHY,
            HealthStatus.WARNING,
            HealthStatus.CRITICAL,
        ]
        assert "event_bus" in health.component_health
        assert "redis_streams" in health.component_health
        assert "pipeline" in health.component_health

        await system_monitor.stop()

    async def test_alert_generation(self, system_monitor, mock_event_bus):
        """Test alert generation for threshold violations."""
        # Set up conditions that should trigger alerts
        mock_event_bus.get_metrics.return_value = {
            EventType.MARKET_DATA: {
                "events_published": 100,
                "events_processed": 90,
                "events_failed": 10,  # High error rate
                "queue_size": 100,  # High queue size
            }
        }

        await system_monitor.start()

        # Give monitoring time to detect issues
        await asyncio.sleep(0.1)

        health = await system_monitor.get_system_health()

        # Should have alerts for high error rate and queue size
        assert len(health.active_alerts) > 0
        alert_messages = " ".join(health.active_alerts)
        assert (
            "error rate" in alert_messages.lower()
            or "queue size" in alert_messages.lower()
        )

        await system_monitor.stop()

    async def test_component_health_assessment(
        self, system_monitor, mock_redis_manager
    ):
        """Test individual component health assessment."""
        # Test unhealthy Redis component
        mock_redis_manager.is_connected = False

        await system_monitor.start()
        await asyncio.sleep(0.1)

        health = await system_monitor.get_system_health()

        assert health.component_health["redis_streams"] == HealthStatus.CRITICAL
        assert health.overall_status in [HealthStatus.WARNING, HealthStatus.CRITICAL]

        await system_monitor.stop()

    async def test_event_replay_integration(self, system_monitor, mock_pipeline):
        """Test event replay functionality integration."""
        # Mock replay events
        start_time = datetime.now(timezone.utc) - timedelta(hours=1)
        end_time = datetime.now(timezone.utc)

        mock_market_data = MarketDataEvent(
            symbol="BTCUSDT", price=Decimal("50000.00"), volume=Decimal("1.5")
        )
        mock_pipeline.replay_events.return_value = [mock_market_data]

        events = await system_monitor.replay_events(
            EventType.MARKET_DATA, start_time, end_time, max_events=100
        )

        assert len(events) == 1
        assert isinstance(events[0], MarketDataEvent)
        mock_pipeline.replay_events.assert_called_once_with(
            EventType.MARKET_DATA, start_time, end_time, 100
        )

    async def test_system_status_summary(self, system_monitor):
        """Test getting system status summary."""
        await system_monitor.start()
        await asyncio.sleep(0.1)

        summary = await system_monitor.get_system_status()

        assert "performance_metrics" in summary
        assert "system_health" in summary
        assert "component_status" in summary
        assert isinstance(summary["performance_metrics"], dict)
        assert isinstance(summary["system_health"], dict)

        await system_monitor.stop()

    @patch("silvertine.core.monitoring.PSUTIL_AVAILABLE", True)
    @patch("silvertine.core.monitoring.psutil.virtual_memory")
    @patch("silvertine.core.monitoring.psutil.cpu_percent")
    async def test_system_resource_monitoring(
        self, mock_cpu, mock_memory, system_monitor
    ):
        """Test system resource monitoring."""
        # Mock system resource calls
        mock_memory.return_value.used = 1024 * 1024 * 512  # 512 MB
        mock_cpu.return_value = 25.5  # 25.5% CPU usage

        await system_monitor.start()
        await asyncio.sleep(0.1)

        metrics = await system_monitor.get_performance_metrics()

        assert metrics.memory_usage_mb == 512.0
        assert metrics.cpu_usage_percent == 25.5

        await system_monitor.stop()

    async def test_monitoring_error_handling(self, system_monitor, mock_event_bus):
        """Test error handling in monitoring operations."""
        # Make metrics collection fail
        mock_event_bus.get_metrics.side_effect = Exception("Metrics failed")

        await system_monitor.start()
        await asyncio.sleep(0.1)

        # Should handle errors gracefully
        health = await system_monitor.get_system_health()
        assert health.component_health["event_bus"] == HealthStatus.CRITICAL

        await system_monitor.stop()

    async def test_double_start_stop(self, system_monitor):
        """Test that multiple start/stop calls are handled gracefully."""
        # Multiple starts should be safe
        await system_monitor.start()
        await system_monitor.start()  # Should not crash
        assert system_monitor.is_running

        # Multiple stops should be safe
        await system_monitor.stop()
        await system_monitor.stop()  # Should not crash
        assert not system_monitor.is_running
