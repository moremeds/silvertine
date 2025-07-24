"""
Unit tests for silvertine.core.engine module.

Tests the Event class and EventEngine implementation in the engine module.
This module appears to be a duplicate of the event module, so these tests
verify the same functionality works correctly and maintains consistency.
"""

import time

import pytest

from silvertine.core.engine import EVENT_TIMER
from silvertine.core.engine import Event
from silvertine.core.engine import EventEngine
from silvertine.core.engine import HandlerType


class TestEngineEvent:
    """Test the Event class from engine module."""

    def test_event_creation_basic(self) -> None:
        """Test basic event creation."""
        event = Event("test_type")
        assert event.type == "test_type"
        assert event.data is None

    def test_event_creation_with_data(self) -> None:
        """Test event creation with data."""
        test_data = {"test": "value"}
        event = Event("test_type", test_data)
        assert event.type == "test_type"
        assert event.data == test_data

    def test_event_type_annotation(self) -> None:
        """Test that Event properly handles type annotations."""
        event = Event("typed_event", 42)
        assert isinstance(event.type, str)
        assert isinstance(event.data, int)


class TestEngineEventEngine:
    """Test the EventEngine class from engine module."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.engine = EventEngine(interval=1)

    def teardown_method(self) -> None:
        """Clean up after tests."""
        if self.engine._active:
            self.engine.stop()

    def test_engine_initialization(self) -> None:
        """Test EventEngine initialization."""
        engine = EventEngine(interval=2)
        assert engine._interval == 2
        assert not engine._active
        assert len(engine._handlers) == 0
        assert len(engine._general_handlers) == 0

    def test_handler_registration(self) -> None:
        """Test handler registration functionality."""
        call_count = 0

        def test_handler(event: Event) -> None:
            nonlocal call_count
            call_count += 1

        # Register handler
        self.engine.register("test_event", test_handler)
        assert test_handler in self.engine._handlers["test_event"]

        # Process event to verify handler works
        event = Event("test_event", "test_data")
        self.engine._process(event)
        assert call_count == 1

    def test_general_handler_registration(self) -> None:
        """Test general handler registration."""
        processed_events = []

        def general_handler(event: Event) -> None:
            processed_events.append(event.type)

        self.engine.register_general(general_handler)
        assert general_handler in self.engine._general_handlers

        # Test with multiple event types
        events = [Event("type1"), Event("type2"), Event("type3")]
        for event in events:
            self.engine._process(event)

        assert len(processed_events) == 3
        assert "type1" in processed_events
        assert "type2" in processed_events
        assert "type3" in processed_events

    def test_event_queue_operations(self) -> None:
        """Test event queue put operation."""
        event = Event("queue_test", "queue_data")
        self.engine.put(event)

        # Verify event is in queue
        queued_event = self.engine._queue.get_nowait()
        assert queued_event.type == "queue_test"
        assert queued_event.data == "queue_data"

    def test_handler_unregistration(self) -> None:
        """Test handler unregistration."""
        def handler1(event: Event) -> None:
            pass

        def handler2(event: Event) -> None:
            pass

        # Register handlers
        self.engine.register("test_type", handler1)
        self.engine.register("test_type", handler2)
        assert len(self.engine._handlers["test_type"]) == 2

        # Unregister one handler
        self.engine.unregister("test_type", handler1)
        assert handler1 not in self.engine._handlers["test_type"]
        assert handler2 in self.engine._handlers["test_type"]

        # Unregister last handler
        self.engine.unregister("test_type", handler2)
        assert "test_type" not in self.engine._handlers

    def test_consistency_with_event_module(self) -> None:
        """Test that engine module behaves consistently with event module."""
        # Import both modules for comparison
        from silvertine.core.engine import Event as EngineEvent
        from silvertine.core.engine import EventEngine as EngineEventEngine
        from silvertine.core.event import Event as EventEvent
        from silvertine.core.event import EventEngine as EventEventEngine

        # Test Event classes have same interface
        event1 = EventEvent("test", "data")
        event2 = EngineEvent("test", "data")

        assert event1.type == event2.type
        assert event1.data == event2.data

        # Test EventEngine classes have same interface
        engine1 = EventEventEngine(interval=5)
        engine2 = EngineEventEngine(interval=5)

        assert engine1._interval == engine2._interval
        assert type(engine1._handlers) == type(engine2._handlers)  # type: ignore
        assert type(engine1._general_handlers) == type(engine2._general_handlers)  # type: ignore

        # Clean up
        if engine1._active:
            engine1.stop()
        if engine2._active:
            engine2.stop()

    @pytest.mark.slow
    def test_timer_functionality(self) -> None:
        """Test timer event generation."""
        timer_events = []

        def timer_handler(event: Event) -> None:
            if event.type == EVENT_TIMER:
                timer_events.append(event)

        # Use short interval for testing
        test_engine = EventEngine(interval=0.1)
        test_engine.register(EVENT_TIMER, timer_handler)

        try:
            test_engine.start()
            time.sleep(0.25)  # Wait for timer events
            test_engine.stop()

            # Should have received timer events
            assert len(timer_events) >= 1
            for event in timer_events:
                assert event.type == EVENT_TIMER
        finally:
            if test_engine._active:
                test_engine.stop()

    def test_multiple_event_types(self) -> None:
        """Test handling multiple different event types."""
        results = []

        def handler_a(event: Event) -> None:
            results.append(f"A: {event.data}")

        def handler_b(event: Event) -> None:
            results.append(f"B: {event.data}")

        self.engine.register("type_a", handler_a)
        self.engine.register("type_b", handler_b)

        # Process different event types
        self.engine._process(Event("type_a", "data_a"))
        self.engine._process(Event("type_b", "data_b"))
        self.engine._process(Event("type_c", "data_c"))  # No handler

        assert len(results) == 2
        assert "A: data_a" in results
        assert "B: data_b" in results

    def test_handler_type_compatibility(self) -> None:
        """Test that HandlerType annotation works correctly."""
        def typed_handler(event: Event) -> None:
            pass

        # This should work without type errors
        handler: HandlerType = typed_handler
        self.engine.register("typed_event", handler)

        assert handler in self.engine._handlers["typed_event"]

    def test_empty_queue_handling(self) -> None:
        """Test behavior when queue is empty."""
        # Queue should be empty initially
        assert self.engine._queue.empty()

        # Put and immediately get should work
        event = Event("empty_test")
        self.engine.put(event)
        assert not self.engine._queue.empty()

        retrieved = self.engine._queue.get_nowait()
        assert retrieved.type == "empty_test"
        assert self.engine._queue.empty()
