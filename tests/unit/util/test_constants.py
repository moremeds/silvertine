"""
Unit tests for silvertine.util.constants module.

Tests all enum constants used throughout the trading platform:
- Direction (LONG, SHORT, NET)
- Offset (NONE, OPEN, CLOSE, etc.)
- Status (SUBMITTING, NOTTRADED, etc.)
- Product (EQUITY, FUTURES, etc.)
- OrderType (LIMIT, MARKET, etc.)
- OptionType (CALL, PUT)
- Exchange (various exchanges)
- Currency (USD, HKD, etc.)
- Interval (MINUTE, HOUR, etc.)
"""

from enum import Enum

import pytest

from silvertine.util.constants import Currency
from silvertine.util.constants import Direction
from silvertine.util.constants import Exchange
from silvertine.util.constants import Interval
from silvertine.util.constants import Offset
from silvertine.util.constants import OptionType
from silvertine.util.constants import OrderType
from silvertine.util.constants import Product
from silvertine.util.constants import Status


class TestDirection:
    """Test Direction enum."""

    def test_direction_values(self):
        """Test Direction enum values."""
        assert Direction.LONG.value == "LONG"
        assert Direction.SHORT.value == "SHORT"
        assert Direction.NET.value == "NET"

    def test_direction_enum_type(self):
        """Test Direction is an Enum."""
        assert issubclass(Direction, Enum)
        assert isinstance(Direction.LONG, Direction)

    def test_direction_all_members(self):
        """Test all Direction members are present."""
        expected_members = {"LONG", "SHORT", "NET"}
        actual_members = {member.name for member in Direction}
        assert actual_members == expected_members

    def test_direction_string_representation(self):
        """Test Direction string representations."""
        assert str(Direction.LONG) == "Direction.LONG"
        assert Direction.LONG.value == "LONG"


class TestOffset:
    """Test Offset enum."""

    def test_offset_values(self):
        """Test Offset enum values."""
        assert Offset.NONE.value == ""
        assert Offset.OPEN.value == "OPEN"
        assert Offset.CLOSE.value == "CLOSE"
        assert Offset.CLOSETODAY.value == "CLOSETODAY"
        assert Offset.CLOSEYESTERDAY.value == "CLOSEYESTERDAY"

    def test_offset_enum_type(self):
        """Test Offset is an Enum."""
        assert issubclass(Offset, Enum)
        assert isinstance(Offset.NONE, Offset)

    def test_offset_all_members(self):
        """Test all Offset members are present."""
        expected_members = {"NONE", "OPEN", "CLOSE", "CLOSETODAY", "CLOSEYESTERDAY"}
        actual_members = {member.name for member in Offset}
        assert actual_members == expected_members


class TestStatus:
    """Test Status enum."""

    def test_status_values(self):
        """Test Status enum values."""
        assert Status.SUBMITTING.value == "SUBMITTING"
        assert Status.NOTTRADED.value == "NOTTRADED"
        assert Status.PARTTRADED.value == "PARTTRADED"
        assert Status.ALLTRADED.value == "ALLTRADED"
        assert Status.CANCELLED.value == "CANCELLED"
        assert Status.REJECTED.value == "REJECTED"

    def test_status_enum_type(self):
        """Test Status is an Enum."""
        assert issubclass(Status, Enum)
        assert isinstance(Status.SUBMITTING, Status)

    def test_status_all_members(self):
        """Test all Status members are present."""
        expected_members = {
            "SUBMITTING", "NOTTRADED", "PARTTRADED",
            "ALLTRADED", "CANCELLED", "REJECTED"
        }
        actual_members = {member.name for member in Status}
        assert actual_members == expected_members

    def test_status_trading_states(self):
        """Test status represents various trading states."""
        # Active trading states
        active_states = [Status.SUBMITTING, Status.NOTTRADED, Status.PARTTRADED]
        for state in active_states:
            assert isinstance(state, Status)

        # Final states
        final_states = [Status.ALLTRADED, Status.CANCELLED, Status.REJECTED]
        for state in final_states:
            assert isinstance(state, Status)


class TestProduct:
    """Test Product enum."""

    def test_product_values(self):
        """Test Product enum values match expected financial instruments."""
        assert Product.EQUITY.value == "EQUITY"
        assert Product.FUTURES.value == "FUTURES"
        assert Product.OPTION.value == "OPTION"
        assert Product.INDEX.value == "INDEX"
        assert Product.FOREX.value == "FOREX"
        assert Product.SPOT.value == "SPOT"
        assert Product.ETF.value == "ETF"
        assert Product.BOND.value == "BOND"
        assert Product.WARRANT.value == "WARRANT"
        assert Product.SPREAD.value == "SPREAD"
        assert Product.FUND.value == "FUND"
        assert Product.CFD.value == "CFD"
        assert Product.SWAP.value == "SWAP"

    def test_product_all_members(self):
        """Test all Product members are present."""
        expected_members = {
            "EQUITY", "FUTURES", "OPTION", "INDEX", "FOREX", "SPOT",
            "ETF", "BOND", "WARRANT", "SPREAD", "FUND", "CFD", "SWAP"
        }
        actual_members = {member.name for member in Product}
        assert actual_members == expected_members

    def test_product_financial_instrument_coverage(self):
        """Test Product covers main financial instrument categories."""
        # Equity-like instruments
        equity_like = [Product.EQUITY, Product.ETF, Product.INDEX]
        assert all(isinstance(p, Product) for p in equity_like)

        # Derivatives
        derivatives = [Product.FUTURES, Product.OPTION, Product.WARRANT, Product.CFD]
        assert all(isinstance(p, Product) for p in derivatives)

        # Fixed income
        fixed_income = [Product.BOND]
        assert all(isinstance(p, Product) for p in fixed_income)


class TestOrderType:
    """Test OrderType enum."""

    def test_order_type_values(self):
        """Test OrderType enum values."""
        assert OrderType.LIMIT.value == "LIMIT"
        assert OrderType.MARKET.value == "MARKET"
        assert OrderType.STOP.value == "STOP"
        assert OrderType.FAK.value == "FAK"  # Fill and Kill
        assert OrderType.FOK.value == "FOK"  # Fill or Kill
        assert OrderType.RFQ.value == "RFQ"  # Request for Quote
        assert OrderType.ETF.value == "ETF"

    def test_order_type_all_members(self):
        """Test all OrderType members are present."""
        expected_members = {"LIMIT", "MARKET", "STOP", "FAK", "FOK", "RFQ", "ETF"}
        actual_members = {member.name for member in OrderType}
        assert actual_members == expected_members

    def test_order_type_execution_types(self):
        """Test OrderType covers main execution types."""
        # Basic order types
        basic_types = [OrderType.LIMIT, OrderType.MARKET, OrderType.STOP]
        assert all(isinstance(ot, OrderType) for ot in basic_types)

        # Advanced order types
        advanced_types = [OrderType.FAK, OrderType.FOK, OrderType.RFQ]
        assert all(isinstance(ot, OrderType) for ot in advanced_types)


class TestOptionType:
    """Test OptionType enum."""

    def test_option_type_values(self):
        """Test OptionType enum values."""
        assert OptionType.CALL.value == "CALL"
        assert OptionType.PUT.value == "PUT"

    def test_option_type_all_members(self):
        """Test all OptionType members are present."""
        expected_members = {"CALL", "PUT"}
        actual_members = {member.name for member in OptionType}
        assert actual_members == expected_members

    def test_option_type_completeness(self):
        """Test OptionType covers all option types."""
        assert len(list(OptionType)) == 2
        assert OptionType.CALL in OptionType
        assert OptionType.PUT in OptionType


class TestExchange:
    """Test Exchange enum."""

    def test_exchange_chinese_exchanges(self):
        """Test Chinese exchange values."""
        chinese_exchanges = {
            Exchange.CFFEX: "CFFEX",    # China Financial Futures Exchange
            Exchange.SHFE: "SHFE",      # Shanghai Futures Exchange
            Exchange.CZCE: "CZCE",      # Zhengzhou Commodity Exchange
            Exchange.DCE: "DCE",        # Dalian Commodity Exchange
            Exchange.INE: "INE",        # Shanghai International Energy Exchange
            Exchange.GFEX: "GFEX",      # Guangzhou Futures Exchange
            Exchange.SSE: "SSE",        # Shanghai Stock Exchange
            Exchange.SZSE: "SZSE",      # Shenzhen Stock Exchange
            Exchange.BSE: "BSE",        # Beijing Stock Exchange
        }

        for exchange, expected_value in chinese_exchanges.items():
            assert exchange.value == expected_value

    def test_exchange_us_exchanges(self):
        """Test US exchange values."""
        us_exchanges = {
            Exchange.NYSE: "NYSE",
            Exchange.NASDAQ: "NASDAQ",
            Exchange.ARCA: "ARCA",
            Exchange.AMEX: "AMEX",
            Exchange.BATS: "BATS",
            Exchange.IEX: "IEX",
        }

        for exchange, expected_value in us_exchanges.items():
            assert exchange.value == expected_value

    def test_exchange_global_exchanges(self):
        """Test global exchange values."""
        global_exchanges = [
            Exchange.SEHK,    # Hong Kong
            Exchange.HKFE,    # Hong Kong Futures
            Exchange.SGX,     # Singapore
            Exchange.EUREX,   # Europe
            Exchange.LME,     # London Metal Exchange
            Exchange.CME,     # Chicago Mercantile Exchange
        ]

        for exchange in global_exchanges:
            assert isinstance(exchange, Exchange)
            assert isinstance(exchange.value, str)
            assert len(exchange.value) > 0

    def test_exchange_special_exchanges(self):
        """Test special function exchanges."""
        assert Exchange.LOCAL.value == "LOCAL"
        assert Exchange.GLOBAL.value == "GLOBAL"
        assert Exchange.OTC.value == "OTC"
        assert Exchange.IBKRATS.value == "IBKRATS"  # Paper Trading

    def test_exchange_enum_type(self):
        """Test Exchange is an Enum."""
        assert issubclass(Exchange, Enum)
        assert isinstance(Exchange.NYSE, Exchange)

    def test_exchange_comprehensive_coverage(self):
        """Test Exchange covers major global exchanges."""
        # Should have many exchanges (at least 30)
        assert len(list(Exchange)) >= 30

        # Should include major regions
        exchange_values = [e.value for e in Exchange]

        # US markets
        assert "NYSE" in exchange_values
        assert "NASDAQ" in exchange_values

        # Asian markets
        assert "SEHK" in exchange_values  # Hong Kong
        assert "SGX" in exchange_values   # Singapore

        # European markets
        assert "EUREX" in exchange_values or "EUX" in exchange_values


class TestCurrency:
    """Test Currency enum."""

    def test_currency_values(self):
        """Test Currency enum values."""
        assert Currency.USD.value == "USD"
        assert Currency.HKD.value == "HKD"
        assert Currency.CNY.value == "CNY"
        assert Currency.CAD.value == "CAD"

    def test_currency_all_members(self):
        """Test all Currency members are present."""
        expected_members = {"USD", "HKD", "CNY", "CAD"}
        actual_members = {member.name for member in Currency}
        assert actual_members == expected_members

    def test_currency_major_currencies(self):
        """Test Currency includes major trading currencies."""
        major_currencies = [Currency.USD, Currency.HKD, Currency.CNY, Currency.CAD]
        for currency in major_currencies:
            assert isinstance(currency, Currency)
            assert len(currency.value) == 3  # Standard currency code length


class TestInterval:
    """Test Interval enum."""

    def test_interval_values(self):
        """Test Interval enum values."""
        assert Interval.MINUTE.value == "1m"
        assert Interval.HOUR.value == "1h"
        assert Interval.DAILY.value == "d"
        assert Interval.WEEKLY.value == "w"
        assert Interval.TICK.value == "tick"

    def test_interval_all_members(self):
        """Test all Interval members are present."""
        expected_members = {"MINUTE", "HOUR", "DAILY", "WEEKLY", "TICK"}
        actual_members = {member.name for member in Interval}
        assert actual_members == expected_members

    def test_interval_time_hierarchy(self):
        """Test Interval represents proper time hierarchy."""
        time_intervals = [
            Interval.TICK,     # Finest granularity
            Interval.MINUTE,   # 1 minute bars
            Interval.HOUR,     # 1 hour bars
            Interval.DAILY,    # Daily bars
            Interval.WEEKLY,   # Weekly bars
        ]

        for interval in time_intervals:
            assert isinstance(interval, Interval)
            assert isinstance(interval.value, str)

    def test_interval_string_formats(self):
        """Test Interval string formats are consistent."""
        # Time-based intervals use short notation
        assert Interval.MINUTE.value == "1m"
        assert Interval.HOUR.value == "1h"

        # Period-based use single letter
        assert Interval.DAILY.value == "d"
        assert Interval.WEEKLY.value == "w"

        # Special case
        assert Interval.TICK.value == "tick"


class TestEnumIntegration:
    """Test enum integration and relationships."""

    def test_all_enums_are_enums(self):
        """Test all constants are proper Enum subclasses."""
        enum_classes = [
            Direction, Offset, Status, Product, OrderType,
            OptionType, Exchange, Currency, Interval
        ]

        for enum_class in enum_classes:
            assert issubclass(enum_class, Enum)
            assert len(list(enum_class)) > 0

    def test_enum_value_types(self):
        """Test all enum values are strings."""
        enum_classes = [
            Direction, Offset, Status, Product, OrderType,
            OptionType, Exchange, Currency, Interval
        ]

        for enum_class in enum_classes:
            for member in enum_class:
                assert isinstance(member.value, str)

    def test_enum_uniqueness(self):
        """Test enum values are unique within each enum."""
        enum_classes = [
            Direction, Offset, Status, Product, OrderType,
            OptionType, Exchange, Currency, Interval
        ]

        for enum_class in enum_classes:
            values = [member.value for member in enum_class]
            assert len(values) == len(set(values)), f"Duplicate values in {enum_class.__name__}"

    def test_enum_membership(self):
        """Test enum membership works correctly."""
        # Test membership
        assert Direction.LONG in Direction
        assert Status.SUBMITTING in Status
        assert Exchange.NYSE in Exchange

        # Test non-membership
        assert "INVALID" not in [d.value for d in Direction]

    @pytest.mark.parametrize("enum_class", [
        Direction, Offset, Status, Product, OrderType,
        OptionType, Exchange, Currency, Interval
    ])
    def test_enum_iteration(self, enum_class):
        """Test enum iteration works for all enums."""
        members = list(enum_class)
        assert len(members) > 0

        for member in members:
            assert isinstance(member, enum_class)
            assert hasattr(member, 'name')
            assert hasattr(member, 'value')

    def test_enum_comparison(self):
        """Test enum comparison operations."""
        # Same enum comparisons
        assert Direction.LONG == Direction.LONG
        assert Direction.LONG != Direction.SHORT

        # Different enum comparisons should not be equal
        assert Direction.LONG != Status.SUBMITTING

        # Value comparisons
        assert Direction.LONG.value == "LONG"
        assert Direction.LONG.value != "SHORT"
