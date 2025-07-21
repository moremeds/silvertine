"""
Exchange broker implementations.

Auto-registers all available brokers with the BrokerRegistry.
"""

from .binance.binance_broker import BinanceBroker
from .factory import BrokerRegistry
from .ib.ib_broker import IBBroker
from .paper.paper_broker import PaperTradingBroker

# Auto-register all brokers
BrokerRegistry.register("paper", PaperTradingBroker)
BrokerRegistry.register("binance", BinanceBroker)
BrokerRegistry.register("ib", IBBroker)

__all__ = ["BrokerRegistry", "PaperTradingBroker", "BinanceBroker", "IBBroker"]
