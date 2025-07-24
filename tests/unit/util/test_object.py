"""
Unit tests for silvertine.util.object module.

Tests all trading data classes and request objects:
- BaseData (base class)
- Data classes: TickData, BarData, OrderData, TradeData, PositionData, AccountData, LogData, ContractData, QuoteData
- Request classes: SubscribeRequest, OrderRequest, CancelRequest, HistoryRequest, QuoteRequest
- Constants: INFO, ACTIVE_STATUSES
- Methods: is_active(), create_cancel_request(), create_order_data(), create_quote_data()
"""

from datetime import datetime

import pytest

from silvertine.util.constants import Direction
from silvertine.util.constants import Exchange
from silvertine.util.constants import Interval
from silvertine.util.constants import Offset
from silvertine.util.constants import OptionType
from silvertine.util.constants import OrderType
from silvertine.util.constants import Product
from silvertine.util.constants import Status
from silvertine.util.object import ACTIVE_STATUSES
from silvertine.util.object import INFO
from silvertine.util.object import AccountData
from silvertine.util.object import BarData
from silvertine.util.object import BaseData
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


class TestConstants:
    """Test module constants."""

    def test_info_constant(self):
        """Test INFO constant value."""
        assert INFO == 20
        assert isinstance(INFO, int)

    def test_active_statuses_constant(self):
        """Test ACTIVE_STATUSES constant."""
        expected_statuses = {Status.SUBMITTING, Status.NOTTRADED, Status.PARTTRADED}
        assert ACTIVE_STATUSES == expected_statuses
        assert isinstance(ACTIVE_STATUSES, set)
        assert len(ACTIVE_STATUSES) == 3


class TestBaseData:
    """Test BaseData base class."""

    def test_base_data_creation(self):
        """Test BaseData creation with adapter_name."""
        base_data = BaseData(adapter_name="test_adapter")
        assert base_data.adapter_name == "test_adapter"
        assert base_data.extra is None

    def test_base_data_extra_field(self):
        """Test BaseData extra field behavior."""
        base_data = BaseData(adapter_name="test_adapter")

        # extra should be None by default and not part of init
        assert base_data.extra is None

        # Should be able to set extra after creation
        base_data.extra = {"key": "value"}
        assert base_data.extra == {"key": "value"}

    def test_base_data_required_field(self):
        """Test BaseData requires adapter_name."""
        # Should work with adapter_name
        base_data = BaseData(adapter_name="test")
        assert base_data.adapter_name == "test"

    def test_base_data_inheritance(self):
        """Test BaseData can be inherited."""
        class TestData(BaseData):
            def __init__(self, adapter_name: str, test_field: str):
                super().__init__(adapter_name)
                self.test_field = test_field

        test_data = TestData("adapter", "test_value")
        assert test_data.adapter_name == "adapter"
        assert test_data.test_field == "test_value"
        assert test_data.extra is None


class TestTickData:
    """Test TickData class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sample_datetime = datetime(2024, 1, 15, 10, 30, 0)

    def test_tick_data_creation_minimal(self):
        """Test TickData creation with minimal required fields."""
        tick = TickData(
            adapter_name="test_adapter",
            symbol="BTCUSDT",
            exchange=Exchange.BINANCE if hasattr(Exchange, 'BINANCE') else Exchange.GLOBAL,
            datetime=self.sample_datetime
        )

        assert tick.adapter_name == "test_adapter"
        assert tick.symbol == "BTCUSDT"
        assert tick.datetime == self.sample_datetime
        assert tick.name == ""  # Default value
        assert tick.volume == 0  # Default value
        assert tick.last_price == 0  # Default value

    def test_tick_data_vt_symbol_generation(self):
        """Test vt_symbol is generated correctly in __post_init__."""
        exchange = Exchange.GLOBAL
        tick = TickData(
            adapter_name="test_adapter",
            symbol="BTCUSDT",
            exchange=exchange,
            datetime=self.sample_datetime
        )

        expected_vt_symbol = f"BTCUSDT.{exchange.value}"
        assert tick.vt_symbol == expected_vt_symbol

    def test_tick_data_all_fields(self):
        """Test TickData with all fields populated."""
        exchange = Exchange.GLOBAL
        tick = TickData(
            adapter_name="binance",
            symbol="ETHUSDT",
            exchange=exchange,
            datetime=self.sample_datetime,
            name="Ethereum/USDT",
            volume=1000.5,
            turnover=50000.25,
            open_interest=2000.0,
            last_price=3500.75,
            last_volume=10.5,
            limit_up=4000.0,
            limit_down=3000.0,
            open_price=3480.0,
            high_price=3520.0,
            low_price=3475.0,
            pre_close=3485.0,
            bid_price_1=3499.5,
            ask_price_1=3500.5,
            bid_volume_1=15.2,
            ask_volume_1=8.7,
            localtime=self.sample_datetime
        )

        assert tick.name == "Ethereum/USDT"
        assert tick.volume == 1000.5
        assert tick.last_price == 3500.75
        assert tick.bid_price_1 == 3499.5
        assert tick.ask_price_1 == 3500.5
        assert tick.localtime == self.sample_datetime
        assert tick.vt_symbol == f"ETHUSDT.{exchange.value}"

    def test_tick_data_orderbook_levels(self):
        """Test TickData orderbook levels (bid/ask prices and volumes)."""
        tick = TickData(
            adapter_name="test",
            symbol="TEST",
            exchange=Exchange.GLOBAL,
            datetime=self.sample_datetime,
            bid_price_1=100.0, bid_volume_1=10.0,
            bid_price_2=99.5, bid_volume_2=20.0,
            bid_price_3=99.0, bid_volume_3=30.0,
            ask_price_1=100.5, ask_volume_1=15.0,
            ask_price_2=101.0, ask_volume_2=25.0,
            ask_price_3=101.5, ask_volume_3=35.0,
        )

        # Test bid levels
        assert tick.bid_price_1 == 100.0
        assert tick.bid_volume_1 == 10.0
        assert tick.bid_price_2 == 99.5
        assert tick.bid_volume_2 == 20.0

        # Test ask levels
        assert tick.ask_price_1 == 100.5
        assert tick.ask_volume_1 == 15.0
        assert tick.ask_price_2 == 101.0
        assert tick.ask_volume_2 == 25.0


class TestBarData:
    """Test BarData class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sample_datetime = datetime(2024, 1, 15, 10, 30, 0)

    def test_bar_data_creation_minimal(self):
        """Test BarData creation with minimal required fields."""
        bar = BarData(
            adapter_name="test_adapter",
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            datetime=self.sample_datetime
        )

        assert bar.adapter_name == "test_adapter"
        assert bar.symbol == "BTCUSDT"
        assert bar.exchange == Exchange.GLOBAL
        assert bar.datetime == self.sample_datetime
        assert bar.interval is None  # Default value
        assert bar.volume == 0  # Default value

    def test_bar_data_vt_symbol_generation(self):
        """Test vt_symbol generation in __post_init__."""
        exchange = Exchange.GLOBAL
        bar = BarData(
            adapter_name="test",
            symbol="ETHUSDT",
            exchange=exchange,
            datetime=self.sample_datetime
        )

        assert bar.vt_symbol == f"ETHUSDT.{exchange.value}"

    def test_bar_data_ohlcv_fields(self):
        """Test BarData OHLCV (Open, High, Low, Close, Volume) fields."""
        bar = BarData(
            adapter_name="test",
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            datetime=self.sample_datetime,
            interval=Interval.MINUTE,
            volume=1000.0,
            turnover=50000.0,
            open_interest=500.0,
            open_price=50000.0,
            high_price=50500.0,
            low_price=49800.0,
            close_price=50200.0
        )

        assert bar.interval == Interval.MINUTE
        assert bar.volume == 1000.0
        assert bar.open_price == 50000.0
        assert bar.high_price == 50500.0
        assert bar.low_price == 49800.0
        assert bar.close_price == 50200.0
        assert bar.turnover == 50000.0


class TestOrderData:
    """Test OrderData class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sample_datetime = datetime(2024, 1, 15, 10, 30, 0)

    def test_order_data_creation_minimal(self):
        """Test OrderData creation with minimal required fields."""
        order = OrderData(
            adapter_name="test_adapter",
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            orderid="12345"
        )

        assert order.adapter_name == "test_adapter"
        assert order.symbol == "BTCUSDT"
        assert order.exchange == Exchange.GLOBAL
        assert order.orderid == "12345"
        assert order.type == OrderType.LIMIT  # Default
        assert order.status == Status.SUBMITTING  # Default

    def test_order_data_vt_identifiers(self):
        """Test vt_symbol and vt_orderid generation."""
        order = OrderData(
            adapter_name="binance",
            symbol="ETHUSDT",
            exchange=Exchange.GLOBAL,
            orderid="67890"
        )

        assert order.vt_symbol == f"ETHUSDT.{Exchange.GLOBAL.value}"
        assert order.vt_orderid == "binance.67890"

    def test_order_data_is_active_method(self):
        """Test is_active() method."""
        # Test active statuses
        active_statuses = [Status.SUBMITTING, Status.NOTTRADED, Status.PARTTRADED]
        for status in active_statuses:
            order = OrderData(
                adapter_name="test", symbol="TEST", exchange=Exchange.GLOBAL,
                orderid="123", status=status
            )
            assert order.is_active() is True

        # Test inactive statuses
        inactive_statuses = [Status.ALLTRADED, Status.CANCELLED, Status.REJECTED]
        for status in inactive_statuses:
            order = OrderData(
                adapter_name="test", symbol="TEST", exchange=Exchange.GLOBAL,
                orderid="123", status=status
            )
            assert order.is_active() is False

    def test_order_data_create_cancel_request(self):
        """Test create_cancel_request() method."""
        order = OrderData(
            adapter_name="test",
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            orderid="12345"
        )

        cancel_req = order.create_cancel_request()

        assert isinstance(cancel_req, CancelRequest)
        assert cancel_req.orderid == "12345"
        assert cancel_req.symbol == "BTCUSDT"
        assert cancel_req.exchange == Exchange.GLOBAL

    def test_order_data_full_fields(self):
        """Test OrderData with all fields populated."""
        order = OrderData(
            adapter_name="binance",
            symbol="ETHUSDT",
            exchange=Exchange.GLOBAL,
            orderid="67890",
            type=OrderType.MARKET,
            direction=Direction.LONG,
            offset=Offset.OPEN,
            price=3500.0,
            volume=10.0,
            traded=5.0,
            status=Status.PARTTRADED,
            datetime=self.sample_datetime,
            reference="test_ref"
        )

        assert order.type == OrderType.MARKET
        assert order.direction == Direction.LONG
        assert order.offset == Offset.OPEN
        assert order.price == 3500.0
        assert order.volume == 10.0
        assert order.traded == 5.0
        assert order.status == Status.PARTTRADED
        assert order.datetime == self.sample_datetime
        assert order.reference == "test_ref"


class TestTradeData:
    """Test TradeData class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sample_datetime = datetime(2024, 1, 15, 10, 30, 0)

    def test_trade_data_creation(self):
        """Test TradeData creation."""
        trade = TradeData(
            adapter_name="binance",
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            orderid="12345",
            tradeid="67890"
        )

        assert trade.adapter_name == "binance"
        assert trade.symbol == "BTCUSDT"
        assert trade.exchange == Exchange.GLOBAL
        assert trade.orderid == "12345"
        assert trade.tradeid == "67890"

    def test_trade_data_vt_identifiers(self):
        """Test vt_symbol, vt_orderid, and vt_tradeid generation."""
        trade = TradeData(
            adapter_name="test_adapter",
            symbol="ETHUSDT",
            exchange=Exchange.GLOBAL,
            orderid="order123",
            tradeid="trade456"
        )

        assert trade.vt_symbol == f"ETHUSDT.{Exchange.GLOBAL.value}"
        assert trade.vt_orderid == "test_adapter.order123"
        assert trade.vt_tradeid == "test_adapter.trade456"

    def test_trade_data_full_fields(self):
        """Test TradeData with all fields."""
        trade = TradeData(
            adapter_name="binance",
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            orderid="12345",
            tradeid="67890",
            direction=Direction.LONG,
            offset=Offset.OPEN,
            price=50000.0,
            volume=0.1,
            datetime=self.sample_datetime
        )

        assert trade.direction == Direction.LONG
        assert trade.offset == Offset.OPEN
        assert trade.price == 50000.0
        assert trade.volume == 0.1
        assert trade.datetime == self.sample_datetime


class TestPositionData:
    """Test PositionData class."""

    def test_position_data_creation(self):
        """Test PositionData creation."""
        position = PositionData(
            adapter_name="test",
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            direction=Direction.LONG
        )

        assert position.adapter_name == "test"
        assert position.symbol == "BTCUSDT"
        assert position.exchange == Exchange.GLOBAL
        assert position.direction == Direction.LONG
        assert position.volume == 0  # Default
        assert position.price == 0  # Default

    def test_position_data_vt_identifiers(self):
        """Test vt_symbol and vt_positionid generation."""
        position = PositionData(
            adapter_name="binance",
            symbol="ETHUSDT",
            exchange=Exchange.GLOBAL,
            direction=Direction.SHORT
        )

        expected_vt_symbol = f"ETHUSDT.{Exchange.GLOBAL.value}"
        expected_vt_positionid = f"binance.{expected_vt_symbol}.{Direction.SHORT.value}"

        assert position.vt_symbol == expected_vt_symbol
        assert position.vt_positionid == expected_vt_positionid

    def test_position_data_full_fields(self):
        """Test PositionData with all fields."""
        position = PositionData(
            adapter_name="test",
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            direction=Direction.LONG,
            volume=10.0,
            frozen=2.0,
            price=50000.0,
            pnl=1000.0,
            yd_volume=8.0
        )

        assert position.volume == 10.0
        assert position.frozen == 2.0
        assert position.price == 50000.0
        assert position.pnl == 1000.0
        assert position.yd_volume == 8.0


class TestAccountData:
    """Test AccountData class."""

    def test_account_data_creation(self):
        """Test AccountData creation."""
        account = AccountData(
            adapter_name="test",
            accountid="account123"
        )

        assert account.adapter_name == "test"
        assert account.accountid == "account123"
        assert account.balance == 0  # Default
        assert account.frozen == 0  # Default

    def test_account_data_available_calculation(self):
        """Test available balance calculation in __post_init__."""
        account = AccountData(
            adapter_name="test",
            accountid="account123",
            balance=10000.0,
            frozen=1000.0
        )

        assert account.balance == 10000.0
        assert account.frozen == 1000.0
        assert account.available == 9000.0  # balance - frozen

    def test_account_data_vt_accountid(self):
        """Test vt_accountid generation."""
        account = AccountData(
            adapter_name="binance",
            accountid="acc456"
        )

        assert account.vt_accountid == "binance.acc456"


class TestLogData:
    """Test LogData class."""

    def test_log_data_creation(self):
        """Test LogData creation."""
        log = LogData(
            adapter_name="test",
            msg="Test log message"
        )

        assert log.adapter_name == "test"
        assert log.msg == "Test log message"
        assert log.level == INFO  # Default

    def test_log_data_time_generation(self):
        """Test time generation in __post_init__."""
        before_creation = datetime.now()
        log = LogData(
            adapter_name="test",
            msg="Test message"
        )
        after_creation = datetime.now()

        assert before_creation <= log.time <= after_creation

    def test_log_data_custom_level(self):
        """Test LogData with custom log level."""
        custom_level = 30
        log = LogData(
            adapter_name="test",
            msg="Warning message",
            level=custom_level
        )

        assert log.level == custom_level


class TestContractData:
    """Test ContractData class."""

    def test_contract_data_creation(self):
        """Test ContractData creation with required fields."""
        contract = ContractData(
            adapter_name="test",
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            name="Bitcoin/USDT",
            product=Product.SPOT,
            size=1.0,
            pricetick=0.01
        )

        assert contract.symbol == "BTCUSDT"
        assert contract.name == "Bitcoin/USDT"
        assert contract.product == Product.SPOT
        assert contract.size == 1.0
        assert contract.pricetick == 0.01

    def test_contract_data_vt_symbol(self):
        """Test vt_symbol generation."""
        contract = ContractData(
            adapter_name="test",
            symbol="ETHUSDT",
            exchange=Exchange.GLOBAL,
            name="Ethereum/USDT",
            product=Product.SPOT,
            size=1.0,
            pricetick=0.01
        )

        assert contract.vt_symbol == f"ETHUSDT.{Exchange.GLOBAL.value}"

    def test_contract_data_optional_fields(self):
        """Test ContractData with optional fields."""
        option_expiry = datetime(2024, 12, 31)
        option_listed = datetime(2024, 1, 1)

        contract = ContractData(
            adapter_name="test",
            symbol="BTCUSDT_C_50000",
            exchange=Exchange.GLOBAL,
            name="BTC Call Option",
            product=Product.OPTION,
            size=1.0,
            pricetick=0.01,
            min_volume=0.1,
            max_volume=1000.0,
            stop_supported=True,
            net_position=True,
            history_data=True,
            option_strike=50000.0,
            option_underlying="BTCUSDT",
            option_type=OptionType.CALL,
            option_listed=option_listed,
            option_expiry=option_expiry,
            option_portfolio="BTC_OPTIONS",
            option_index="001"
        )

        assert contract.product == Product.OPTION
        assert contract.min_volume == 0.1
        assert contract.max_volume == 1000.0
        assert contract.stop_supported is True
        assert contract.option_strike == 50000.0
        assert contract.option_type == OptionType.CALL
        assert contract.option_expiry == option_expiry


class TestQuoteData:
    """Test QuoteData class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sample_datetime = datetime(2024, 1, 15, 10, 30, 0)

    def test_quote_data_creation(self):
        """Test QuoteData creation."""
        quote = QuoteData(
            adapter_name="test",
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            quoteid="quote123"
        )

        assert quote.symbol == "BTCUSDT"
        assert quote.quoteid == "quote123"
        assert quote.status == Status.SUBMITTING  # Default

    def test_quote_data_vt_identifiers(self):
        """Test vt_symbol and vt_quoteid generation."""
        quote = QuoteData(
            adapter_name="binance",
            symbol="ETHUSDT",
            exchange=Exchange.GLOBAL,
            quoteid="quote456"
        )

        assert quote.vt_symbol == f"ETHUSDT.{Exchange.GLOBAL.value}"
        assert quote.vt_quoteid == "binance.quote456"

    def test_quote_data_is_active_method(self):
        """Test is_active() method."""
        # Test active statuses
        for status in ACTIVE_STATUSES:
            quote = QuoteData(
                adapter_name="test", symbol="TEST", exchange=Exchange.GLOBAL,
                quoteid="123", status=status
            )
            assert quote.is_active() is True

        # Test inactive status
        quote = QuoteData(
            adapter_name="test", symbol="TEST", exchange=Exchange.GLOBAL,
            quoteid="123", status=Status.CANCELLED
        )
        assert quote.is_active() is False

    def test_quote_data_create_cancel_request(self):
        """Test create_cancel_request() method."""
        quote = QuoteData(
            adapter_name="test",
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            quoteid="quote123"
        )

        cancel_req = quote.create_cancel_request()

        assert isinstance(cancel_req, CancelRequest)
        assert cancel_req.orderid == "quote123"  # Uses quoteid as orderid
        assert cancel_req.symbol == "BTCUSDT"
        assert cancel_req.exchange == Exchange.GLOBAL


class TestRequestClasses:
    """Test request classes."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sample_datetime = datetime(2024, 1, 15, 10, 30, 0)

    def test_subscribe_request(self):
        """Test SubscribeRequest class."""
        req = SubscribeRequest(
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL
        )

        assert req.symbol == "BTCUSDT"
        assert req.exchange == Exchange.GLOBAL
        assert req.vt_symbol == f"BTCUSDT.{Exchange.GLOBAL.value}"

    def test_order_request(self):
        """Test OrderRequest class."""
        req = OrderRequest(
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            direction=Direction.LONG,
            type=OrderType.LIMIT,
            volume=1.0,
            price=50000.0
        )

        assert req.symbol == "BTCUSDT"
        assert req.direction == Direction.LONG
        assert req.type == OrderType.LIMIT
        assert req.volume == 1.0
        assert req.price == 50000.0
        assert req.offset == Offset.NONE  # Default

    def test_order_request_create_order_data(self):
        """Test OrderRequest.create_order_data() method."""
        req = OrderRequest(
            symbol="ETHUSDT",
            exchange=Exchange.GLOBAL,
            direction=Direction.SHORT,
            type=OrderType.MARKET,
            volume=2.0,
            reference="test_ref"
        )

        order = req.create_order_data("order123", "test_adapter")

        assert isinstance(order, OrderData)
        assert order.symbol == "ETHUSDT"
        assert order.exchange == Exchange.GLOBAL
        assert order.orderid == "order123"
        assert order.direction == Direction.SHORT
        assert order.type == OrderType.MARKET
        assert order.volume == 2.0
        assert order.adapter_name == "test_adapter"
        assert order.reference == "test_ref"

    def test_cancel_request(self):
        """Test CancelRequest class."""
        req = CancelRequest(
            orderid="12345",
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL
        )

        assert req.orderid == "12345"
        assert req.symbol == "BTCUSDT"
        assert req.exchange == Exchange.GLOBAL
        assert req.vt_symbol == f"BTCUSDT.{Exchange.GLOBAL.value}"

    def test_history_request(self):
        """Test HistoryRequest class."""
        start_time = datetime(2024, 1, 1)
        end_time = datetime(2024, 1, 31)

        req = HistoryRequest(
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            start=start_time,
            end=end_time,
            interval=Interval.DAILY
        )

        assert req.symbol == "BTCUSDT"
        assert req.start == start_time
        assert req.end == end_time
        assert req.interval == Interval.DAILY
        assert req.vt_symbol == f"BTCUSDT.{Exchange.GLOBAL.value}"

    def test_quote_request(self):
        """Test QuoteRequest class."""
        req = QuoteRequest(
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            bid_price=49900.0,
            bid_volume=10,
            ask_price=50100.0,
            ask_volume=5
        )

        assert req.symbol == "BTCUSDT"
        assert req.bid_price == 49900.0
        assert req.bid_volume == 10
        assert req.ask_price == 50100.0
        assert req.ask_volume == 5

    def test_quote_request_create_quote_data(self):
        """Test QuoteRequest.create_quote_data() method."""
        req = QuoteRequest(
            symbol="ETHUSDT",
            exchange=Exchange.GLOBAL,
            bid_price=3450.0,
            bid_volume=15,
            ask_price=3455.0,
            ask_volume=8,
            bid_offset=Offset.OPEN,
            ask_offset=Offset.CLOSE,
            reference="test_quote"
        )

        quote = req.create_quote_data("quote789", "test_adapter")

        assert isinstance(quote, QuoteData)
        assert quote.symbol == "ETHUSDT"
        assert quote.quoteid == "quote789"
        assert quote.bid_price == 3450.0
        assert quote.bid_volume == 15
        assert quote.ask_price == 3455.0
        assert quote.ask_volume == 8
        assert quote.bid_offset == Offset.OPEN
        assert quote.ask_offset == Offset.CLOSE
        assert quote.reference == "test_quote"
        assert quote.adapter_name == "test_adapter"


class TestDataClassBehavior:
    """Test general dataclass behaviors."""

    def test_dataclass_immutability_attempt(self):
        """Test that dataclasses can be modified (they're not frozen by default)."""
        order = OrderData(
            adapter_name="test",
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            orderid="12345"
        )

        # Should be able to modify fields (dataclasses are mutable by default)
        order.price = 50000.0
        assert order.price == 50000.0

        order.volume = 1.0
        assert order.volume == 1.0

    def test_dataclass_equality(self):
        """Test dataclass equality comparison."""
        order1 = OrderData(
            adapter_name="test",
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            orderid="12345",
            price=50000.0
        )

        order2 = OrderData(
            adapter_name="test",
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            orderid="12345",
            price=50000.0
        )

        # Should be equal because all fields are the same
        assert order1 == order2

        # Modify one field
        order2.price = 51000.0
        assert order1 != order2

    def test_dataclass_string_representation(self):
        """Test dataclass string representation."""
        tick = TickData(
            adapter_name="test",
            symbol="BTCUSDT",
            exchange=Exchange.GLOBAL,
            datetime=datetime(2024, 1, 15, 10, 30, 0)
        )

        str_repr = str(tick)

        # Should contain class name and key fields
        assert "TickData" in str_repr
        assert "BTCUSDT" in str_repr
        assert "test" in str_repr

    @pytest.mark.parametrize("data_class,required_args", [
        (TickData, {"adapter_name": "test", "symbol": "TEST", "exchange": Exchange.GLOBAL, "datetime": datetime.now()}),
        (BarData, {"adapter_name": "test", "symbol": "TEST", "exchange": Exchange.GLOBAL, "datetime": datetime.now()}),
        (OrderData, {"adapter_name": "test", "symbol": "TEST", "exchange": Exchange.GLOBAL, "orderid": "123"}),
        (TradeData, {"adapter_name": "test", "symbol": "TEST", "exchange": Exchange.GLOBAL, "orderid": "123", "tradeid": "456"}),
        (PositionData, {"adapter_name": "test", "symbol": "TEST", "exchange": Exchange.GLOBAL, "direction": Direction.LONG}),
        (AccountData, {"adapter_name": "test", "accountid": "acc123"}),
        (LogData, {"adapter_name": "test", "msg": "test message"}),
        (ContractData, {"adapter_name": "test", "symbol": "TEST", "exchange": Exchange.GLOBAL, "name": "Test", "product": Product.SPOT, "size": 1.0, "pricetick": 0.01}),
        (QuoteData, {"adapter_name": "test", "symbol": "TEST", "exchange": Exchange.GLOBAL, "quoteid": "123"}),
    ])
    def test_data_class_creation_parametrized(self, data_class, required_args):
        """Test data class creation with minimal required arguments."""
        instance = data_class(**required_args)

        # Verify instance was created successfully
        assert isinstance(instance, data_class)
        assert isinstance(instance, BaseData)

        # Verify required fields are set
        for field_name, expected_value in required_args.items():
            assert getattr(instance, field_name) == expected_value
