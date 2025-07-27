"""
IB Symbol Rules

SPY-USD-STK   SMART
EUR-USD-CASH  IDEALPRO
XAUUSD-USD-CMDTY  SMART
ES-202002-USD-FUT  GLOBEX
SI-202006-1000-USD-FUT  NYMEX
ES-2020006-C-2430-50-USD-FOP  GLOBEX

ConId is also supported for symbol.
"""

import shelve
from copy import copy
from datetime import datetime, timedelta
from decimal import Decimal
from threading import Condition, Thread

from ibapi.client import EClient
from ibapi.common import BarData as IbBarData
from ibapi.common import OrderId, TickAttrib, TickerId
from ibapi.contract import Contract, ContractDetails
from ibapi.execution import Execution
from ibapi.order import Order
from ibapi.order_cancel import OrderCancel
from ibapi.order_state import OrderState
from ibapi.ticktype import TickType, TickTypeEnum
from ibapi.wrapper import EWrapper
from silvertine.adapter.base_adapter import BaseAdapter
from silvertine.core.engine import EventEngine
from silvertine.core.event import EVENT_TIMER, Event
from silvertine.util.constants import Direction, Exchange, OrderType, Product, Status
from silvertine.util.object import (AccountData, BarData, CancelRequest, ContractData,
                                    HistoryRequest, OrderData, OrderRequest,
                                    PositionData, SubscribeRequest, TickData, TradeData)
from silvertine.util.utility import ZoneInfo, get_file_path

from .ib_mappings import (ACCOUNTFIELD_IB2VT, DIRECTION_IB2VT, DIRECTION_VT2IB,
                          EXCHANGE_IB2VT, EXCHANGE_VT2IB, INTERVAL_VT2IB, JOIN_SYMBOL,
                          OPTION_IB2VT, ORDERTYPE_IB2VT, ORDERTYPE_VT2IB, PRODUCT_IB2VT,
                          STATUS_IB2VT, TICKFIELD_IB2VT)

LOCAL_TZ = ZoneInfo("Asia/Shanghai")


class IBAdapter(BaseAdapter):
    """
    Silvertine trading interface for Interactive Brokers.
    """

    default_name: str = "IB"

    default_setting: dict[str, str|int ] = {
        "TWS Address": "127.0.0.1",
        "TWS Port": 7497,
        "Client ID": 1,
        "Trading Account": ""
    }

    exchanges: list[Exchange] = list(EXCHANGE_VT2IB.keys())

    def __init__(self, event_engine: EventEngine, adapter_name: str) -> None:
        """Constructor"""
        super().__init__(event_engine=event_engine, adapter_name=adapter_name)

        self.api: IbApi = IbApi(self)
        self.count: int = 0

    def connect(self, setting: dict[str, str | int | float | bool]) -> None:
        """Connect to the trading interface"""
        host: str = str(setting["TWS Address"])
        port: int = int(setting["TWS Port"])
        clientid: int = int(setting["Client ID"])
        account: str = str(setting["Trading Account"])

        self.api.connect(host, port, clientid, account)

        self.event_engine.register(EVENT_TIMER, self.process_timer_event)

    def close(self) -> None:
        """Close the interface"""
        self.api.close()

    def subscribe(self, req: SubscribeRequest) -> None:
        """Subscribe to market data"""
        self.api.subscribe(req)

    def send_order(self, req: OrderRequest) -> str:
        """Send an order"""
        return self.api.send_order(req)

    def cancel_order(self, req: CancelRequest) -> None:
        """Cancel an order"""
        self.api.cancel_order(req)

    def query_account(self) -> None:
        """Query account balance"""
        pass

    def query_position(self) -> None:
        """Query holdings"""
        pass

    def query_history(self, req: HistoryRequest) -> list[BarData]:
        """Query historical data"""
        return self.api.query_history(req)

    def process_timer_event(self, event: Event) -> None:
        """Process timer events"""
        self.count += 1
        if self.count < 10:
            return
        self.count = 0

        self.api.check_connection()


class IbApi(EWrapper):
    """IB API interface"""

    data_filename: str = "ib_contract_data.db"
    data_filepath: str = str(get_file_path(data_filename))

    def __init__(self, adapter: IBAdapter) -> None:
        """Constructor"""
        super().__init__()

        self.adapter: IBAdapter = adapter
        self.adapter_name: str = adapter.adapter_name

        self.status: bool = False

        self.reqid: int = 0
        self.orderid: int = 0
        self.clientid: int = 0
        self.history_reqid: int = 0
        self.account: str = ""

        self.ticks: dict[int, TickData] = {}
        self.orders: dict[str, OrderData] = {}
        self.accounts: dict[str, AccountData] = {}
        self.contracts: dict[str, ContractData] = {}

        self.subscribed: dict[str, SubscribeRequest] = {}
        self.data_ready: bool = False

        self.history_req: HistoryRequest | None = None
        self.history_condition: Condition = Condition()
        self.history_buf: list[BarData] = []

        self.reqid_symbol_map: dict[int, str] = {}              # reqid: subscribe tick symbol
        self.reqid_underlying_map: dict[int, Contract] = {}     # reqid: query option underlying

        self.client: EClient = EClient(self)

        self.ib_contracts: dict[str, Contract] = {}

    def connectAck(self) -> None:
        """Callback for successful connection"""
        self.status = True
        self.adapter.write_log("IB TWS connected successfully")

        self.load_contract_data()

        self.data_ready = False

    def connectionClosed(self) -> None:
        """Callback for connection loss"""
        self.status = False
        self.adapter.write_log("IB TWS connection lost")

    def nextValidId(self, orderId: int) -> None:
        """Callback for next valid order ID"""
        super().nextValidId(orderId)

        if not self.orderid:
            self.orderid = orderId

    def currentTime(self, time: int) -> None:
        """Callback for current server time of IB"""
        super().currentTime(time)

        dt: datetime = datetime.fromtimestamp(time)
        time_string: str = dt.strftime("%Y-%m-%d %H:%M:%S.%f")

        msg: str = f"Server time: {time_string}"
        self.adapter.write_log(msg)

    def error(
        self,
        reqId: TickerId,
        errorCode: int,
        errorString: str,
        advancedOrderRejectJson: str = ""
    ) -> None:
        """Callback for error requests"""
        super().error(reqId, errorCode, errorString)

        # Information messages with codes 2000-2999 are not errors
        if reqId == self.history_reqid and errorCode not in range(2000, 3000):
            self.history_condition.acquire()
            self.history_condition.notify()
            self.history_condition.release()

        msg: str = f"Information message, code: {errorCode}, content: {errorString}"
        self.adapter.write_log(msg)

        # Market data server connected
        if errorCode == 2104 and not self.data_ready:
            self.data_ready = True

            self.client.reqCurrentTime()

            reqs: list[SubscribeRequest] = list(self.subscribed.values())
            self.subscribed.clear()
            for req in reqs:
                self.subscribe(req)

    def tickPrice(self, reqId: TickerId, tickType: TickType, price: float, attrib: TickAttrib) -> None:
        """Callback for tick price updates"""
        super().tickPrice(reqId, tickType, price, attrib)

        if tickType not in TICKFIELD_IB2VT:
            return

        tick: TickData | None = self.ticks.get(reqId, None)
        if not tick:
            self.adapter.write_log(f"tickPrice function received an unsolicited push, reqId: {reqId}")
            return

        name: str = TICKFIELD_IB2VT[tickType]
        setattr(tick, name, price)

        # Update the name field of the tick data
        contract: ContractData | None = self.contracts.get(tick.vt_symbol, None)
        if contract:
            tick.name = contract.name

        # Locally calculate the tick time and latest price for Forex of IDEALPRO and Spot Commodity
        if tick.exchange == Exchange.IDEALPRO or "CMDTY" in tick.symbol:
            if not tick.bid_price_1 or not tick.ask_price_1 or tick.low_price == -1:
                return
            tick.last_price = (tick.bid_price_1 + tick.ask_price_1) / 2
            tick.datetime = datetime.now(LOCAL_TZ)

        self.adapter.on_tick(copy(tick))

    def tickSize(self, reqId: TickerId, tickType: TickType, size: Decimal) -> None:
        """Callback for tick size updates"""
        super().tickSize(reqId, tickType, size)

        if tickType not in TICKFIELD_IB2VT:
            return

        tick: TickData | None = self.ticks.get(reqId, None)
        if not tick:
            self.adapter.write_log(f"tickSize function received an unsolicited push, reqId: {reqId}")
            return

        name: str = TICKFIELD_IB2VT[tickType]
        setattr(tick, name, float(size))

        self.adapter.on_tick(copy(tick))

    def tickString(self, reqId: TickerId, tickType: TickType, value: str) -> None:
        """Callback for tick string updates"""
        super().tickString(reqId, tickType, value)

        if tickType != TickTypeEnum.LAST_TIMESTAMP:
            return

        tick: TickData | None = self.ticks.get(reqId, None)
        if not tick:
            self.adapter.write_log(f"tickString function received an unsolicited push, reqId: {reqId}")
            return

        dt: datetime = datetime.fromtimestamp(int(value))
        tick.datetime = dt.replace(tzinfo=LOCAL_TZ)

        self.adapter.on_tick(copy(tick))

    def tickOptionComputation(
        self,
        reqId: TickerId,
        tickType: TickType,
        tickAttrib: int,
        impliedVol: float,
        delta: float,
        optPrice: float,
        pvDividend: float,
        gamma: float,
        vega: float,
        theta: float,
        undPrice: float
    ) -> None:
        """Callback for tick option data pushes"""
        super().tickOptionComputation(
            reqId,
            tickType,
            tickAttrib,
            impliedVol,
            delta,
            optPrice,
            pvDividend,
            gamma,
            vega,
            theta,
            undPrice,
        )

        tick: TickData | None = self.ticks.get(reqId, None)
        if not tick:
            self.adapter.write_log(f"tickOptionComputation function received an unsolicited push, reqId: {reqId}")
            return

        prefix: str = TICKFIELD_IB2VT[tickType]

        if tick.extra is None:
            tick.extra = {}
        tick.extra["underlying_price"] = undPrice

        if optPrice:
            tick.extra[f"{prefix}_price"] = optPrice
            tick.extra[f"{prefix}_impv"] = impliedVol
            tick.extra[f"{prefix}_delta"] = delta
            tick.extra[f"{prefix}_gamma"] = gamma
            tick.extra[f"{prefix}_theta"] = theta
            tick.extra[f"{prefix}_vega"] = vega
        else:
            tick.extra[f"{prefix}_price"] = 0
            tick.extra[f"{prefix}_impv"] = 0
            tick.extra[f"{prefix}_delta"] = 0
            tick.extra[f"{prefix}_gamma"] = 0
            tick.extra[f"{prefix}_theta"] = 0
            tick.extra[f"{prefix}_vega"] = 0

    def tickSnapshotEnd(self, reqId: int) -> None:
        """Callback for when a market data snapshot is finished"""
        super().tickSnapshotEnd(reqId)

        tick: TickData | None = self.ticks.get(reqId, None)
        if not tick:
            self.adapter.write_log(f"tickSnapshotEnd function received an unsolicited push, reqId: {reqId}")
            return

        self.adapter.write_log(f"{tick.vt_symbol} market data snapshot query successful")

    def orderStatus(
        self,
        orderId: OrderId,
        status: str,
        filled: Decimal,
        remaining: Decimal,
        avgFillPrice: float,
        permId: int,
        parentId: int,
        lastFillPrice: float,
        clientId: int,
        whyHeld: str,
        mktCapPrice: float,
    ) -> None:
        """Callback for order status updates"""
        super().orderStatus(
            orderId,
            status,
            filled,
            remaining,
            avgFillPrice,
            permId,
            parentId,
            lastFillPrice,
            clientId,
            whyHeld,
            mktCapPrice,
        )

        orderid: str = str(orderId)
        order: OrderData = self.orders.get(orderid, None) # type: ignore
        if not order:
            return

        order.traded = float(filled)

        # Filter out "canceling" status
        order_status: Status = STATUS_IB2VT.get(status, None) # type: ignore
        if order_status:
            order.status = order_status

        self.adapter.on_order(copy(order))

    def openOrder(
        self,
        orderId: OrderId,
        ib_contract: Contract,
        ib_order: Order,
        orderState: OrderState,
    ) -> None:
        """Callback for new orders"""
        super().openOrder(orderId, ib_contract, ib_order, orderState)

        orderid: str = str(orderId)

        if ib_order.orderRef:
            dt: datetime = datetime.strptime(ib_order.orderRef, "%Y-%m-%d %H:%M:%S")
        else:
            dt = datetime.now()

        # Prioritize using locally cached order records to resolve issues with exchange information changing when SMART is used
        order: OrderData = self.orders.get(orderid, None) # type: ignore
        if not order:
            order = OrderData(
                symbol=self.generate_symbol(ib_contract),
                exchange=EXCHANGE_IB2VT.get(ib_contract.exchange, Exchange.SMART),
                type=ORDERTYPE_IB2VT[ib_order.orderType],
                orderid=orderid,
                direction=DIRECTION_IB2VT[ib_order.action],
                volume=ib_order.totalQuantity,
                datetime=dt,
                adapter_name=self.adapter_name,
            )

        if order.type == OrderType.LIMIT:
            order.price = ib_order.lmtPrice
        elif order.type == OrderType.STOP:
            order.price = ib_order.auxPrice

        self.orders[orderid] = order
        self.adapter.on_order(copy(order))

    def updateAccountValue(self, key: str, val: str, currency: str, accountName: str) -> None:
        """Callback for account updates"""
        super().updateAccountValue(key, val, currency, accountName)

        if not currency or key not in ACCOUNTFIELD_IB2VT:
            return

        accountid: str = f"{accountName}.{currency}"
        account: AccountData = self.accounts.get(accountid, None) # type: ignore
        if not account:
            account = AccountData(
                accountid=accountid,
                adapter_name=self.adapter_name
            )
            self.accounts[accountid] = account

        name: str = ACCOUNTFIELD_IB2VT[key]
        setattr(account, name, float(val))

    def updatePortfolio(
        self,
        contract: Contract,
        position: Decimal,
        marketPrice: float,
        marketValue: float,
        averageCost: float,
        unrealizedPNL: float,
        realizedPNL: float,
        accountName: str,
    ) -> None:
        """Callback for position updates"""
        super().updatePortfolio(
            contract,
            position,
            marketPrice,
            marketValue,
            averageCost,
            unrealizedPNL,
            realizedPNL,
            accountName,
        )

        if contract.exchange:
            exchange: Exchange = EXCHANGE_IB2VT.get(contract.exchange, None) # type: ignore
        elif contract.primaryExchange:
            exchange = EXCHANGE_IB2VT.get(contract.primaryExchange, None) # type: ignore
        else:
            exchange = Exchange.SMART   # Use smart routing by default

        if not exchange:
            msg: str = f"Unsupported exchange holding exists: {self.generate_symbol(contract)} {contract.exchange} {contract.primaryExchange}"
            self.adapter.write_log(msg)
            return

        try:
            ib_size: int = int(contract.multiplier)
        except ValueError:
            ib_size = 1
        price = averageCost / ib_size

        pos: PositionData = PositionData(
            symbol=self.generate_symbol(contract),
            exchange=exchange,
            direction=Direction.NET,
            volume=float(position),
            price=price,
            pnl=unrealizedPNL,
            adapter_name=self.adapter_name,
        )
        self.adapter.on_position(pos)

    def updateAccountTime(self, timeStamp: str) -> None:
        """Callback for account update time"""
        super().updateAccountTime(timeStamp)
        for account in self.accounts.values():
            self.adapter.on_account(copy(account))

    def contractDetails(self, reqId: int, contractDetails: ContractDetails) -> None:
        """Callback for contract data updates"""
        super().contractDetails(reqId, contractDetails)

        # Extract contract information
        ib_contract: Contract = contractDetails.contract

        # Handle the case where the contract multiplier is 0
        if not ib_contract.multiplier:
            ib_contract.multiplier = 1

        # For string-style symbols, get them from the cache
        if reqId in self.reqid_symbol_map:
            symbol: str = self.reqid_symbol_map[reqId]
        # Otherwise, use numeric-style symbols by default
        else:
            symbol = str(ib_contract.conId)

        # Filter out unsupported types
        product: Product = PRODUCT_IB2VT.get(ib_contract.secType, None) # type: ignore
        if not product:
            return

        # Generate the contract
        contract: ContractData = ContractData(
            symbol=symbol,
            exchange=EXCHANGE_IB2VT[ib_contract.exchange],
            name=contractDetails.longName,
            product=PRODUCT_IB2VT[ib_contract.secType],
            size=float(ib_contract.multiplier),
            pricetick=contractDetails.minTick,
            min_volume=contractDetails.minSize,
            net_position=True,
            history_data=True,
            stop_supported=True,
            adapter_name=self.adapter_name,
        )

        if contract.product == Product.OPTION:
            underlying_symbol: str = str(contractDetails.underConId)

            contract.option_portfolio = underlying_symbol + "_O"
            contract.option_type = OPTION_IB2VT.get(ib_contract.right, None)
            contract.option_strike = ib_contract.strike
            contract.option_index = str(ib_contract.strike)
            contract.option_expiry = datetime.strptime(ib_contract.lastTradeDateOrContractMonth, "%Y%m%d")
            contract.option_underlying = underlying_symbol + "_" + ib_contract.lastTradeDateOrContractMonth

        if contract.vt_symbol not in self.contracts:
            self.adapter.on_contract(contract)

            self.contracts[contract.vt_symbol] = contract
            self.ib_contracts[contract.vt_symbol] = ib_contract

    def contractDetailsEnd(self, reqId: int) -> None:
        """Callback for when contract data updates are finished"""
        super().contractDetailsEnd(reqId)

        # Only process option queries
        underlying: Contract = self.reqid_underlying_map.get(reqId, None)
        if not underlying:
            return

        # Output log information
        symbol: str = self.generate_symbol(underlying)
        exchange: Exchange = EXCHANGE_IB2VT.get(underlying.exchange, Exchange.SMART)
        vt_symbol: str = f"{symbol}.{exchange.value}"

        self.adapter.write_log(f"{vt_symbol} option chain query successful")

        # Save option contracts to a file
        self.save_contract_data()

    def execDetails(self, reqId: int, contract: Contract, execution: Execution) -> None:
        """Callback for trade data updates"""
        super().execDetails(reqId, contract, execution)

        # Parse execution time
        time_str: str = execution.time
        time_split: list = time_str.split(" ")
        words_count: int = 3

        if len(time_split) == words_count:
            timezone = time_split[-1]
            time_str = time_str.replace(f" {timezone}", "")
            tz = ZoneInfo(timezone)
        elif len(time_split) == (words_count - 1):
            tz = LOCAL_TZ
        else:
            self.adapter.write_log(f"Received unsupported time format: {time_str}")
            return

        dt: datetime = datetime.strptime(time_str, "%Y%m%d %H:%M:%S")
        dt = dt.replace(tzinfo=tz)

        if tz != LOCAL_TZ:
            dt = dt.astimezone(LOCAL_TZ)

        # Prioritize using locally cached order records to resolve issues with exchange information changing when SMART is used
        orderid: str = str(execution.orderId)
        order: OrderData = self.orders.get(orderid, None) # type: ignore

        if order:
            symbol: str = order.symbol
            exchange: Exchange = order.exchange
        else:
            symbol = self.generate_symbol(contract)
            exchange = EXCHANGE_IB2VT.get(contract.exchange, Exchange.SMART)

        # Push trade data
        trade: TradeData = TradeData(
            symbol=symbol,
            exchange=exchange,
            orderid=orderid,
            tradeid=str(execution.execId),
            direction=DIRECTION_IB2VT[execution.side],
            price=execution.price,
            volume=float(execution.shares),
            datetime=dt,
            adapter_name=self.adapter_name,
        )

        self.adapter.on_trade(trade)

    def managedAccounts(self, accountsList: str) -> None:
        """Callback for all sub-accounts"""
        super().managedAccounts(accountsList)

        if not self.account:
            for account_code in accountsList.split(","):
                if account_code:
                    self.account = account_code

        self.adapter.write_log(f"Currently used trading account: {self.account}")
        self.client.reqAccountUpdates(True, self.account)

    def historicalData(self, reqId: int, ib_bar: IbBarData) -> None:
        """Callback for historical data updates"""
        # Daily and weekly data format is %Y%m%d
        time_str: str = ib_bar.date
        time_split: list = time_str.split(" ")
        words_count: int = 3

        if ":" not in time_str:
            words_count -= 1

        if len(time_split) == words_count:
            timezone = time_split[-1]
            time_str = time_str.replace(f" {timezone}", "")
            tz = ZoneInfo(timezone)
        elif len(time_split) == (words_count - 1):
            tz = LOCAL_TZ
        else:
            self.adapter.write_log(f"Received unsupported time format: {time_str}")
            return

        if ":" in time_str:
            dt: datetime = datetime.strptime(time_str, "%Y%m%d %H:%M:%S")
        else:
            dt = datetime.strptime(time_str, "%Y%m%d")
        dt = dt.replace(tzinfo=tz)

        if tz != LOCAL_TZ:
            dt = dt.astimezone(LOCAL_TZ)

        bar: BarData = BarData(
            symbol=self.history_req.symbol,
            exchange=self.history_req.exchange,
            datetime=dt,
            interval=self.history_req.interval,
            volume=float(ib_bar.volume),
            open_price=ib_bar.open,
            high_price=ib_bar.high,
            low_price=ib_bar.low,
            close_price=ib_bar.close,
            adapter_name=self.adapter_name
        )
        if bar.volume < 0:
            bar.volume = 0

        self.history_buf.append(bar)

    def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:
        """Callback for when historical data query is finished"""
        self.history_condition.acquire()
        self.history_condition.notify()
        self.history_condition.release()

    def connect(
        self,
        host: str,
        port: int,
        clientid: int,
        account: str
    ) -> None:
        """Connect to TWS"""
        if self.status:
            return

        self.host = host
        self.port = port
        self.clientid = clientid
        self.account = account

        self.client.connect(host, port, clientid)
        self.thread = Thread(target=self.client.run)
        self.thread.start()

    def check_connection(self) -> None:
        """Check connection"""
        if self.client.isConnected():
            return

        if self.status:
            self.close()

        self.client.connect(self.host, self.port, self.clientid)

        self.thread = Thread(target=self.client.run)
        self.thread.start()

    def close(self) -> None:
        """Disconnect from TWS"""
        if not self.status:
            return

        self.save_contract_data()

        self.status = False
        self.client.disconnect()

    def query_option_portfolio(self, underlying: Contract) -> None:
        """Query option chain contract data"""
        if not self.status:
            return

        # Parse IB option contract
        ib_contract: Contract = Contract()
        ib_contract.symbol = underlying.symbol
        ib_contract.currency = underlying.currency

        # Futures options must use the specified exchange
        if underlying.secType == "FUT":
            ib_contract.secType = "FOP"
            ib_contract.exchange = underlying.exchange
        # Spot options support smart routing
        else:
            ib_contract.secType = "OPT"
            ib_contract.exchange = "SMART"

        # Query contract information through TWS
        self.reqid += 1
        self.client.reqContractDetails(self.reqid, ib_contract)

        # Cache the query record
        self.reqid_underlying_map[self.reqid] = underlying

    def subscribe(self, req: SubscribeRequest) -> None:
        """Subscribe to tick data updates"""
        if not self.status:
            return

        if req.exchange not in EXCHANGE_VT2IB:
            self.adapter.write_log(f"Unsupported exchange {req.exchange}")
            return

        if " " in req.symbol:
            self.adapter.write_log("Subscription failed, symbol contains spaces")
            return

        # Filter out duplicate subscriptions
        if req.vt_symbol in self.subscribed:
            return
        self.subscribed[req.vt_symbol] = req

        # Parse IB contract details
        ib_contract: Contract = generate_ib_contract(req.symbol, req.exchange)
        if not ib_contract:
            self.adapter.write_log("Symbol parsing failed, please check the format")
            return

        # Query contract information through TWS
        self.reqid += 1
        self.client.reqContractDetails(self.reqid, ib_contract)

        # If a string-style symbol is used, it needs to be cached
        if "-" in req.symbol:
            self.reqid_symbol_map[self.reqid] = req.symbol

        # Subscribe to tick data and create a tick object buffer
        self.reqid += 1
        self.client.reqMktData(self.reqid, ib_contract, "", False, False, [])

        tick: TickData = TickData(
            symbol=req.symbol,
            exchange=req.exchange,
            datetime=datetime.now(LOCAL_TZ),
            adapter_name=self.adapter_name
        )
        tick.extra = {}

        self.ticks[self.reqid] = tick

    def send_order(self, req: OrderRequest) -> str:
        """Send an order"""
        if not self.status:
            return ""

        if req.exchange not in EXCHANGE_VT2IB:
            self.adapter.write_log(f"Unsupported exchange: {req.exchange}")
            return ""

        if req.type not in ORDERTYPE_VT2IB:
            self.adapter.write_log(f"Unsupported price type: {req.type}")
            return ""

        if " " in req.symbol:
            self.adapter.write_log("Order failed, symbol contains spaces")
            return ""

        self.orderid += 1

        ib_contract: Contract = generate_ib_contract(req.symbol, req.exchange)
        if not ib_contract:
            return ""

        ib_order: Order = Order()
        ib_order.orderId = self.orderid
        ib_order.clientId = self.clientid
        ib_order.action = DIRECTION_VT2IB[req.direction]
        ib_order.orderType = ORDERTYPE_VT2IB[req.type]
        ib_order.totalQuantity = Decimal(req.volume)
        ib_order.account = self.account
        ib_order.orderRef = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if req.type == OrderType.LIMIT:
            ib_order.lmtPrice = req.price
        elif req.type == OrderType.STOP:
            ib_order.auxPrice = req.price

        self.client.placeOrder(self.orderid, ib_contract, ib_order)
        self.client.reqIds(1)

        order: OrderData = req.create_order_data(str(self.orderid), self.adapter_name)
        self.orders[order.orderid] = order
        self.adapter.on_order(order)
        return order.vt_orderid

    def cancel_order(self, req: CancelRequest) -> None:
        """Cancel an order"""
        if not self.status:
            return

        cancel: OrderCancel = OrderCancel()
        self.client.cancelOrder(int(req.orderid), cancel)

    def query_history(self, req: HistoryRequest) -> list[BarData]:
        """Query historical data"""
        contract: ContractData = self.contracts[req.vt_symbol]
        if not contract:
            self.adapter.write_log(f"Contract not found: {req.vt_symbol}, please subscribe first")
            return []

        self.history_req = req

        self.reqid += 1

        ib_contract: Contract = generate_ib_contract(req.symbol, req.exchange)

        if req.end:
            end: datetime = req.end
        else:
            end = datetime.now(LOCAL_TZ)

        # Use UTC end time
        utc_tz: ZoneInfo = ZoneInfo("UTC")
        utc_end: datetime = end.astimezone(utc_tz)
        end_str: str = utc_end.strftime("%Y%m%d-%H:%M:%S")

        delta: timedelta = end - req.start
        days: int = delta.days
        if days < 365:
            duration: str = f"{days} D"
        else:
            duration = f"{delta.days/365:.0f} Y"

        bar_size: str = INTERVAL_VT2IB[req.interval]    # type: ignore

        if contract.product in [Product.SPOT, Product.FOREX]:
            bar_type: str = "MIDPOINT"
        else:
            bar_type = "TRADES"

        self.history_reqid = self.reqid
        self.client.reqHistoricalData(
            self.reqid,
            ib_contract,
            end_str,
            duration,
            bar_size,
            bar_type,
            0,
            1,
            False,
            []
        )

        self.history_condition.acquire()    # Wait for asynchronous data to be returned
        self.history_condition.wait(600)
        self.history_condition.release()

        history: list[BarData] = self.history_buf
        self.history_buf = []       # Create a new buffer list
        self.history_req = None

        return history

    def load_contract_data(self) -> None:
        """Load local contract data"""
        f = shelve.open(self.data_filepath)
        self.contracts = f.get("contracts", {})
        self.ib_contracts = f.get("ib_contracts", {})
        f.close()

        for contract in self.contracts.values():
            self.adapter.on_contract(contract)

        self.adapter.write_log("Successfully loaded local cached contract information")

    def save_contract_data(self) -> None:
        """Save contract data to a local file"""
        # Before saving, ensure that all contract data interface names are set to IB to avoid issues with other modules
        contracts: dict[str, ContractData] = {}
        for vt_symbol, contract in self.contracts.items():
            c: ContractData = copy(contract)
            c.adapter_name = "IB"
            contracts[vt_symbol] = c

        f = shelve.open(self.data_filepath)
        f["contracts"] = contracts
        f["ib_contracts"] = self.ib_contracts
        f.close()

    def generate_symbol(self, ib_contract: Contract) -> str:
        """Generate a contract symbol"""
        # Generate a string-style symbol
        fields: list = [ib_contract.symbol]

        if ib_contract.secType in ["FUT", "OPT", "FOP"]:
            fields.append(ib_contract.lastTradeDateOrContractMonth)

        if ib_contract.secType in ["OPT", "FOP"]:
            fields.append(ib_contract.right)
            fields.append(str(ib_contract.strike))
            fields.append(str(ib_contract.multiplier))

        fields.append(ib_contract.currency)
        fields.append(ib_contract.secType)

        symbol: str = JOIN_SYMBOL.join(fields)
        exchange: Exchange = EXCHANGE_IB2VT.get(ib_contract.exchange, Exchange.SMART)
        vt_symbol: str = f"{symbol}.{exchange.value}"

        # If the string-style symbol is not found in the contract information, use the numeric symbol
        if vt_symbol not in self.contracts:
            symbol = str(ib_contract.conId)

        return symbol

    def query_tick(self, vt_symbol: str) -> None:
        """Query tick data"""
        if not self.status:
            return

        contract: ContractData | None = self.contracts.get(vt_symbol, None)
        if not contract:
            self.adapter.write_log(f"Failed to query tick data, could not find contract data for {vt_symbol}")
            return

        ib_contract: Contract = self.ib_contracts.get(vt_symbol, None)
        if not contract:
            self.adapter.write_log(f"Failed to query tick data, could not find IB contract data for {vt_symbol}")
            return

        self.reqid += 1
        self.client.reqMktData(self.reqid, ib_contract, "", True, False, [])

        tick: TickData = TickData(
            symbol=contract.symbol,
            exchange=contract.exchange,
            datetime=datetime.now(LOCAL_TZ),
            adapter_name=self.adapter_name
        )
        tick.extra = {}

        self.ticks[self.reqid] = tick

    def unsubscribe(self, req: SubscribeRequest) -> None:
        """Unsubscribe from tick data updates"""
        # Remove subscription record
        if req.vt_symbol not in self.subscribed:
            return
        self.subscribed.pop(req.vt_symbol)

        # Get subscription ID
        cancel_id: int = 0
        for reqid, tick in self.ticks.items():
            if tick.vt_symbol == req.vt_symbol:
                cancel_id = reqid
                break

        # Send unsubscribe request
        self.client.cancelMktData(cancel_id)


def generate_ib_contract(symbol: str, exchange: Exchange) -> Contract | None:
    """Generate an IB contract"""
    # String-style symbol
    if "-" in symbol:
        try:
            fields: list[str] = symbol.split(JOIN_SYMBOL)

            ib_contract: Contract = Contract()
            ib_contract.exchange = EXCHANGE_VT2IB[exchange]
            ib_contract.secType = fields[-1]
            ib_contract.currency = fields[-2]
            ib_contract.symbol = fields[0]

            if ib_contract.secType in ["FUT", "OPT", "FOP"]:
                ib_contract.lastTradeDateOrContractMonth = fields[1]

            if ib_contract.secType == "FUT":
                if len(fields) == 5:
                    ib_contract.multiplier = int(fields[2])

            if ib_contract.secType in ["OPT", "FOP"]:
                ib_contract.right = fields[2]
                ib_contract.strike = float(fields[3])
                ib_contract.multiplier = int(fields[4])
        except IndexError:
            ib_contract = None
    # Numeric-style symbol (ConId)
    else:
        if symbol.isdigit():
            ib_contract = Contract()
            ib_contract.exchange = EXCHANGE_VT2IB[exchange]
            ib_contract.conId = symbol
        else:
            ib_contract = None

    return ib_contract
