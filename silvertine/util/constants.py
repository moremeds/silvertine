"""
General constant enums used in the trading platform.
"""

from enum import Enum


class Direction(Enum):
    """
    Direction of order/trade/position.
    """
    LONG = "LONG"
    SHORT = "SHORT"
    NET = "NET"


class Offset(Enum):
    """
    Offset of order/trade.
    """
    NONE = ""
    OPEN = "OPEN"
    CLOSE = "CLOSE"
    CLOSETODAY = "CLOSETODAY"
    CLOSEYESTERDAY = "CLOSEYESTERDAY"


class Status(Enum):
    """
    Order status.
    """
    SUBMITTING = "SUBMITTING"
    NOTTRADED = "NOTTRADED"
    PARTTRADED = "PARTTRADED"
    ALLTRADED = "ALLTRADED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class Product(Enum):
    """
    Product class.
    """
    EQUITY = "EQUITY"
    FUTURES = "FUTURES"
    OPTION = "OPTION"
    INDEX = "INDEX"
    FOREX = "FOREX"
    SPOT = "SPOT"
    ETF = "ETF"
    BOND = "BOND"
    WARRANT = "WARRANT"
    SPREAD = "SPREAD"
    FUND = "FUND"
    CFD = "CFD"
    SWAP = "SWAP"


class OrderType(Enum):
    """
    Order type.
    """
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP = "STOP"
    FAK = "FAK"
    FOK = "FOK"
    RFQ = "RFQ"
    ETF = "ETF"


class OptionType(Enum):
    """
    Option type.
    """
    CALL = "CALL"
    PUT = "PUT"


class Exchange(Enum):
    """
    Exchange.
    """
    # Chinese
    CFFEX = "CFFEX"         # China Financial Futures Exchange
    SHFE = "SHFE"           # Shanghai Futures Exchange
    CZCE = "CZCE"           # Zhengzhou Commodity Exchange
    DCE = "DCE"             # Dalian Commodity Exchange
    INE = "INE"             # Shanghai International Energy Exchange
    GFEX = "GFEX"           # Guangzhou Futures Exchange
    SSE = "SSE"             # Shanghai Stock Exchange
    SZSE = "SZSE"           # Shenzhen Stock Exchange
    BSE = "BSE"             # Beijing Stock Exchange
    SHHK = "SHHK"           # Shanghai-HK Stock Connect
    SZHK = "SZHK"           # Shenzhen-HK Stock Connect
    SGE = "SGE"             # Shanghai Gold Exchange
    WXE = "WXE"             # Wuxi Steel Exchange
    CFETS = "CFETS"         # CFETS Bond Market Maker Trading System
    XBOND = "XBOND"         # CFETS X-Bond Anonymous Trading System

    # Global
    SMART = "SMART"         # Smart Router for US stocks
    NYSE = "NYSE"           # New York Stock Exchnage
    NASDAQ = "NASDAQ"       # Nasdaq Exchange
    ARCA = "ARCA"           # ARCA Exchange
    EDGEA = "EDGEA"         # Direct Edge Exchange
    ISLAND = "ISLAND"       # Nasdaq Island ECN
    BATS = "BATS"           # Bats Global Markets
    IEX = "IEX"             # The Investors Exchange
    AMEX = "AMEX"           # American Stock Exchange
    TSE = "TSE"             # Toronto Stock Exchange
    NYMEX = "NYMEX"         # New York Mercantile Exchange
    COMEX = "COMEX"         # COMEX of CME
    GLOBEX = "GLOBEX"       # Globex of CME
    IDEALPRO = "IDEALPRO"   # Forex ECN of Interactive Brokers
    CME = "CME"             # Chicago Mercantile Exchange
    ICE = "ICE"             # Intercontinental Exchange
    SEHK = "SEHK"           # Stock Exchange of Hong Kong
    HKFE = "HKFE"           # Hong Kong Futures Exchange
    SGX = "SGX"             # Singapore Global Exchange
    CBOT = "CBOT"           # Chicago Board of Trade
    CBOE = "CBOE"           # Chicago Board Options Exchange
    CFE = "CFE"             # CBOE Futures Exchange
    DME = "DME"             # Dubai Mercantile Exchange
    EUREX = "EUX"           # Eurex Exchange
    APEX = "APEX"           # Asia Pacific Exchange
    LME = "LME"             # London Metal Exchange
    BMD = "BMD"             # Bursa Malaysia Derivatives
    TOCOM = "TOCOM"         # Tokyo Commodity Exchange
    EUNX = "EUNX"           # Euronext Exchange
    KRX = "KRX"             # Korean Exchange
    OTC = "OTC"             # OTC Product (Forex/CFD/Pink Sheet Equity)
    IBKRATS = "IBKRATS"     # Paper Trading Exchange of IB

    # Crypto
    BINANCE = "BINANCE"     # Binance
    BITMEX = "BITMEX"       # BitMEX
    OKX = "OKX"             # OKX
    DERIBIT = "DERIBIT"     # Deribit
    BYBIT = "BYBIT"         # Bybit
    GATEIO = "GATEIO"       # Gate.io
    COINBASE = "COINBASE"   # Coinbase

    # Special Function
    LOCAL = "LOCAL"         # For local generated data
    GLOBAL = "GLOBAL"       # For those exchanges not supported yet


class Currency(Enum):
    """
    Currency.
    """
    USD = "USD"
    HKD = "HKD"
    CNY = "CNY"
    CAD = "CAD"


class Interval(Enum):
    """
    Interval of bar data.
    """
    MINUTE = "1m"
    HOUR = "1h"
    DAILY = "d"
    WEEKLY = "w"
    TICK = "tick"
