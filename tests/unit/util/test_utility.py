"""
Unit tests for utility.py module.
"""

import unittest
from datetime import datetime
from datetime import time
from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import mock_open
from unittest.mock import patch

import numpy as np

from silvertine.util.constants import Exchange
from silvertine.util.constants import Interval
from silvertine.util.object import BarData
from silvertine.util.object import TickData
from silvertine.util.utility import TEMP_DIR
from silvertine.util.utility import ArrayManager
from silvertine.util.utility import BarGenerator
from silvertine.util.utility import _get_trader_dir
from silvertine.util.utility import ceil_to
from silvertine.util.utility import extract_vt_symbol
from silvertine.util.utility import floor_to
from silvertine.util.utility import generate_vt_symbol
from silvertine.util.utility import get_digits
from silvertine.util.utility import get_file_path
from silvertine.util.utility import get_folder_path
from silvertine.util.utility import get_icon_path
from silvertine.util.utility import load_json
from silvertine.util.utility import round_to
from silvertine.util.utility import save_json
from silvertine.util.utility import virtual


class TestVTSymbolFunctions(unittest.TestCase):
    """Test VT symbol functions."""

    def test_extract_vt_symbol(self) -> None:
        """Test extract_vt_symbol function."""
        symbol, exchange = extract_vt_symbol("BTCUSDT.BINANCE")
        self.assertEqual(symbol, "BTCUSDT")
        self.assertEqual(exchange, Exchange.BINANCE)

        symbol, exchange = extract_vt_symbol("AAPL.NASDAQ")
        self.assertEqual(symbol, "AAPL")
        self.assertEqual(exchange, Exchange.NASDAQ)

        # Test with multiple dots
        symbol, exchange = extract_vt_symbol("ES2412.CBOT")
        self.assertEqual(symbol, "ES2412")
        self.assertEqual(exchange, Exchange.CBOT)

    def test_generate_vt_symbol(self) -> None:
        """Test generate_vt_symbol function."""
        vt_symbol = generate_vt_symbol("BTCUSDT", Exchange.BINANCE)
        self.assertEqual(vt_symbol, "BTCUSDT.BINANCE")

        vt_symbol = generate_vt_symbol("AAPL", Exchange.NASDAQ)
        self.assertEqual(vt_symbol, "AAPL.NASDAQ")


class TestPathFunctions(unittest.TestCase):
    """Test path-related functions."""

    def test_get_file_path(self) -> None:
        """Test get_file_path function."""
        result = get_file_path("test.json")
        expected = TEMP_DIR.joinpath("test.json")
        self.assertEqual(result, expected)

    @patch('silvertine.util.utility.TEMP_DIR')
    def test_get_folder_path_exists(self, mock_temp_dir: MagicMock) -> None:
        """Test get_folder_path when folder exists."""
        mock_folder = Mock()
        mock_folder.exists.return_value = True
        mock_temp_dir.joinpath.return_value = mock_folder

        result = get_folder_path("test_folder")

        mock_temp_dir.joinpath.assert_called_once_with("test_folder")
        mock_folder.exists.assert_called_once()
        mock_folder.mkdir.assert_not_called()
        self.assertEqual(result, mock_folder)

    @patch('silvertine.util.utility.TEMP_DIR')
    def test_get_folder_path_not_exists(self, mock_temp_dir: MagicMock) -> None:
        """Test get_folder_path when folder doesn't exist."""
        mock_folder = Mock()
        mock_folder.exists.return_value = False
        mock_temp_dir.joinpath.return_value = mock_folder

        result = get_folder_path("test_folder")

        mock_temp_dir.joinpath.assert_called_once_with("test_folder")
        mock_folder.exists.assert_called_once()
        mock_folder.mkdir.assert_called_once()
        self.assertEqual(result, mock_folder)

    def test_get_icon_path(self) -> None:
        """Test get_icon_path function."""
        test_filepath = "/path/to/ui/main.py"
        result = get_icon_path(test_filepath, "icon.png")
        expected = "/path/to/ui/ico/icon.png"
        self.assertEqual(result, expected)


class TestJsonFunctions(unittest.TestCase):
    """Test JSON file functions."""

    @patch('silvertine.util.utility.get_file_path')
    @patch('builtins.open', new_callable=mock_open, read_data='{"key": "value"}')
    def test_load_json_file_exists(self, mock_file: MagicMock, mock_get_file_path: MagicMock) -> None:
        """Test load_json when file exists."""
        mock_path = Mock()
        mock_path.exists.return_value = True
        mock_get_file_path.return_value = mock_path

        result = load_json("test.json")

        mock_get_file_path.assert_called_once_with("test.json")
        mock_path.exists.assert_called_once()
        mock_file.assert_called_once_with(mock_path, encoding="UTF-8")
        self.assertEqual(result, {"key": "value"})

    @patch('silvertine.util.utility.get_file_path')
    @patch('silvertine.util.utility.save_json')
    def test_load_json_file_not_exists(self, mock_save_json: MagicMock, mock_get_file_path: MagicMock) -> None:
        """Test load_json when file doesn't exist."""
        mock_path = Mock()
        mock_path.exists.return_value = False
        mock_get_file_path.return_value = mock_path

        result = load_json("test.json")

        mock_get_file_path.assert_called_once_with("test.json")
        mock_path.exists.assert_called_once()
        mock_save_json.assert_called_once_with("test.json", {})
        self.assertEqual(result, {})

    @patch('silvertine.util.utility.get_file_path')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    def test_save_json(self, mock_json_dump: MagicMock, mock_file: MagicMock, mock_get_file_path: MagicMock) -> None:
        """Test save_json function."""
        mock_path = Mock()
        mock_get_file_path.return_value = mock_path
        test_data = {"key": "value", "number": 123}

        save_json("test.json", test_data)

        mock_get_file_path.assert_called_once_with("test.json")
        mock_file.assert_called_once_with(mock_path, mode="w+", encoding="UTF-8")
        mock_json_dump.assert_called_once_with(
            test_data,
            mock_file.return_value.__enter__.return_value,
            indent=4,
            ensure_ascii=False
        )


class TestMathFunctions(unittest.TestCase):
    """Test mathematical utility functions."""

    def test_round_to(self) -> None:
        """Test round_to function."""
        # Basic rounding
        self.assertEqual(round_to(1.234, 0.01), 1.23)
        self.assertEqual(round_to(1.236, 0.01), 1.24)

        # Round to different targets
        self.assertEqual(round_to(12.34, 0.5), 12.5)
        self.assertEqual(round_to(12.24, 0.5), 12.0)

        # Round to 1
        self.assertEqual(round_to(12.6, 1.0), 13.0)
        self.assertEqual(round_to(12.4, 1.0), 12.0)

    def test_floor_to(self) -> None:
        """Test floor_to function."""
        # Basic flooring
        self.assertEqual(floor_to(1.236, 0.01), 1.23)
        self.assertEqual(floor_to(1.234, 0.01), 1.23)

        # Floor to different targets
        self.assertEqual(floor_to(12.74, 0.5), 12.5)
        self.assertEqual(floor_to(12.24, 0.5), 12.0)

        # Floor to 1
        self.assertEqual(floor_to(12.9, 1.0), 12.0)
        self.assertEqual(floor_to(12.1, 1.0), 12.0)

    def test_ceil_to(self) -> None:
        """Test ceil_to function."""
        # Basic ceiling
        self.assertEqual(ceil_to(1.231, 0.01), 1.24)
        self.assertEqual(ceil_to(1.236, 0.01), 1.24)

        # Ceil to different targets
        self.assertEqual(ceil_to(12.24, 0.5), 12.5)
        self.assertEqual(ceil_to(12.01, 0.5), 12.5)

        # Ceil to 1
        self.assertEqual(ceil_to(12.1, 1.0), 13.0)
        self.assertEqual(ceil_to(12.9, 1.0), 13.0)

    def test_get_digits(self) -> None:
        """Test get_digits function."""
        # Regular decimals
        self.assertEqual(get_digits(1.23), 2)
        self.assertEqual(get_digits(1.234567), 6)
        self.assertEqual(get_digits(1.0), 1)

        # Scientific notation
        self.assertEqual(get_digits(1e-5), 5)
        self.assertEqual(get_digits(1e-10), 10)

        # Integers
        self.assertEqual(get_digits(123), 0)
        self.assertEqual(get_digits(0), 0)


class TestBarGeneratorInit(unittest.TestCase):
    """Test BarGenerator initialization."""

    def test_init_basic(self) -> None:
        """Test basic BarGenerator initialization."""
        on_bar = Mock()
        generator = BarGenerator(on_bar)

        self.assertIsNone(generator.bar)
        self.assertEqual(generator.on_bar, on_bar)
        self.assertEqual(generator.interval, Interval.MINUTE)
        self.assertEqual(generator.interval_count, 0)
        self.assertIsNone(generator.hour_bar)
        self.assertIsNone(generator.daily_bar)
        self.assertEqual(generator.window, 0)
        self.assertIsNone(generator.window_bar)
        self.assertIsNone(generator.on_window_bar)
        self.assertIsNone(generator.last_tick)
        self.assertIsNone(generator.daily_end)

    def test_init_with_window(self) -> None:
        """Test BarGenerator initialization with window."""
        on_bar = Mock()
        on_window_bar = Mock()
        generator = BarGenerator(
            on_bar=on_bar,
            window=5,
            on_window_bar=on_window_bar,
            interval=Interval.HOUR
        )

        self.assertEqual(generator.window, 5)
        self.assertEqual(generator.on_window_bar, on_window_bar)
        self.assertEqual(generator.interval, Interval.HOUR)

    def test_init_daily_without_end_time_raises_error(self) -> None:
        """Test that daily interval without end time raises error."""
        on_bar = Mock()

        with self.assertRaises(RuntimeError) as context:
            BarGenerator(on_bar, interval=Interval.DAILY)

        self.assertIn("Synthetic daily K-line must pass in the daily closing time", str(context.exception))

    def test_init_daily_with_end_time(self) -> None:
        """Test daily interval with end time."""
        on_bar = Mock()
        daily_end = time(15, 0)

        generator = BarGenerator(on_bar, interval=Interval.DAILY, daily_end=daily_end)

        self.assertEqual(generator.daily_end, daily_end)


class TestBarGeneratorTickUpdate(unittest.TestCase):
    """Test BarGenerator tick update functionality."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.on_bar = Mock()
        self.generator = BarGenerator(self.on_bar)

    def create_tick(self, symbol="BTCUSDT", exchange=Exchange.BINANCE,
                   datetime_obj=None, last_price=100.0, volume=1000.0,
                   turnover=100000.0, open_interest=0.0):
        """Helper to create tick data."""
        if datetime_obj is None:
            datetime_obj = datetime(2024, 1, 1, 10, 0, 0)

        return TickData(
            symbol=symbol,
            exchange=exchange,
            datetime=datetime_obj,
            adapter_name="test",
            last_price=last_price,
            volume=volume,
            turnover=turnover,
            open_interest=open_interest
        )

    def test_update_tick_zero_price_filtered(self) -> None:
        """Test that ticks with zero last price are filtered."""
        tick = self.create_tick(last_price=0.0)

        self.generator.update_tick(tick)

        self.assertIsNone(self.generator.bar)
        self.on_bar.assert_not_called()

    def test_update_tick_first_tick_creates_bar(self) -> None:
        """Test that first valid tick creates a bar."""
        tick = self.create_tick(
            datetime_obj=datetime(2024, 1, 1, 10, 30, 15),
            last_price=100.0,
            volume=1000.0,
            turnover=100000.0,
            open_interest=50.0
        )

        self.generator.update_tick(tick)

        self.assertIsNotNone(self.generator.bar)
        self.assertEqual(self.generator.bar.symbol, "BTCUSDT")
        self.assertEqual(self.generator.bar.exchange, Exchange.BINANCE)
        self.assertEqual(self.generator.bar.open_price, 100.0)
        self.assertEqual(self.generator.bar.high_price, 100.0)
        self.assertEqual(self.generator.bar.low_price, 100.0)
        self.assertEqual(self.generator.bar.close_price, 100.0)
        self.assertEqual(self.generator.bar.open_interest, 50.0)
        self.assertEqual(self.generator.last_tick, tick)

    def test_update_tick_same_minute_updates_bar(self) -> None:
        """Test that ticks in same minute update existing bar."""
        # First tick
        tick1 = self.create_tick(
            datetime_obj=datetime(2024, 1, 1, 10, 30, 15),
            last_price=100.0,
            volume=1000.0
        )
        self.generator.update_tick(tick1)

        # Second tick in same minute with higher price
        tick2 = self.create_tick(
            datetime_obj=datetime(2024, 1, 1, 10, 30, 45),
            last_price=105.0,
            volume=1100.0
        )
        self.generator.update_tick(tick2)

        # Bar should be updated
        self.assertEqual(self.generator.bar.high_price, 105.0)
        self.assertEqual(self.generator.bar.low_price, 100.0)
        self.assertEqual(self.generator.bar.close_price, 105.0)
        self.assertEqual(self.generator.bar.volume, 100.0)  # volume difference

    def test_update_tick_new_minute_pushes_bar(self) -> None:
        """Test that new minute pushes previous bar and creates new one."""
        # First tick
        tick1 = self.create_tick(
            datetime_obj=datetime(2024, 1, 1, 10, 30, 15),
            last_price=100.0
        )
        self.generator.update_tick(tick1)

        # Second tick in new minute
        tick2 = self.create_tick(
            datetime_obj=datetime(2024, 1, 1, 10, 31, 15),
            last_price=105.0
        )
        self.generator.update_tick(tick2)

        # Previous bar should be pushed
        self.on_bar.assert_called_once()
        pushed_bar = self.on_bar.call_args[0][0]
        self.assertEqual(pushed_bar.close_price, 100.0)
        self.assertEqual(pushed_bar.datetime.second, 0)
        self.assertEqual(pushed_bar.datetime.microsecond, 0)

        # New bar should be created
        self.assertEqual(self.generator.bar.open_price, 105.0)
        self.assertEqual(self.generator.bar.close_price, 105.0)


class TestArrayManager(unittest.TestCase):
    """Test ArrayManager functionality."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.array_manager = ArrayManager(size=10)

    def create_bar(self, open_price=100.0, high_price=105.0, low_price=95.0,
                   close_price=102.0, volume=1000.0, turnover=100000.0,
                   open_interest=50.0) -> BarData:
        """Helper to create bar data."""
        return BarData(
            symbol="BTCUSDT",
            exchange=Exchange.BINANCE,
            datetime=datetime(2024, 1, 1, 10, 0),
            interval=Interval.MINUTE,
            adapter_name="test",
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            volume=volume,
            turnover=turnover,
            open_interest=open_interest
        )

    def test_init(self) -> None:
        """Test ArrayManager initialization."""
        self.assertEqual(self.array_manager.count, 0)
        self.assertEqual(self.array_manager.size, 10)
        self.assertFalse(self.array_manager.inited)

        # Check arrays are initialized with zeros
        self.assertEqual(len(self.array_manager.open_array), 10)
        self.assertTrue(np.array_equal(self.array_manager.open_array, np.zeros(10)))

    def test_update_bar_single(self) -> None:
        """Test updating with single bar."""
        bar = self.create_bar(open_price=100.0, high_price=105.0,
                             low_price=95.0, close_price=102.0)

        self.array_manager.update_bar(bar)

        self.assertEqual(self.array_manager.count, 1)
        self.assertFalse(self.array_manager.inited)  # Not enough bars yet
        self.assertEqual(self.array_manager.open_array[-1], 100.0)
        self.assertEqual(self.array_manager.high_array[-1], 105.0)
        self.assertEqual(self.array_manager.low_array[-1], 95.0)
        self.assertEqual(self.array_manager.close_array[-1], 102.0)

    def test_update_bar_multiple_until_inited(self) -> None:
        """Test updating until array is initialized."""
        for i in range(10):
            bar = self.create_bar(close_price=100.0 + i)
            self.array_manager.update_bar(bar)

        self.assertEqual(self.array_manager.count, 10)
        self.assertTrue(self.array_manager.inited)

        # Check that the last value is correct
        self.assertEqual(self.array_manager.close_array[-1], 109.0)
        # Check that first value is correct
        self.assertEqual(self.array_manager.close_array[0], 100.0)

    def test_update_bar_rolling_window(self) -> None:
        """Test that array rolls when more than size bars are added."""
        # Add 12 bars to a size-10 array
        for i in range(12):
            bar = self.create_bar(close_price=100.0 + i)
            self.array_manager.update_bar(bar)

        self.assertEqual(self.array_manager.count, 12)
        self.assertTrue(self.array_manager.inited)

        # Check that old values are rolled out
        self.assertEqual(self.array_manager.close_array[0], 102.0)  # Was 100+2
        self.assertEqual(self.array_manager.close_array[-1], 111.0)  # Is 100+11

    def test_properties(self) -> None:
        """Test array properties."""
        # Add some bars
        for i in range(5):
            bar = self.create_bar(
                open_price=100.0 + i,
                high_price=105.0 + i,
                low_price=95.0 + i,
                close_price=102.0 + i,
                volume=1000.0 + i * 100,
                turnover=100000.0 + i * 10000,
                open_interest=50.0 + i * 5
            )
            self.array_manager.update_bar(bar)

        # Test properties return correct arrays
        self.assertTrue(np.array_equal(self.array_manager.open, self.array_manager.open_array))
        self.assertTrue(np.array_equal(self.array_manager.high, self.array_manager.high_array))
        self.assertTrue(np.array_equal(self.array_manager.low, self.array_manager.low_array))
        self.assertTrue(np.array_equal(self.array_manager.close, self.array_manager.close_array))
        self.assertTrue(np.array_equal(self.array_manager.volume, self.array_manager.volume_array))
        self.assertTrue(np.array_equal(self.array_manager.turnover, self.array_manager.turnover_array))
        self.assertTrue(np.array_equal(self.array_manager.open_interest, self.array_manager.open_interest_array))

    @patch('talib.SMA')
    def test_sma_single_value(self, mock_sma: MagicMock) -> None:
        """Test SMA calculation returning single value."""
        mock_sma.return_value = np.array([10.0, 11.0, 12.0])

        result = self.array_manager.sma(5, array=False)

        mock_sma.assert_called_once_with(self.array_manager.close, 5)
        self.assertEqual(result, 12.0)

    @patch('talib.SMA')
    def test_sma_array(self, mock_sma: MagicMock) -> None:
        """Test SMA calculation returning array."""
        expected_array = np.array([10.0, 11.0, 12.0])
        mock_sma.return_value = expected_array

        result = self.array_manager.sma(5, array=True)

        mock_sma.assert_called_once_with(self.array_manager.close, 5)
        self.assertTrue(np.array_equal(result, expected_array))

    @patch('talib.MACD')
    def test_macd_tuple_return(self, mock_macd: MagicMock) -> None:
        """Test MACD calculation returning tuple."""
        macd_line = np.array([1.0, 2.0, 3.0])
        signal_line = np.array([0.5, 1.5, 2.5])
        histogram = np.array([0.5, 0.5, 0.5])
        mock_macd.return_value = (macd_line, signal_line, histogram)

        result = self.array_manager.macd(12, 26, 9, array=False)

        mock_macd.assert_called_once_with(self.array_manager.close, 12, 26, 9)
        self.assertEqual(result, (3.0, 2.5, 0.5))

    @patch('talib.MACD')
    def test_macd_array_return(self, mock_macd: MagicMock) -> None:
        """Test MACD calculation returning arrays."""
        macd_line = np.array([1.0, 2.0, 3.0])
        signal_line = np.array([0.5, 1.5, 2.5])
        histogram = np.array([0.5, 0.5, 0.5])
        mock_macd.return_value = (macd_line, signal_line, histogram)

        result = self.array_manager.macd(12, 26, 9, array=True)

        mock_macd.assert_called_once_with(self.array_manager.close, 12, 26, 9)
        self.assertEqual(len(result), 3)
        self.assertTrue(np.array_equal(result[0], macd_line))
        self.assertTrue(np.array_equal(result[1], signal_line))
        self.assertTrue(np.array_equal(result[2], histogram))


class TestGetTraderDir(unittest.TestCase):
    """Test _get_trader_dir function."""

    @patch('silvertine.util.utility.Path.cwd')
    @patch('silvertine.util.utility.Path.home')
    def test_get_trader_dir_current_dir_exists(self, mock_home: MagicMock, mock_cwd: MagicMock) -> None:
        """Test _get_trader_dir when .vntrader exists in current directory."""
        mock_cwd_path = Mock()
        mock_temp_path = Mock()
        mock_temp_path.exists.return_value = True
        mock_cwd_path.joinpath.return_value = mock_temp_path
        mock_cwd.return_value = mock_cwd_path

        result = _get_trader_dir(".vntrader")

        mock_cwd.assert_called_once()
        mock_cwd_path.joinpath.assert_called_once_with(".vntrader")
        mock_temp_path.exists.assert_called_once()
        mock_home.assert_not_called()
        self.assertEqual(result, (mock_cwd_path, mock_temp_path))

    @patch('silvertine.util.utility.Path.cwd')
    @patch('silvertine.util.utility.Path.home')
    def test_get_trader_dir_home_exists(self, mock_home: MagicMock, mock_cwd: MagicMock) -> None:
        """Test _get_trader_dir when .vntrader doesn't exist in current dir but exists in home."""
        # Current directory mocks
        mock_cwd_path = Mock()
        mock_cwd_temp_path = Mock()
        mock_cwd_temp_path.exists.return_value = False
        mock_cwd_path.joinpath.return_value = mock_cwd_temp_path
        mock_cwd.return_value = mock_cwd_path

        # Home directory mocks
        mock_home_path = Mock()
        mock_home_temp_path = Mock()
        mock_home_temp_path.exists.return_value = True
        mock_home_path.joinpath.return_value = mock_home_temp_path
        mock_home.return_value = mock_home_path

        result = _get_trader_dir(".vntrader")

        mock_cwd.assert_called_once()
        mock_home.assert_called_once()
        mock_home_path.joinpath.assert_called_once_with(".vntrader")
        mock_home_temp_path.exists.assert_called_once()
        mock_home_temp_path.mkdir.assert_not_called()
        self.assertEqual(result, (mock_home_path, mock_home_temp_path))

    @patch('silvertine.util.utility.Path.cwd')
    @patch('silvertine.util.utility.Path.home')
    def test_get_trader_dir_home_not_exists_creates(self, mock_home: MagicMock, mock_cwd: MagicMock) -> None:
        """Test _get_trader_dir creates .vntrader in home when it doesn't exist."""
        # Current directory mocks
        mock_cwd_path = Mock()
        mock_cwd_temp_path = Mock()
        mock_cwd_temp_path.exists.return_value = False
        mock_cwd_path.joinpath.return_value = mock_cwd_temp_path
        mock_cwd.return_value = mock_cwd_path

        # Home directory mocks
        mock_home_path = Mock()
        mock_home_temp_path = Mock()
        mock_home_temp_path.exists.return_value = False
        mock_home_path.joinpath.return_value = mock_home_temp_path
        mock_home.return_value = mock_home_path

        result = _get_trader_dir(".vntrader")

        mock_cwd.assert_called_once()
        mock_home.assert_called_once()
        mock_home_path.joinpath.assert_called_once_with(".vntrader")
        mock_home_temp_path.exists.assert_called_once()
        mock_home_temp_path.mkdir.assert_called_once()
        self.assertEqual(result, (mock_home_path, mock_home_temp_path))


class TestBarGeneratorAdvanced(unittest.TestCase):
    """Test advanced BarGenerator functionality."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.on_bar = Mock()
        self.on_window_bar = Mock()

    def create_bar(self, datetime_obj: datetime, open_price: float = 100.0, high_price: float = 105.0,
                   low_price: float = 95.0, close_price: float = 102.0, volume: float = 1000.0) -> BarData:
        """Helper to create BarData objects."""
        return BarData(
            adapter_name="test_adapter",
            symbol="BTCUSDT",
            exchange=Exchange.BINANCE,
            datetime=datetime_obj,
            interval=Interval.MINUTE,
            volume=volume,
            turnover=volume * close_price,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            open_interest=0.0
        )

    def test_update_bar_basic(self) -> None:
        """Test basic update_bar functionality with window."""
        # Initialize with window to avoid division by zero
        generator = BarGenerator(self.on_bar, window=5, on_window_bar=self.on_window_bar)
        bar = self.create_bar(datetime(2024, 1, 1, 10, 0))

        generator.update_bar(bar)

        # Should not trigger window bar callback on first bar
        self.on_window_bar.assert_not_called()

    def test_update_bar_minute_window(self) -> None:
        """Test update_bar_minute_window functionality."""
        generator = BarGenerator(self.on_bar, window=5, on_window_bar=self.on_window_bar, interval=Interval.MINUTE)

        # First bar - should not trigger window bar
        bar1 = self.create_bar(datetime(2024, 1, 1, 10, 0), close_price=100.0, volume=100.0)
        generator.update_bar_minute_window(bar1)
        self.on_window_bar.assert_not_called()
        self.assertIsNotNone(generator.window_bar)

        # Add more bars to reach window size
        for i in range(1, 5):
            bar = self.create_bar(datetime(2024, 1, 1, 10, i), close_price=100.0 + i, volume=100.0)
            generator.update_bar_minute_window(bar)

        # 5th bar should trigger window bar
        bar5 = self.create_bar(datetime(2024, 1, 1, 10, 5), close_price=105.0, volume=100.0)
        generator.update_bar_minute_window(bar5)

        # Should have called window bar callback
        self.on_window_bar.assert_called_once()

    def test_update_bar_hour_window(self) -> None:
        """Test update_bar_hour_window functionality."""
        generator = BarGenerator(self.on_bar, window=2, on_window_bar=self.on_window_bar, interval=Interval.HOUR)

        # Create a sequence of bars to complete the first hour
        # First initialize the hour with minute 0
        bar1_start = self.create_bar(datetime(2024, 1, 1, 10, 0), close_price=100.0, volume=50.0)
        generator.update_bar_hour_window(bar1_start)

        # Complete the first hour with minute 59
        bar1_end = self.create_bar(datetime(2024, 1, 1, 10, 59), close_price=101.0, volume=50.0)
        generator.update_bar_hour_window(bar1_end)
        self.on_window_bar.assert_not_called()  # First hour completed, but window not complete yet

        # Start and complete second hour
        bar2_start = self.create_bar(datetime(2024, 1, 1, 11, 0), close_price=102.0, volume=50.0)
        generator.update_bar_hour_window(bar2_start)

        bar2_end = self.create_bar(datetime(2024, 1, 1, 11, 59), close_price=103.0, volume=50.0)
        generator.update_bar_hour_window(bar2_end)

        self.on_window_bar.assert_called_once()  # Second hour completes window of 2

    def test_update_bar_daily_window(self) -> None:
        """Test update_bar_daily_window functionality."""
        from datetime import time
        daily_end = time(15, 0)  # 3 PM closing time
        generator = BarGenerator(self.on_bar, window=2, on_window_bar=self.on_window_bar, interval=Interval.DAILY, daily_end=daily_end)

        # First daily bar at closing time - should trigger callback immediately
        bar1 = self.create_bar(datetime(2024, 1, 1, 15, 0), close_price=100.0, volume=1000.0)
        generator.update_bar_daily_window(bar1)
        self.on_window_bar.assert_called_once()  # Daily window calls callback for each completed day

        # Reset mock for second test
        self.on_window_bar.reset_mock()

        # Second daily bar at closing time - should also trigger callback
        bar2 = self.create_bar(datetime(2024, 1, 2, 15, 0), close_price=102.0, volume=1000.0)
        generator.update_bar_daily_window(bar2)

        self.on_window_bar.assert_called_once()  # Each completed day triggers callback

    def test_on_hour_bar(self) -> None:
        """Test on_hour_bar callback functionality."""
        generator = BarGenerator(self.on_bar, window=1, on_window_bar=self.on_window_bar)
        bar = self.create_bar(datetime(2024, 1, 1, 10, 0))

        generator.on_hour_bar(bar)

        # With window=1, should immediately call on_window_bar
        self.on_window_bar.assert_called_once_with(bar)

    def test_generate_method(self) -> None:
        """Test generate method calls callback immediately."""
        generator = BarGenerator(self.on_bar)
        bar = self.create_bar(datetime(2024, 1, 1, 10, 30))

        # Set up a bar in the generator
        generator.bar = bar

        generator.generate()

        # Should call callback with the bar
        self.on_bar.assert_called_once()
        # Bar should be cleared after generation
        self.assertIsNone(generator.bar)


class TestArrayManagerTechnicalIndicators(unittest.TestCase):
    """Test ArrayManager technical indicator methods."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.array_manager = ArrayManager(size=100)
        # Add some sample data
        for i in range(50):
            bar = BarData(
                adapter_name="test_adapter",
                symbol="BTCUSDT",
                exchange=Exchange.BINANCE,
                datetime=datetime(2024, 1, 1, 10, i),
                interval=Interval.MINUTE,
                volume=1000.0,
                turnover=100000.0,
                open_price=100.0 + i * 0.1,
                high_price=101.0 + i * 0.1,
                low_price=99.0 + i * 0.1,
                close_price=100.0 + i * 0.1,
                open_interest=0.0
            )
            self.array_manager.update_bar(bar)

    @patch('talib.EMA')
    def test_ema_single_value(self, mock_ema: MagicMock) -> None:
        """Test EMA calculation returning single value."""
        mock_ema.return_value = np.array([10.0, 11.0, 12.0])

        result = self.array_manager.ema(14, array=False)

        mock_ema.assert_called_once_with(self.array_manager.close, 14)
        self.assertEqual(result, 12.0)

    @patch('talib.EMA')
    def test_ema_array_return(self, mock_ema: MagicMock) -> None:
        """Test EMA calculation returning array."""
        expected_array = np.array([10.0, 11.0, 12.0])
        mock_ema.return_value = expected_array

        result = self.array_manager.ema(14, array=True)

        mock_ema.assert_called_once_with(self.array_manager.close, 14)
        self.assertTrue(np.array_equal(result, expected_array))

    @patch('talib.RSI')
    def test_rsi_single_value(self, mock_rsi: MagicMock) -> None:
        """Test RSI calculation returning single value."""
        mock_rsi.return_value = np.array([30.0, 45.0, 70.0])

        result = self.array_manager.rsi(14, array=False)

        mock_rsi.assert_called_once_with(self.array_manager.close, 14)
        self.assertEqual(result, 70.0)

    @patch('talib.RSI')
    def test_rsi_array_return(self, mock_rsi: MagicMock) -> None:
        """Test RSI calculation returning array."""
        expected_array = np.array([30.0, 45.0, 70.0])
        mock_rsi.return_value = expected_array

        result = self.array_manager.rsi(14, array=True)

        mock_rsi.assert_called_once_with(self.array_manager.close, 14)
        self.assertTrue(np.array_equal(result, expected_array))

    @patch('talib.ATR')
    def test_atr_single_value(self, mock_atr: MagicMock) -> None:
        """Test ATR calculation returning single value."""
        mock_atr.return_value = np.array([1.0, 1.2, 1.5])

        result = self.array_manager.atr(14, array=False)

        mock_atr.assert_called_once_with(self.array_manager.high, self.array_manager.low, self.array_manager.close, 14)
        self.assertEqual(result, 1.5)

    @patch('talib.ATR')
    def test_atr_array_return(self, mock_atr: MagicMock) -> None:
        """Test ATR calculation returning array."""
        expected_array = np.array([1.0, 1.2, 1.5])
        mock_atr.return_value = expected_array

        result = self.array_manager.atr(14, array=True)

        mock_atr.assert_called_once_with(self.array_manager.high, self.array_manager.low, self.array_manager.close, 14)
        self.assertTrue(np.array_equal(result, expected_array))


    @patch('talib.CCI')
    def test_cci_single_value(self, mock_cci: MagicMock) -> None:
        """Test CCI calculation returning single value."""
        mock_cci.return_value = np.array([-100.0, 0.0, 100.0])

        result = self.array_manager.cci(14, array=False)

        mock_cci.assert_called_once_with(self.array_manager.high, self.array_manager.low, self.array_manager.close, 14)
        self.assertEqual(result, 100.0)

    @patch('talib.KAMA')
    def test_kama_single_value(self, mock_kama: MagicMock) -> None:
        """Test KAMA calculation returning single value."""
        mock_kama.return_value = np.array([98.0, 99.0, 100.0])

        result = self.array_manager.kama(14, array=False)

        mock_kama.assert_called_once_with(self.array_manager.close, 14)
        self.assertEqual(result, 100.0)

    @patch('talib.WMA')
    def test_wma_single_value(self, mock_wma: MagicMock) -> None:
        """Test WMA calculation returning single value."""
        mock_wma.return_value = np.array([98.0, 99.0, 100.0])

        result = self.array_manager.wma(14, array=False)

        mock_wma.assert_called_once_with(self.array_manager.close, 14)
        self.assertEqual(result, 100.0)

    @patch('talib.STDDEV')
    def test_std_single_value(self, mock_std: MagicMock) -> None:
        """Test Standard Deviation calculation returning single value."""
        mock_std.return_value = np.array([1.0, 1.2, 1.5])

        result = self.array_manager.std(14, array=False)

        mock_std.assert_called_once_with(self.array_manager.close, 14, 1)
        self.assertEqual(result, 1.5)

    @patch('talib.OBV')
    def test_obv_single_value(self, mock_obv: MagicMock) -> None:
        """Test OBV calculation returning single value."""
        mock_obv.return_value = np.array([1000.0, 2000.0, 3000.0])

        result = self.array_manager.obv(array=False)

        mock_obv.assert_called_once_with(self.array_manager.close, self.array_manager.volume)
        self.assertEqual(result, 3000.0)

    @patch('talib.MFI')
    def test_mfi_single_value(self, mock_mfi: MagicMock) -> None:
        """Test MFI calculation returning single value."""
        mock_mfi.return_value = np.array([20.0, 50.0, 80.0])

        result = self.array_manager.mfi(14, array=False)

        mock_mfi.assert_called_once_with(
            self.array_manager.high,
            self.array_manager.low,
            self.array_manager.close,
            self.array_manager.volume,
            14
        )
        self.assertEqual(result, 80.0)

    @patch('talib.NATR')
    def test_natr_single_value(self, mock_natr: MagicMock) -> None:
        """Test NATR calculation returning single value."""
        mock_natr.return_value = np.array([1.0, 1.2, 1.5])

        result = self.array_manager.natr(14, array=False)

        mock_natr.assert_called_once_with(self.array_manager.high, self.array_manager.low, self.array_manager.close, 14)
        self.assertEqual(result, 1.5)

    @patch('talib.TRANGE')
    def test_trange_single_value(self, mock_trange: MagicMock) -> None:
        """Test TRANGE calculation returning single value."""
        mock_trange.return_value = np.array([1.0, 1.2, 1.5])

        result = self.array_manager.trange(array=False)

        mock_trange.assert_called_once_with(self.array_manager.high, self.array_manager.low, self.array_manager.close)
        self.assertEqual(result, 1.5)

    @patch('talib.ROC')
    def test_roc_single_value(self, mock_roc: MagicMock) -> None:
        """Test ROC calculation returning single value."""
        mock_roc.return_value = np.array([1.0, 2.0, 3.0])

        result = self.array_manager.roc(10, array=False)

        mock_roc.assert_called_once_with(self.array_manager.close, 10)
        self.assertEqual(result, 3.0)

    @patch('talib.CMO')
    def test_cmo_single_value(self, mock_cmo: MagicMock) -> None:
        """Test CMO calculation returning single value."""
        mock_cmo.return_value = np.array([10.0, 20.0, 30.0])

        result = self.array_manager.cmo(14, array=False)

        mock_cmo.assert_called_once_with(self.array_manager.close, 14)
        self.assertEqual(result, 30.0)


class TestVirtualDecorator(unittest.TestCase):
    """Test virtual decorator function."""

    def test_virtual_decorator(self) -> None:
        """Test that virtual decorator returns the function unchanged."""
        def test_function():
            return "test"

        decorated_function = virtual(test_function)

        self.assertEqual(decorated_function, test_function)
        self.assertEqual(decorated_function(), "test")


if __name__ == '__main__':
    unittest.main()
