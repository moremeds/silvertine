from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from importlib import import_module
from types import ModuleType

from util.constants import Exchange
from util.constants import Interval
from util.object import BarData
from util.object import TickData
from util.settings import SETTINGS
from util.utility import ZoneInfo

DB_TZ = ZoneInfo(SETTINGS["database.timezone"])


def convert_tz(dt: datetime) -> datetime:
    """
    Convert timezone of datetime object to DB_TZ.
    """
    dt = dt.astimezone(DB_TZ)
    return dt.replace(tzinfo=None)


@dataclass
class BarOverview:
    """
    Overview of bar data stored in database.
    """

    symbol: str = ""
    exchange: Exchange | None = None
    interval: Interval | None = None
    count: int = 0
    start: datetime | None = None
    end: datetime | None = None


@dataclass
class TickOverview:
    """
    Overview of tick data stored in database.
    """

    symbol: str = ""
    exchange: Exchange | None = None
    count: int = 0
    start: datetime | None = None
    end: datetime | None = None


class BaseDatabase(ABC):
    """
    Abstract database class for connecting to different database.
    """

    @abstractmethod
    def save_bar_data(self, bars: list[BarData], stream: bool = False) -> bool:
        """
        Save bar data into database.
        """
        pass

    @abstractmethod
    def save_tick_data(self, ticks: list[TickData], stream: bool = False) -> bool:
        """
        Save tick data into database.
        """
        pass

    @abstractmethod
    def load_bar_data(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
        start: datetime,
        end: datetime
    ) -> list[BarData]:
        """
        Load bar data from database.
        """
        pass

    @abstractmethod
    def load_tick_data(
        self,
        symbol: str,
        exchange: Exchange,
        start: datetime,
        end: datetime
    ) -> list[TickData]:
        """
        Load tick data from database.
        """
        pass

    @abstractmethod
    def delete_bar_data(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval
    ) -> int:
        """
        Delete all bar data with given symbol + exchange + interval.
        """
        pass

    @abstractmethod
    def delete_tick_data(
        self,
        symbol: str,
        exchange: Exchange
    ) -> int:
        """
        Delete all tick data with given symbol + exchange.
        """
        pass

    @abstractmethod
    def get_bar_overview(self) -> list[BarOverview]:
        """
        Return bar data avaible in database.
        """
        pass

    @abstractmethod
    def get_tick_overview(self) -> list[TickOverview]:
        """
        Return tick data avaible in database.
        """
        pass


database: BaseDatabase | None = None


def get_database() -> BaseDatabase:
    """"""
    # Return database object if already inited
    global database
    if database:
        return database

    # Read database related global setting
    database_name: str = SETTINGS["database.name"]
    module_name: str = f"silvertine_{database_name}"

    # Try to import database module
    try:
        module: ModuleType = import_module(module_name)
    except ModuleNotFoundError:
        print(f"Can't find database driver {module_name}, using default SQLite database")
        module = import_module("silvertine_sqlite")

    # Create database object from module
    database = module.Database()
    if database is None:
        raise RuntimeError("Failed to initialize database object from module.")
    return database
