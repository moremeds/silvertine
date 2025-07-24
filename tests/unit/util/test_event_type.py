"""
Unit tests for silvertine.util.event_type module.

Tests the event type string constants used throughout the trading platform:
- EVENT_TICK
- EVENT_TRADE  
- EVENT_ORDER
- EVENT_POSITION
- EVENT_ACCOUNT
- EVENT_QUOTE
- EVENT_CONTRACT
- EVENT_LOG
"""

import pytest

from silvertine.util.event_type import EVENT_ACCOUNT
from silvertine.util.event_type import EVENT_CONTRACT
from silvertine.util.event_type import EVENT_LOG
from silvertine.util.event_type import EVENT_ORDER
from silvertine.util.event_type import EVENT_POSITION
from silvertine.util.event_type import EVENT_QUOTE
from silvertine.util.event_type import EVENT_TICK
from silvertine.util.event_type import EVENT_TRADE


class TestEventTypeConstants:
    """Test event type string constants."""

    def test_event_tick_constant(self):
        """Test EVENT_TICK constant."""
        assert EVENT_TICK == "eTick."
        assert isinstance(EVENT_TICK, str)
        assert EVENT_TICK.startswith("e")
        assert EVENT_TICK.endswith(".")

    def test_event_trade_constant(self):
        """Test EVENT_TRADE constant."""
        assert EVENT_TRADE == "eTrade."
        assert isinstance(EVENT_TRADE, str)
        assert EVENT_TRADE.startswith("e")
        assert EVENT_TRADE.endswith(".")

    def test_event_order_constant(self):
        """Test EVENT_ORDER constant."""
        assert EVENT_ORDER == "eOrder."
        assert isinstance(EVENT_ORDER, str)
        assert EVENT_ORDER.startswith("e")
        assert EVENT_ORDER.endswith(".")

    def test_event_position_constant(self):
        """Test EVENT_POSITION constant."""
        assert EVENT_POSITION == "ePosition."
        assert isinstance(EVENT_POSITION, str)
        assert EVENT_POSITION.startswith("e")
        assert EVENT_POSITION.endswith(".")

    def test_event_account_constant(self):
        """Test EVENT_ACCOUNT constant."""
        assert EVENT_ACCOUNT == "eAccount."
        assert isinstance(EVENT_ACCOUNT, str)
        assert EVENT_ACCOUNT.startswith("e")
        assert EVENT_ACCOUNT.endswith(".")

    def test_event_quote_constant(self):
        """Test EVENT_QUOTE constant."""
        assert EVENT_QUOTE == "eQuote."
        assert isinstance(EVENT_QUOTE, str)
        assert EVENT_QUOTE.startswith("e")
        assert EVENT_QUOTE.endswith(".")

    def test_event_contract_constant(self):
        """Test EVENT_CONTRACT constant."""
        assert EVENT_CONTRACT == "eContract."
        assert isinstance(EVENT_CONTRACT, str)
        assert EVENT_CONTRACT.startswith("e")
        assert EVENT_CONTRACT.endswith(".")

    def test_event_log_constant(self):
        """Test EVENT_LOG constant."""
        assert EVENT_LOG == "eLog"
        assert isinstance(EVENT_LOG, str)
        assert EVENT_LOG.startswith("e")
        # Note: EVENT_LOG does not end with "." unlike others

    def test_all_constants_are_strings(self):
        """Test all event type constants are strings."""
        constants = [
            EVENT_TICK, EVENT_TRADE, EVENT_ORDER, EVENT_POSITION,
            EVENT_ACCOUNT, EVENT_QUOTE, EVENT_CONTRACT, EVENT_LOG
        ]

        for constant in constants:
            assert isinstance(constant, str)
            assert len(constant) > 0

    def test_event_type_naming_convention(self):
        """Test event type constants follow naming convention."""
        # Most event types end with "." except EVENT_LOG
        dot_ended_events = [
            EVENT_TICK, EVENT_TRADE, EVENT_ORDER, EVENT_POSITION,
            EVENT_ACCOUNT, EVENT_QUOTE, EVENT_CONTRACT
        ]

        for event_type in dot_ended_events:
            assert event_type.startswith("e")
            assert event_type.endswith(".")
            assert len(event_type) > 2  # At least "e" + content + "."

        # EVENT_LOG is special case
        assert EVENT_LOG.startswith("e")
        assert not EVENT_LOG.endswith(".")

    def test_event_type_uniqueness(self):
        """Test all event type constants are unique."""
        constants = [
            EVENT_TICK, EVENT_TRADE, EVENT_ORDER, EVENT_POSITION,
            EVENT_ACCOUNT, EVENT_QUOTE, EVENT_CONTRACT, EVENT_LOG
        ]

        # Check uniqueness
        assert len(constants) == len(set(constants))

    def test_event_type_content(self):
        """Test event type constants contain expected content."""
        # Test that each constant contains relevant keywords
        assert "Tick" in EVENT_TICK
        assert "Trade" in EVENT_TRADE
        assert "Order" in EVENT_ORDER
        assert "Position" in EVENT_POSITION
        assert "Account" in EVENT_ACCOUNT
        assert "Quote" in EVENT_QUOTE
        assert "Contract" in EVENT_CONTRACT
        assert "Log" in EVENT_LOG

    def test_event_type_case_sensitivity(self):
        """Test event type constants maintain proper case."""
        # All should start with lowercase 'e'
        constants = [
            EVENT_TICK, EVENT_TRADE, EVENT_ORDER, EVENT_POSITION,
            EVENT_ACCOUNT, EVENT_QUOTE, EVENT_CONTRACT, EVENT_LOG
        ]

        for constant in constants:
            assert constant.startswith("e")
            assert not constant.startswith("E")

    def test_event_type_string_operations(self):
        """Test string operations work correctly with event types."""
        # Test concatenation
        symbol = "BTCUSDT"
        tick_event = EVENT_TICK + symbol
        assert tick_event == "eTick.BTCUSDT"

        trade_event = EVENT_TRADE + symbol
        assert trade_event == "eTrade.BTCUSDT"

    def test_event_type_pattern_matching(self):
        """Test event types can be used for pattern matching."""
        # Test prefix matching
        test_events = [
            "eTick.BTCUSDT",
            "eTrade.ETHUSDT",
            "eOrder.12345",
            "ePosition.LONG",
            "eLog",
            "other_event"
        ]

        tick_events = [e for e in test_events if e.startswith(EVENT_TICK)]
        assert len(tick_events) == 1
        assert tick_events[0] == "eTick.BTCUSDT"

        trade_events = [e for e in test_events if e.startswith(EVENT_TRADE)]
        assert len(trade_events) == 1
        assert trade_events[0] == "eTrade.ETHUSDT"

        log_events = [e for e in test_events if e.startswith(EVENT_LOG)]
        assert len(log_events) == 1
        assert log_events[0] == "eLog"

    def test_event_type_immutable(self):
        """Test event type constants are effectively immutable."""
        # Constants should be strings (immutable in Python)
        original_tick = EVENT_TICK

        # String operations create new strings
        modified_tick = EVENT_TICK + "modified"
        assert EVENT_TICK == original_tick  # Original unchanged
        assert modified_tick != EVENT_TICK

    @pytest.mark.parametrize("event_type,expected_value", [
        (EVENT_TICK, "eTick."),
        (EVENT_TRADE, "eTrade."),
        (EVENT_ORDER, "eOrder."),
        (EVENT_POSITION, "ePosition."),
        (EVENT_ACCOUNT, "eAccount."),
        (EVENT_QUOTE, "eQuote."),
        (EVENT_CONTRACT, "eContract."),
        (EVENT_LOG, "eLog"),
    ])
    def test_event_type_values_parametrized(self, event_type, expected_value):
        """Test event type values using parametrized tests."""
        assert event_type == expected_value

    def test_event_type_module_completeness(self):
        """Test that the module contains all expected event types."""
        # Import the module to check its contents
        import silvertine.util.event_type as event_type_module

        # Expected constants
        expected_constants = [
            'EVENT_TICK', 'EVENT_TRADE', 'EVENT_ORDER', 'EVENT_POSITION',
            'EVENT_ACCOUNT', 'EVENT_QUOTE', 'EVENT_CONTRACT', 'EVENT_LOG'
        ]

        for const_name in expected_constants:
            assert hasattr(event_type_module, const_name)
            const_value = getattr(event_type_module, const_name)
            assert isinstance(const_value, str)

    def test_event_type_usage_patterns(self):
        """Test common usage patterns with event types."""
        # Test as dictionary keys
        event_handlers = {
            EVENT_TICK: "tick_handler",
            EVENT_TRADE: "trade_handler",
            EVENT_ORDER: "order_handler",
        }

        assert event_handlers[EVENT_TICK] == "tick_handler"
        assert event_handlers[EVENT_TRADE] == "trade_handler"
        assert event_handlers[EVENT_ORDER] == "order_handler"

        # Test in sets
        critical_events = {EVENT_ORDER, EVENT_TRADE, EVENT_POSITION}

        assert EVENT_ORDER in critical_events
        assert EVENT_TRADE in critical_events
        assert EVENT_TICK not in critical_events

    def test_event_type_length_consistency(self):
        """Test event type lengths are reasonable."""
        constants = [
            EVENT_TICK, EVENT_TRADE, EVENT_ORDER, EVENT_POSITION,
            EVENT_ACCOUNT, EVENT_QUOTE, EVENT_CONTRACT, EVENT_LOG
        ]

        for constant in constants:
            # All should be reasonably short (under 20 chars)
            assert len(constant) < 20
            # All should be at least 4 characters
            assert len(constant) >= 4
