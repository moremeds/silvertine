"""
Unit tests for silvertine.core.event module.

Tests the Event class and EventEngine implementation including:
- Event creation and data handling
- Event engine lifecycle (start/stop)
- Handler registration and deregistration
- Event processing and distribution
- Timer events
- Thread safety
"""

import threading
import time
from queue import Queue
from unittest.mock import patch

import pytest

from silvertine.core.event import EVENT_TIMER
from silvertine.core.event import Event
from silvertine.core.event import EventEngine


class TestEvent:
    """Test the Event class."""

    def test_event_creation_with_type_only(self):
        """Test creating an event with only a type."""
        event = Event("test_type")
        assert event.type == "test_type"
        assert event.data is None

    def test_event_creation_with_type_and_data(self):
        """Test creating an event with type and data."""
        test_data = {"key": "value", "number": 42}
        event = Event("test_type", test_data)
        assert event.type == "test_type"
        assert event.data == test_data

    def test_event_creation_with_various_data_types(self):
        """Test creating events with different data types."""
        # String data
        event1 = Event("string_event", "test_string")
        assert event1.data == "test_string"

        # List data
        event2 = Event("list_event", [1, 2, 3])
        assert event2.data == [1, 2, 3]

        # None data explicitly
        event3 = Event("none_event", None)
        assert event3.data is None

        # Complex object
        class TestObject:
            def __init__(self, value):
                self.value = value

        test_obj = TestObject("test")
        event4 = Event("object_event", test_obj)
        assert event4.data.value == "test"


class TestEventEngine:
    """Test the EventEngine class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.engine = EventEngine(interval=1)
        self.test_events = []
        self.handler_call_count = 0

    def teardown_method(self):
        """Clean up after each test method."""
        if self.engine._active:
            self.engine.stop()

    def test_event_engine_initialization(self):
        """Test EventEngine initialization with default and custom intervals."""
        # Default interval
        engine1 = EventEngine()
        assert engine1._interval == 1
        assert not engine1._active
        assert isinstance(engine1._queue, Queue)
        assert isinstance(engine1._handlers, dict)
        assert isinstance(engine1._general_handlers, list)

        # Custom interval
        engine2 = EventEngine(interval=5)
        assert engine2._interval == 5

    def test_handler_registration_and_unregistration(self):
        """Test handler registration and unregistration for specific events."""
        def test_handler(event: Event) -> None:
            self.test_events.append(event)

        # Register handler
        self.engine.register("test_event", test_handler)
        assert "test_event" in self.engine._handlers
        assert test_handler in self.engine._handlers["test_event"]

        # Register same handler again (should not duplicate)
        self.engine.register("test_event", test_handler)
        assert len(self.engine._handlers["test_event"]) == 1

        # Register different handler for same event
        def another_handler(event: Event) -> None:
            pass

        self.engine.register("test_event", another_handler)
        assert len(self.engine._handlers["test_event"]) == 2

        # Unregister handler
        self.engine.unregister("test_event", test_handler)
        assert test_handler not in self.engine._handlers["test_event"]
        assert another_handler in self.engine._handlers["test_event"]

        # Unregister last handler (should remove the event type)
        self.engine.unregister("test_event", another_handler)
        assert "test_event" not in self.engine._handlers

    def test_general_handler_registration_and_unregistration(self):
        """Test general handler registration and unregistration."""
        def general_handler(event: Event) -> None:
            self.test_events.append(event)

        # Register general handler
        self.engine.register_general(general_handler)
        assert general_handler in self.engine._general_handlers

        # Register same handler again (should not duplicate)
        self.engine.register_general(general_handler)
        assert len(self.engine._general_handlers) == 1

        # Unregister general handler
        self.engine.unregister_general(general_handler)
        assert general_handler not in self.engine._general_handlers

    def test_event_processing_with_specific_handlers(self):
        """Test event processing with handlers registered for specific types."""
        processed_events = []

        def handler1(event: Event) -> None:
            processed_events.append(("handler1", event.type, event.data))

        def handler2(event: Event) -> None:
            processed_events.append(("handler2", event.type, event.data))

        # Register handlers for different event types
        self.engine.register("type1", handler1)
        self.engine.register("type2", handler2)

        # Process events directly (without starting the engine)
        event1 = Event("type1", "data1")
        event2 = Event("type2", "data2")
        event3 = Event("type3", "data3")

        self.engine._process(event1)
        self.engine._process(event2)
        self.engine._process(event3)

        # Check results
        assert len(processed_events) == 2
        assert ("handler1", "type1", "data1") in processed_events
        assert ("handler2", "type2", "data2") in processed_events

    def test_event_processing_with_general_handlers(self):
        """Test event processing with general handlers."""
        processed_events = []

        def general_handler(event: Event) -> None:
            processed_events.append(("general", event.type, event.data))

        # Register general handler
        self.engine.register_general(general_handler)

        # Process various events
        events = [
            Event("type1", "data1"),
            Event("type2", "data2"),
            Event("type3", "data3")
        ]

        for event in events:
            self.engine._process(event)

        # Check that general handler received all events
        assert len(processed_events) == 3
        assert ("general", "type1", "data1") in processed_events
        assert ("general", "type2", "data2") in processed_events
        assert ("general", "type3", "data3") in processed_events

    def test_event_processing_with_both_specific_and_general_handlers(self):
        """Test event processing with both specific and general handlers."""
        processed_events = []

        def specific_handler(event: Event) -> None:
            processed_events.append(("specific", event.type, event.data))

        def general_handler(event: Event) -> None:
            processed_events.append(("general", event.type, event.data))

        # Register both types of handlers
        self.engine.register("test_type", specific_handler)
        self.engine.register_general(general_handler)

        # Process event
        event = Event("test_type", "test_data")
        self.engine._process(event)

        # Both handlers should have been called
        assert len(processed_events) == 2
        assert ("specific", "test_type", "test_data") in processed_events
        assert ("general", "test_type", "test_data") in processed_events

    def test_put_event(self):
        """Test putting events into the queue."""
        event = Event("test_type", "test_data")
        self.engine.put(event)

        # Verify event is in queue
        queued_event = self.engine._queue.get_nowait()
        assert queued_event.type == "test_type"
        assert queued_event.data == "test_data"

    @pytest.mark.slow
    def test_engine_start_and_stop(self):
        """Test starting and stopping the event engine."""
        processed_events = []

        def test_handler(event: Event) -> None:
            processed_events.append(event)

        self.engine.register("test_event", test_handler)

        # Start engine
        self.engine.start()
        assert self.engine._active is True
        assert self.engine._thread.is_alive()
        assert self.engine._timer.is_alive()

        # Put an event and wait for processing
        test_event = Event("test_event", "test_data")
        self.engine.put(test_event)
        time.sleep(0.1)  # Allow time for processing

        # Stop engine
        self.engine.stop()
        assert self.engine._active is False

        # Verify event was processed
        assert len(processed_events) > 0
        assert processed_events[0].type == "test_event"

    @pytest.mark.slow
    def test_timer_events(self):
        """Test that timer events are generated at the specified interval."""
        timer_events = []

        def timer_handler(event: Event) -> None:
            if event.type == EVENT_TIMER:
                timer_events.append(event)

        # Use shorter interval for testing
        engine = EventEngine(interval=0.1)
        engine.register(EVENT_TIMER, timer_handler)

        try:
            engine.start()
            time.sleep(0.35)  # Wait for multiple timer events
            engine.stop()

            # Should have received at least 2-3 timer events
            assert len(timer_events) >= 2
            for event in timer_events:
                assert event.type == EVENT_TIMER
        finally:
            if engine._active:
                engine.stop()

    def test_multiple_handlers_for_same_event_type(self):
        """Test multiple handlers registered for the same event type."""
        results = []

        def handler1(event: Event) -> None:
            results.append(f"handler1: {event.data}")

        def handler2(event: Event) -> None:
            results.append(f"handler2: {event.data}")

        def handler3(event: Event) -> None:
            results.append(f"handler3: {event.data}")

        # Register multiple handlers
        self.engine.register("multi_event", handler1)
        self.engine.register("multi_event", handler2)
        self.engine.register("multi_event", handler3)

        # Process event
        event = Event("multi_event", "test")
        self.engine._process(event)

        # All handlers should have been called
        assert len(results) == 3
        assert "handler1: test" in results
        assert "handler2: test" in results
        assert "handler3: test" in results

    def test_unregister_nonexistent_handler(self):
        """Test unregistering a handler that was never registered."""
        def dummy_handler(event: Event) -> None:
            pass

        # This should not raise an error
        self.engine.unregister("nonexistent_type", dummy_handler)

        # Register a handler and unregister a different one
        def real_handler(event: Event) -> None:
            pass

        self.engine.register("test_type", real_handler)
        self.engine.unregister("test_type", dummy_handler)  # Should not affect real_handler

        assert real_handler in self.engine._handlers["test_type"]

    def test_unregister_general_handler_not_registered(self):
        """Test unregistering a general handler that was never registered."""
        def dummy_handler(event: Event) -> None:
            pass

        # This should not raise an error
        self.engine.unregister_general(dummy_handler)

        # Verify general handlers list is still empty
        assert len(self.engine._general_handlers) == 0

    @patch('time.sleep')
    def test_timer_thread_behavior(self, mock_sleep):
        """Test the timer thread behavior with mocked sleep."""
        timer_events = []

        def timer_handler(event: Event) -> None:
            if event.type == EVENT_TIMER:
                timer_events.append(event)

        # Mock sleep to return immediately but count calls
        sleep_calls = []
        def side_effect(duration):
            sleep_calls.append(duration)
            if len(sleep_calls) >= 3:  # Stop after a few iterations
                self.engine._active = False

        mock_sleep.side_effect = side_effect

        self.engine.register(EVENT_TIMER, timer_handler)
        self.engine.start()

        # Wait for timer thread to finish
        self.engine._timer.join()
        self.engine._thread.join()

        # Verify sleep was called with correct interval
        assert len(sleep_calls) >= 3
        for call_duration in sleep_calls:
            assert call_duration == 1  # Default interval

    def test_concurrent_event_processing(self):
        """Test concurrent event processing from multiple threads."""
        processed_events = []
        lock = threading.Lock()

        def thread_safe_handler(event: Event) -> None:
            with lock:
                processed_events.append(event.data)

        self.engine.register("concurrent_event", thread_safe_handler)

        # Start the engine
        self.engine.start()

        # Put events from multiple threads
        def put_events(start_num, count):
            for i in range(start_num, start_num + count):
                event = Event("concurrent_event", f"data_{i}")
                self.engine.put(event)

        threads = []
        for i in range(3):
            thread = threading.Thread(target=put_events, args=(i * 10, 5))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Allow time for event processing
        time.sleep(0.2)
        self.engine.stop()

        # Verify all events were processed
        assert len(processed_events) == 15
        for i in range(15):
            expected_data = f"data_{i}"
            assert expected_data in processed_events

    def test_exception_in_handler_does_not_stop_engine(self):
        """Test that exceptions in handlers don't stop the event engine."""
        processed_events = []

        def failing_handler(event: Event) -> None:
            raise Exception("Handler failed")

        def working_handler(event: Event) -> None:
            processed_events.append(event)

        self.engine.register("test_event", failing_handler)
        self.engine.register("test_event", working_handler)

        # This should not raise an exception
        event = Event("test_event", "test_data")
        try:
            self.engine._process(event)
        except Exception:
            pytest.fail("Exception in handler should not propagate")

        # Working handler should still have been called
        assert len(processed_events) == 1
        assert processed_events[0].data == "test_data"
