from collections.abc import Callable
from importlib import import_module
from types import ModuleType

from util.object import BarData
from util.object import HistoryRequest
from util.object import TickData
from util.settings import SETTINGS


class BaseDatafeed:
    """
    Abstract datafeed class for connecting to different datafeed.
    """

    def init(self, output: Callable[[str], None] = print) -> bool:
        """
        Initialize datafeed service connection.
        """
        return False

    def query_bar_history(self, req: HistoryRequest, output: Callable[[str], None] = print) -> list[BarData]:
        """
        Query history bar data.
        """
        output("Query K-line data failed: no correct configuration of data service")
        return []

    def query_tick_history(self, req: HistoryRequest, output: Callable[[str], None] = print) -> list[TickData]:
        """
        Query history tick data.
        """
        output("Query Tick data failed: no correct configuration of data service")
        return []


datafeed: BaseDatafeed = BaseDatafeed()


def get_datafeed() -> BaseDatafeed:
    """"""
    # Return datafeed object if already inited
    global datafeed
    if datafeed:
        return datafeed

    # Read datafeed related global setting
    datafeed_name: str = SETTINGS["datafeed.name"]

    if not datafeed_name:
        datafeed = BaseDatafeed()

        print("No data service configured, please modify the datafeed related content in the global configuration")
    else:
        module_name: str = f"vnpy_{datafeed_name}"

        # Try to import datafeed module
        try:
            module: ModuleType = import_module(module_name)

            # Create datafeed object from module
            datafeed = module.Datafeed()
        # Use base class if failed
        except ModuleNotFoundError:
            datafeed = BaseDatafeed()

            print(f"Can't load data service module, please run pip install {module_name} to try install")

    return datafeed
