from silvertine.util.constants import Status, Direction, OrderType, Exchange, Product, OptionType, Currency, Interval
from silvertine.util.utility import ZoneInfo
from tzlocal import get_localzone_name


# 委托状态映射
STATUS_IB2VT: dict[str, Status] = {
    "ApiPending": Status.SUBMITTING,
    "PendingSubmit": Status.SUBMITTING,
    "PreSubmitted": Status.NOTTRADED,
    "Submitted": Status.NOTTRADED,
    "ApiCancelled": Status.CANCELLED,
    "Cancelled": Status.CANCELLED,
    "Filled": Status.ALLTRADED,
    "Inactive": Status.REJECTED,
}

# 多空方向映射
DIRECTION_VT2IB: dict[Direction, str] = {Direction.LONG: "BUY", Direction.SHORT: "SELL"}
DIRECTION_IB2VT: dict[str, Direction] = {v: k for k, v in DIRECTION_VT2IB.items()}
DIRECTION_IB2VT["BOT"] = Direction.LONG
DIRECTION_IB2VT["SLD"] = Direction.SHORT

# 委托类型映射
ORDERTYPE_VT2IB: dict[OrderType, str] = {
    OrderType.LIMIT: "LMT",
    OrderType.MARKET: "MKT",
    OrderType.STOP: "STP"
}
ORDERTYPE_IB2VT: dict[str, OrderType] = {v: k for k, v in ORDERTYPE_VT2IB.items()}

# 交易所映射
EXCHANGE_VT2IB: dict[Exchange, str] = {
    Exchange.SMART: "SMART",
    Exchange.NYMEX: "NYMEX",
    Exchange.COMEX: "COMEX",
    Exchange.GLOBEX: "GLOBEX",
    Exchange.IDEALPRO: "IDEALPRO",
    Exchange.CME: "CME",
    Exchange.CBOT: "CBOT",
    Exchange.CBOE: "CBOE",
    Exchange.ICE: "ICE",
    Exchange.SEHK: "SEHK",
    Exchange.SSE: "SEHKNTL",
    Exchange.SZSE: "SEHKSZSE",
    Exchange.HKFE: "HKFE",
    Exchange.CFE: "CFE",
    Exchange.TSE: "TSE",
    Exchange.NYSE: "NYSE",
    Exchange.NASDAQ: "NASDAQ",
    Exchange.AMEX: "AMEX",
    Exchange.ARCA: "ARCA",
    Exchange.EDGEA: "EDGEA",
    Exchange.ISLAND: "ISLAND",
    Exchange.BATS: "BATS",
    Exchange.IEX: "IEX",
    Exchange.IBKRATS: "IBKRATS",
    Exchange.OTC: "PINK",
    Exchange.SGX: "SGX",
    Exchange.EUREX: "EUREX",
    Exchange.LME: "LMEOTC"
}
EXCHANGE_IB2VT: dict[str, Exchange] = {v: k for k, v in EXCHANGE_VT2IB.items()}

# 产品类型映射
PRODUCT_IB2VT: dict[str, Product] = {
    "STK": Product.EQUITY,
    "CASH": Product.FOREX,
    "CMDTY": Product.SPOT,
    "FUT": Product.FUTURES,
    "OPT": Product.OPTION,
    "FOP": Product.OPTION,
    "CONTFUT": Product.FUTURES,
    "IND": Product.INDEX,
    "CFD": Product.CFD
}

# 期权类型映射
OPTION_IB2VT: dict[str, OptionType] = {
    "C": OptionType.CALL,
    "CALL": OptionType.CALL,
    "P": OptionType.PUT,
    "PUT": OptionType.PUT
}

# 货币类型映射
CURRENCY_VT2IB: dict[Currency, str] = {
    Currency.USD: "USD",
    Currency.CAD: "CAD",
    Currency.CNY: "CNY",
    Currency.HKD: "HKD",
}

# 切片数据字段映射
TICKFIELD_IB2VT: dict[int, str] = {
    0: "bid_volume_1",
    1: "bid_price_1",
    2: "ask_price_1",
    3: "ask_volume_1",
    4: "last_price",
    5: "last_volume",
    6: "high_price",
    7: "low_price",
    8: "volume",
    9: "pre_close",
    10: "bid",
    11: "ask",
    12: "last",
    13: "model",
    14: "open_price",
    86: "open_interest"
}

# 账户类型映射
ACCOUNTFIELD_IB2VT: dict[str, str] = {
    "NetLiquidationByCurrency": "balance",
    "NetLiquidation": "balance",
    "UnrealizedPnL": "positionProfit",
    "AvailableFunds": "available",
    "MaintMarginReq": "margin",
}

# 数据频率映射
INTERVAL_VT2IB: dict[Interval, str] = {
    Interval.MINUTE: "1 min",
    Interval.HOUR: "1 hour",
    Interval.DAILY: "1 day",
}

# 其他常量
LOCAL_TZ = ZoneInfo(get_localzone_name())
JOIN_SYMBOL: str = "-"