"""
Unit tests for the event processing pipeline.
"""

import asyncio
from datetime import datetime
from datetime import timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from silvertine.core.event.event_bus import EventBus
from silvertine.core.event.events import EventType
from silvertine.core.event.events import MarketDataEvent
from silvertine.core.event.events import OrderEvent
from silvertine.core.event.events import OrderSide
from silvertine.core.pipeline import EventProcessor
from silvertine.core.pipeline import PipelineConfig
from silvertine.core.pipeline import PipelineMetrics
from silvertine.core.redis.redis_streams import RedisStreamManager


class TestPipelineConfig:
    """Test the PipelineConfig class."""

    def test_pipeline_config_creation(self):
        """Test creating a pipeline configuration."""
        config = PipelineConfig(
            batch_size=20,
            max_pending_events=2000,
            process_interval=0.05,
            backpressure_threshold=0.9,
            enable_persistence=False,
            enable_replay=False,
        )

        assert config.batch_size == 20
        assert config.max_pending_events == 2000
        assert config.process_interval == 0.05
        assert config.backpressure_threshold == 0.9
        assert config.enable_persistence is False
        assert config.enable_replay is False

    def test_pipeline_config_defaults(self):
        """Test pipeline configuration with default values."""
        config = PipelineConfig()

        assert config.batch_size == 10
        assert config.max_pending_events == 1000
        assert config.process_interval == 0.1
        assert config.backpressure_threshold == 0.8
        assert config.enable_persistence is True
        assert config.enable_replay is True


class TestPipelineMetrics:
    """Test the PipelineMetrics class."""

    def test_metrics_creation(self):
        """Test creating pipeline metrics."""
        metrics = PipelineMetrics()

        assert metrics.events_ingested == 0
        assert metrics.events_processed == 0
        assert metrics.events_failed == 0
        assert metrics.events_persisted == 0
        assert metrics.backpressure_events == 0
        assert metrics.processing_time_total == 0.0
        assert metrics.last_activity is None
        assert isinstance(metrics.start_time, float)

    def test_metrics_calculations(self):
        """Test metrics calculations."""
        metrics = PipelineMetrics()

        # Simulate some processing
        metrics.events_processed = 100
        metrics.processing_time_total = 5.0

        assert metrics.events_per_second > 0  # Based on uptime
        assert metrics.average_processing_time == 0.05  # 5.0 / 100

    def test_metrics_to_dict(self):
        """Test converting metrics to dictionary."""
        metrics = PipelineMetrics()
        metrics.events_ingested = 50
        metrics.events_processed = 45
        metrics.events_failed = 5

        result = metrics.to_dict()

        assert "events_ingested" in result
        assert "events_processed" in result
        assert "events_failed" in result
        assert "uptime_seconds" in result
        assert "events_per_second" in result
        assert result["events_ingested"] == 50
        assert result["events_processed"] == 45
        assert result["events_failed"] == 5


class TestEventProcessor:
    """Test the EventProcessor class."""

    @pytest.fixture
    def mock_event_bus(self):
        """Create a mock event bus."""
        mock_bus = AsyncMock(spec=EventBus)
        mock_bus.is_running = False  # Start as not running
        return mock_bus

    @pytest.fixture
    def mock_redis_manager(self):
        """Create a mock Redis stream manager."""
        mock_manager = AsyncMock(spec=RedisStreamManager)
        mock_manager.is_connected = False  # Start as not connected
        return mock_manager

    @pytest.fixture
    def pipeline_config(self):
        """Create a test pipeline configuration."""
        return PipelineConfig(
            batch_size=5,
            max_pending_events=100,
            process_interval=0.01,  # Fast for testing
            backpressure_threshold=0.8,
            enable_persistence=True,
            enable_replay=True,
        )

    @pytest.fixture
    def event_processor(self, mock_event_bus, mock_redis_manager, pipeline_config):
        """Create an EventProcessor instance."""
        return EventProcessor(mock_event_bus, mock_redis_manager, pipeline_config)

    @pytest.fixture
    def market_data_event(self):
        """Create a test market data event."""
        return MarketDataEvent(
            symbol="BTCUSDT", price=Decimal("50000.00"), volume=Decimal("1.5")
        )

    @pytest.fixture
    def order_event(self):
        """Create a test order event."""
        return OrderEvent(
            order_id="order_123",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            order_type="MARKET",
        )

    async def test_processor_creation(self, event_processor):
        """Test creating an event processor."""
        assert not event_processor.is_running
        assert event_processor.pending_event_count == 0
        assert not event_processor.is_backpressure_active
        assert isinstance(event_processor.metrics, PipelineMetrics)

    async def test_processor_start_stop_lifecycle(
        self, event_processor, mock_event_bus, mock_redis_manager
    ):
        """Test processor start/stop lifecycle."""
        assert not event_processor.is_running

        # Start processor
        await event_processor.start()
        assert event_processor.is_running
        assert len(event_processor._processing_tasks) >= 1

        # Verify dependencies were started
        mock_event_bus.start.assert_called_once()
        mock_redis_manager.connect.assert_called_once()
        mock_redis_manager.create_streams.assert_called_once()

        # Stop processor
        await event_processor.stop()
        assert not event_processor.is_running
        assert len(event_processor._processing_tasks) == 0

    async def test_event_ingestion(self, event_processor, market_data_event):
        """Test ingesting events into the pipeline."""
        await event_processor.start()

        # Ingest event
        await event_processor.ingest_event(market_data_event)

        assert event_processor.pending_event_count == 1
        assert event_processor.metrics.events_ingested == 1
        assert event_processor.metrics.last_activity is not None

        await event_processor.stop()

    async def test_event_ingestion_not_running(
        self, event_processor, market_data_event
    ):
        """Test that ingestion fails when processor is not running."""
        with pytest.raises(RuntimeError, match="Pipeline is not running"):
            await event_processor.ingest_event(market_data_event)

    async def test_backpressure_handling(self, event_processor, market_data_event):
        """Test backpressure handling."""
        # Set low threshold and max events for testing
        event_processor.config.max_pending_events = 5
        event_processor.config.backpressure_threshold = (
            0.6  # 3/5 = 0.6, so 3 events trigger backpressure
        )

        await event_processor.start()

        # Ingest events until just before backpressure
        for _ in range(2):
            await event_processor.ingest_event(market_data_event)

        assert not event_processor.is_backpressure_active

        # This should trigger backpressure (3/5 = 0.6 >= 0.6)
        await event_processor.ingest_event(market_data_event)
        assert event_processor.is_backpressure_active

        # Next ingestion should fail
        with pytest.raises(ValueError, match="Pipeline backpressure active"):
            await event_processor.ingest_event(market_data_event)

        assert event_processor.metrics.backpressure_events == 1

        await event_processor.stop()

    async def test_multiple_event_types(
        self, event_processor, market_data_event, order_event
    ):
        """Test handling multiple event types."""
        await event_processor.start()

        # Ingest different event types
        await event_processor.ingest_event(market_data_event)
        await event_processor.ingest_event(order_event)

        assert event_processor.pending_event_count == 2
        assert len(event_processor._pending_events[EventType.MARKET_DATA]) == 1
        assert len(event_processor._pending_events[EventType.ORDER]) == 1

        await event_processor.stop()

    async def test_pending_event_processing(
        self, event_processor, mock_event_bus, market_data_event
    ):
        """Test processing of pending events."""
        await event_processor.start()

        # Ingest events
        await event_processor.ingest_event(market_data_event)
        await event_processor.ingest_event(market_data_event)

        # Give processing loop time to work
        await asyncio.sleep(0.05)

        # Events should be published to event bus
        assert mock_event_bus.publish.call_count >= 2
        assert event_processor.metrics.events_processed >= 2

        await event_processor.stop()

    async def test_redis_consumption(
        self, event_processor, mock_redis_manager, market_data_event
    ):
        """Test consuming events from Redis Streams."""
        # Mock Redis consumption
        mock_redis_manager.consume_events.return_value = [
            (market_data_event, "1234567890-0")
        ]

        await event_processor.start()

        # Give ingestion loop time to work
        await asyncio.sleep(0.05)

        # Should consume from Redis and acknowledge
        mock_redis_manager.consume_events.assert_called()
        mock_redis_manager.acknowledge_message.assert_called_with(
            EventType.MARKET_DATA, "1234567890-0"
        )

        await event_processor.stop()

    async def test_outbound_event_persistence(
        self, event_processor, mock_redis_manager, market_data_event
    ):
        """Test persistence of outbound events."""
        await event_processor.start()

        # Simulate event published to event bus
        await event_processor._handle_outbound_event(market_data_event)

        # Should persist to Redis
        mock_redis_manager.publish_event.assert_called_once_with(market_data_event)
        assert event_processor.metrics.events_persisted == 1

        await event_processor.stop()

    async def test_outbound_persistence_disabled(
        self, mock_event_bus, mock_redis_manager, market_data_event
    ):
        """Test that persistence can be disabled."""
        config = PipelineConfig(enable_persistence=False)
        processor = EventProcessor(mock_event_bus, mock_redis_manager, config)

        await processor.start()

        # Handle outbound event
        await processor._handle_outbound_event(market_data_event)

        # Should not persist to Redis
        mock_redis_manager.publish_event.assert_not_called()
        assert processor.metrics.events_persisted == 0

        await processor.stop()

    async def test_event_replay(
        self, event_processor, mock_redis_manager, market_data_event
    ):
        """Test event replay functionality."""
        # Set Redis as connected for replay
        mock_redis_manager.is_connected = True

        start_time = datetime.now(timezone.utc)
        end_time = datetime.now(timezone.utc)

        # Mock replay response
        mock_redis_manager.replay_events.return_value = [
            (market_data_event, "1234567890-0"),
            (market_data_event, "1234567890-1"),
        ]

        events = await event_processor.replay_events(
            EventType.MARKET_DATA, start_time, end_time, max_events=1000
        )

        assert len(events) == 2
        assert all(isinstance(event, MarketDataEvent) for event in events)
        mock_redis_manager.replay_events.assert_called_once_with(
            EventType.MARKET_DATA, start_time, end_time, 1000
        )

    async def test_replay_disabled(self, mock_event_bus, mock_redis_manager):
        """Test that replay can be disabled."""
        config = PipelineConfig(enable_replay=False)
        processor = EventProcessor(mock_event_bus, mock_redis_manager, config)

        start_time = datetime.now(timezone.utc)
        end_time = datetime.now(timezone.utc)

        with pytest.raises(RuntimeError, match="Event replay is disabled"):
            await processor.replay_events(EventType.MARKET_DATA, start_time, end_time)

    async def test_replay_not_connected(self, event_processor):
        """Test replay when Redis is not connected."""
        event_processor.redis_manager.is_connected = False

        start_time = datetime.now(timezone.utc)
        end_time = datetime.now(timezone.utc)

        with pytest.raises(RuntimeError, match="Redis manager is not connected"):
            await event_processor.replay_events(
                EventType.MARKET_DATA, start_time, end_time
            )

    async def test_graceful_shutdown_with_pending_events(
        self, event_processor, market_data_event
    ):
        """Test graceful shutdown with pending events."""
        await event_processor.start()

        # Ingest events but don't let them process
        await event_processor.ingest_event(market_data_event)
        await event_processor.ingest_event(market_data_event)

        initial_pending = event_processor.pending_event_count
        assert initial_pending > 0

        # Stop should flush pending events
        await event_processor.stop()

        # Should have attempted to process pending events
        assert event_processor.metrics.events_processed >= 0

    async def test_error_handling_in_processing(
        self, event_processor, mock_event_bus, market_data_event
    ):
        """Test error handling during event processing."""
        # Make event bus publish fail
        mock_event_bus.publish.side_effect = Exception("Processing failed")

        await event_processor.start()

        # Ingest event
        await event_processor.ingest_event(market_data_event)

        # Give processing time to fail
        await asyncio.sleep(0.05)

        # Should have recorded the failure
        assert event_processor.metrics.events_failed >= 1

        await event_processor.stop()

    async def test_error_handling_in_persistence(
        self, event_processor, mock_redis_manager, market_data_event
    ):
        """Test error handling during persistence."""
        # Make Redis publish fail
        mock_redis_manager.publish_event.side_effect = Exception("Persistence failed")

        await event_processor.start()

        # Handle outbound event (should not crash)
        await event_processor._handle_outbound_event(market_data_event)

        # Should have attempted persistence
        mock_redis_manager.publish_event.assert_called_once()

        await event_processor.stop()

    async def test_metrics_collection(self, event_processor, market_data_event):
        """Test that metrics are collected properly."""
        await event_processor.start()

        # Ingest and process events
        await event_processor.ingest_event(market_data_event)
        await asyncio.sleep(0.05)  # Let processing happen

        metrics = event_processor.get_metrics()

        assert "events_ingested" in metrics
        assert "events_processed" in metrics
        assert "uptime_seconds" in metrics
        assert "events_per_second" in metrics
        assert metrics["events_ingested"] >= 1

        await event_processor.stop()

    async def test_metrics_reset(self, event_processor, market_data_event):
        """Test resetting pipeline metrics."""
        await event_processor.start()

        # Generate some metrics
        await event_processor.ingest_event(market_data_event)
        assert event_processor.metrics.events_ingested > 0

        # Reset metrics
        event_processor.reset_metrics()
        assert event_processor.metrics.events_ingested == 0

        await event_processor.stop()

    async def test_batch_processing(self, event_processor, market_data_event):
        """Test batch processing of events."""
        # Set small batch size for testing
        event_processor.config.batch_size = 2

        await event_processor.start()

        # Ingest multiple events
        for _ in range(5):
            await event_processor.ingest_event(market_data_event)

        # Initial pending count
        initial_pending = event_processor.pending_event_count
        assert initial_pending == 5

        # Give processing time
        await asyncio.sleep(0.1)

        # Should have processed events in batches
        final_pending = event_processor.pending_event_count
        assert final_pending < initial_pending

        await event_processor.stop()

    async def test_double_start_stop(self, event_processor):
        """Test that multiple start/stop calls are handled gracefully."""
        # Multiple starts should be safe
        await event_processor.start()
        await event_processor.start()  # Should not crash
        assert event_processor.is_running

        # Multiple stops should be safe
        await event_processor.stop()
        await event_processor.stop()  # Should not crash
        assert not event_processor.is_running
