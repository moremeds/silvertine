"""
Unit tests for silvertine.adapter.adapter module.

Tests the BaseAdapter abstract class and its event handling methods:
- Initialization and basic properties
- Event handling methods (on_tick, on_trade, on_order, etc.)
- Abstract method requirements
- Thread safety considerations
- Event publishing functionality
"""

from datetime import datetime
from unittest.mock import Mock

import pytest

from silvertine.adapter.adapter import BaseAdapter
from silvertine.core.engine import EventEngine
from silvertine.util.constants import Direction
from silvertine.util.constants import Exchange
from silvertine.util.constants import OrderType
from silvertine.util.constants import Product
from silvertine.util.constants import Status
from silvertine.util.event_type import EVENT_ACCOUNT
from silvertine.util.event_type import EVENT_CONTRACT
from silvertine.util.event_type import EVENT_LOG
from silvertine.util.event_type import EVENT_ORDER
from silvertine.util.event_type import EVENT_POSITION
from silvertine.util.event_type import EVENT_QUOTE
from silvertine.util.event_type import EVENT_TICK
from silvertine.util.event_type import EVENT_TRADE
from silvertine.util.object import AccountData
from silvertine.util.object import CancelRequest
from silvertine.util.object import ContractData
from silvertine.util.object import HistoryRequest
from silvertine.util.object import LogData
from silvertine.util.object import OrderData
from silvertine.util.object import OrderRequest
from silvertine.util.object import PositionData
from silvertine.util.object import QuoteData
from silvertine.util.object import QuoteRequest
from silvertine.util.object import SubscribeRequest
from silvertine.util.object import TickData
from silvertine.util.object import TradeData


class ConcreteAdapter(BaseAdapter):
    """Concrete implementation of BaseAdapter for testing."""

    default_name = "test_adapter"
    default_setting = {"host": "localhost", "port": 8080}
    exchanges = [Exchange.GLOBAL]

    def __init__(self, event_engine: EventEngine, adapter_name: str):
        super().__init__(event_engine, adapter_name)
        self.connected = False
        self.subscriptions = []
        self.orders = {}

    def connect(self, setting):
        """Mock connect implementation."""
        self.connected = True
        self.write_log(f"Connected to {setting.get('host', 'localhost')}")

    def close(self):
        """Mock close implementation."""
        self.connected = False
        self.write_log("Disconnected")

    def subscribe(self, req: SubscribeRequest):
        """Mock subscribe implementation."""
        self.subscriptions.append((req.symbol, req.exchange))
        self.write_log(f"Subscribed to {req.vt_symbol}")

    def send_order(self, req: OrderRequest) -> str:
        """Mock send_order implementation."""
        order_id = f"order_{len(self.orders) + 1}"
        order = req.create_order_data(order_id, self.adapter_name)
        order.status = Status.SUBMITTING
        self.orders[order_id] = order
        self.on_order(order)
        return order.vt_orderid

    def cancel_order(self, req: CancelRequest):
        """Mock cancel_order implementation."""
        if req.orderid in self.orders:
            order = self.orders[req.orderid]
            order.status = Status.CANCELLED
            self.on_order(order)

    def query_account(self):
        """Mock query_account implementation."""
        account = AccountData(
            adapter_name=self.adapter_name,
            accountid="test_account",
            balance=10000.0,
            frozen=1000.0
        )
        self.on_account(account)

    def query_position(self):
        """Mock query_position implementation."""
        position = PositionData(
            adapter_name=self.adapter_name,
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            direction=Direction.LONG,
            volume=1.0,
            price=50000.0
        )
        self.on_position(position)


class TestBaseAdapter:
    """Test BaseAdapter abstract class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.event_engine = Mock(spec=EventEngine)
        self.adapter_name = "test_adapter"
        self.adapter = ConcreteAdapter(self.event_engine, self.adapter_name)

    def test_base_adapter_initialization(self):
        """Test BaseAdapter initialization."""
        assert self.adapter.event_engine == self.event_engine
        assert self.adapter.adapter_name == self.adapter_name
        assert self.adapter.default_name == "test_adapter"
        assert self.adapter.default_setting == {"host": "localhost", "port": 8080}
        assert self.adapter.exchanges == [Exchange.GLOBAL]

    def test_base_adapter_cannot_be_instantiated(self):
        """Test that BaseAdapter cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseAdapter(self.event_engine, "test")

    def test_on_event_method(self):
        """Test on_event method."""
        test_data = {"key": "value"}
        event_type = "test_event"

        self.adapter.on_event(event_type, test_data)

        # Verify event was put into the event engine
        self.event_engine.put.assert_called_once()
        call_args = self.event_engine.put.call_args[0][0]
        assert call_args.type == event_type
        assert call_args.data == test_data

    def test_on_tick_method(self):
        """Test on_tick method publishes both general and specific tick events."""
        tick = TickData(
            adapter_name=self.adapter_name,
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            datetime=datetime.now()
        )

        self.adapter.on_tick(tick)

        # Should publish two events: general and symbol-specific
        assert self.event_engine.put.call_count == 2

        call_args_list = self.event_engine.put.call_args_list

        # First call: general tick event
        general_event = call_args_list[0][0][0]
        assert general_event.type == EVENT_TICK
        assert general_event.data == tick

        # Second call: symbol-specific tick event
        specific_event = call_args_list[1][0][0]
        assert specific_event.type == EVENT_TICK + tick.vt_symbol
        assert specific_event.data == tick

    def test_on_trade_method(self):
        """Test on_trade method publishes both general and specific trade events."""
        trade = TradeData(
            adapter_name=self.adapter_name,
            symbol="ETHUSDT",
            exchange=Exchange.GLOBAL,
            orderid="12345",
            tradeid="67890"
        )

        self.adapter.on_trade(trade)

        assert self.event_engine.put.call_count == 2
        call_args_list = self.event_engine.put.call_args_list

        # General trade event
        general_event = call_args_list[0][0][0]
        assert general_event.type == EVENT_TRADE
        assert general_event.data == trade

        # Symbol-specific trade event
        specific_event = call_args_list[1][0][0]
        assert specific_event.type == EVENT_TRADE + trade.vt_symbol
        assert specific_event.data == trade

    def test_on_order_method(self):
        """Test on_order method publishes both general and order-specific events."""
        order = OrderData(
            adapter_name=self.adapter_name,
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            orderid="12345"
        )

        self.adapter.on_order(order)

        assert self.event_engine.put.call_count == 2
        call_args_list = self.event_engine.put.call_args_list

        # General order event
        general_event = call_args_list[0][0][0]
        assert general_event.type == EVENT_ORDER
        assert general_event.data == order

        # Order-specific event
        specific_event = call_args_list[1][0][0]
        assert specific_event.type == EVENT_ORDER + order.vt_orderid
        assert specific_event.data == order

    def test_on_position_method(self):
        """Test on_position method publishes both general and symbol-specific events."""
        position = PositionData(
            adapter_name=self.adapter_name,
            symbol="ETHUSDT",
            exchange=Exchange.GLOBAL,
            direction=Direction.LONG
        )

        self.adapter.on_position(position)

        assert self.event_engine.put.call_count == 2
        call_args_list = self.event_engine.put.call_args_list

        # General position event
        general_event = call_args_list[0][0][0]
        assert general_event.type == EVENT_POSITION
        assert general_event.data == position

        # Symbol-specific position event
        specific_event = call_args_list[1][0][0]
        assert specific_event.type == EVENT_POSITION + position.vt_symbol
        assert specific_event.data == position

    def test_on_account_method(self):
        """Test on_account method publishes both general and account-specific events."""
        account = AccountData(
            adapter_name=self.adapter_name,
            accountid="test_account"
        )

        self.adapter.on_account(account)

        assert self.event_engine.put.call_count == 2
        call_args_list = self.event_engine.put.call_args_list

        # General account event
        general_event = call_args_list[0][0][0]
        assert general_event.type == EVENT_ACCOUNT
        assert general_event.data == account

        # Account-specific event
        specific_event = call_args_list[1][0][0]
        assert specific_event.type == EVENT_ACCOUNT + account.vt_accountid
        assert specific_event.data == account

    def test_on_quote_method(self):
        """Test on_quote method publishes both general and symbol-specific events."""
        quote = QuoteData(
            adapter_name=self.adapter_name,
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            quoteid="quote123"
        )

        self.adapter.on_quote(quote)

        assert self.event_engine.put.call_count == 2
        call_args_list = self.event_engine.put.call_args_list

        # General quote event
        general_event = call_args_list[0][0][0]
        assert general_event.type == EVENT_QUOTE
        assert general_event.data == quote

        # Symbol-specific quote event
        specific_event = call_args_list[1][0][0]
        assert specific_event.type == EVENT_QUOTE + quote.vt_symbol
        assert specific_event.data == quote

    def test_on_log_method(self):
        """Test on_log method publishes log event."""
        log = LogData(
            adapter_name=self.adapter_name,
            msg="Test log message"
        )

        self.adapter.on_log(log)

        # Should publish only one event (no specific event for logs)
        assert self.event_engine.put.call_count == 1

        event = self.event_engine.put.call_args[0][0]
        assert event.type == EVENT_LOG
        assert event.data == log

    def test_on_contract_method(self):
        """Test on_contract method publishes contract event."""
        contract = ContractData(
            adapter_name=self.adapter_name,
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            name="Bitcoin/USDT",
            product=Product.SPOT,
            size=1.0,
            pricetick=0.01
        )

        self.adapter.on_contract(contract)

        # Should publish only one event (no specific event for contracts)
        assert self.event_engine.put.call_count == 1

        event = self.event_engine.put.call_args[0][0]
        assert event.type == EVENT_CONTRACT
        assert event.data == contract

    def test_write_log_method(self):
        """Test write_log method creates and publishes log event."""
        test_message = "Test log message"

        self.adapter.write_log(test_message)

        # Should have called on_log, which calls on_event
        assert self.event_engine.put.call_count == 1

        event = self.event_engine.put.call_args[0][0]
        assert event.type == EVENT_LOG
        assert event.data.msg == test_message
        assert event.data.adapter_name == self.adapter_name

    def test_get_default_setting_method(self):
        """Test get_default_setting method."""
        default_setting = self.adapter.get_default_setting()

        assert default_setting == {"host": "localhost", "port": 8080}
        assert default_setting == self.adapter.default_setting


class TestConcreteAdapterImplementation:
    """Test the concrete adapter implementation used for testing."""

    def setup_method(self):
        """Set up test fixtures."""
        self.event_engine = Mock(spec=EventEngine)
        self.adapter = ConcreteAdapter(self.event_engine, "test_adapter")

    def test_connect_method(self):
        """Test connect method implementation."""
        setting = {"host": "example.com", "port": 9999}

        self.adapter.connect(setting)

        assert self.adapter.connected is True
        # Should have written a log message
        assert self.event_engine.put.call_count >= 1

    def test_close_method(self):
        """Test close method implementation."""
        self.adapter.connected = True

        self.adapter.close()

        assert self.adapter.connected is False
        # Should have written a log message
        assert self.event_engine.put.call_count >= 1

    def test_subscribe_method(self):
        """Test subscribe method implementation."""
        req = SubscribeRequest(
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL
        )

        self.adapter.subscribe(req)

        assert ("BTCUSDT", Exchange.GLOBAL) in self.adapter.subscriptions
        # Should have written a log message
        assert self.event_engine.put.call_count >= 1

    def test_send_order_method(self):
        """Test send_order method implementation."""
        req = OrderRequest(
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            direction=Direction.LONG,
            type=OrderType.LIMIT,
            volume=1.0,
            price=50000.0
        )

        vt_orderid = self.adapter.send_order(req)

        # Should return a vt_orderid
        assert vt_orderid.startswith(self.adapter.adapter_name)

        # Should have stored the order
        assert len(self.adapter.orders) == 1

        # Should have published order event
        assert self.event_engine.put.call_count >= 2  # on_order publishes 2 events

    def test_cancel_order_method(self):
        """Test cancel_order method implementation."""
        # First create an order
        req = OrderRequest(
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            direction=Direction.LONG,
            type=OrderType.LIMIT,
            volume=1.0,
            price=50000.0
        )

        vt_orderid = self.adapter.send_order(req)
        order_id = vt_orderid.split('.')[1]  # Extract order_id from vt_orderid

        # Reset mock call count
        self.event_engine.put.reset_mock()

        # Now cancel the order
        cancel_req = CancelRequest(
            orderid=order_id,
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL
        )

        self.adapter.cancel_order(cancel_req)

        # Order should be cancelled
        order = self.adapter.orders[order_id]
        assert order.status == Status.CANCELLED

        # Should have published updated order event
        assert self.event_engine.put.call_count >= 2

    def test_query_account_method(self):
        """Test query_account method implementation."""
        self.adapter.query_account()

        # Should have published account event
        assert self.event_engine.put.call_count >= 2  # on_account publishes 2 events

        # Verify account data
        call_args_list = self.event_engine.put.call_args_list
        account_event = call_args_list[0][0][0]
        assert account_event.type == EVENT_ACCOUNT
        assert account_event.data.accountid == "test_account"
        assert account_event.data.balance == 10000.0

    def test_query_position_method(self):
        """Test query_position method implementation."""
        self.adapter.query_position()

        # Should have published position event
        assert self.event_engine.put.call_count >= 2  # on_position publishes 2 events

        # Verify position data
        call_args_list = self.event_engine.put.call_args_list
        position_event = call_args_list[0][0][0]
        assert position_event.type == EVENT_POSITION
        assert position_event.data.symbol == "BTCUSDT"
        assert position_event.data.direction == Direction.LONG

    def test_query_history_default_implementation(self):
        """Test query_history default implementation returns empty list."""
        req = HistoryRequest(
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            start=datetime.now()
        )

        result = self.adapter.query_history(req)

        assert result == []

    def test_send_quote_default_implementation(self):
        """Test send_quote default implementation returns empty string."""
        req = QuoteRequest(
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            bid_price=49900.0,
            bid_volume=10,
            ask_price=50100.0,
            ask_volume=5
        )

        result = self.adapter.send_quote(req)

        assert result == ""

    def test_cancel_quote_default_implementation(self):
        """Test cancel_quote default implementation does nothing."""
        req = CancelRequest(
            orderid="quote123",
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL
        )

        # Should not raise any exception
        result = self.adapter.cancel_quote(req)

        assert result is None

    def test_adapter_class_attributes(self):
        """Test adapter class attributes are properly set."""
        assert ConcreteAdapter.default_name == "test_adapter"
        assert ConcreteAdapter.default_setting == {"host": "localhost", "port": 8080}
        assert ConcreteAdapter.exchanges == [Exchange.GLOBAL]

    def test_adapter_instance_maintains_state(self):
        """Test adapter instance maintains its own state."""
        adapter1 = ConcreteAdapter(Mock(), "adapter1")
        adapter2 = ConcreteAdapter(Mock(), "adapter2")

        # Each adapter should have its own state
        adapter1.connected = True
        adapter2.connected = False

        assert adapter1.connected != adapter2.connected
        assert adapter1.adapter_name != adapter2.adapter_name
        assert len(adapter1.orders) == 0
        assert len(adapter2.orders) == 0
