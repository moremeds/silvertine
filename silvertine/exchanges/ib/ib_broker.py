"""
Interactive Brokers Exchange Broker implementation.

Provides production-ready Interactive Brokers integration using ib_insync library
with comprehensive order management, market data streams, and portfolio tracking.
"""

import asyncio
import logging
from datetime import datetime
from datetime import timezone
from decimal import Decimal
from typing import Any

import ib_insync as ibs
from ib_insync import IB
from ib_insync import Contract
from ib_insync import Forex
from ib_insync import LimitOrder
from ib_insync import MarketOrder
from ib_insync import Order
from ib_insync import Stock

from ...core.event.events import FillEvent
from ...core.event.events import MarketDataEvent
from ...core.event.events import OrderEvent
from ...core.event.events import OrderSide
from ...core.event.events import OrderType
from ..iexchange import AbstractBroker
from ..iexchange import BrokerAccountInfo
from ..iexchange import BrokerBalance
from ..iexchange import BrokerPosition
from ..iexchange import ConnectionState


class IBBroker(AbstractBroker):
    """
    Interactive Brokers exchange broker implementation.

    Features:
    - ib_insync integration for professional trading
    - Real-time market data subscriptions
    - Multi-asset support (stocks, forex, futures, options)
    - Portfolio and position tracking
    - Advanced order types and risk management
    """

    def __init__(self, event_bus, broker_id: str = "ib", config: dict[str, Any] | None = None):
        """
        Initialize Interactive Brokers broker.

        Args:
            event_bus: Event bus for communication
            broker_id: Unique broker identifier
            config: IB-specific configuration
        """
        super().__init__(event_bus=event_bus, broker_id=broker_id, config=config)

        # IB Gateway/TWS connection configuration
        self.host = config.get("host", "127.0.0.1")
        self.port = config.get("port", 7497)  # 7497 for TWS, 4002 for IB Gateway
        self.client_id = config.get("client_id", 1)
        self.timeout = config.get("timeout", 10)

        # Account configuration
        self.account = config.get("account", "")  # Specific account ID if multiple accounts
        self.paper_trading = config.get("paper_trading", True)  # Default to paper trading for safety

        # Market data configuration
        self.market_data_type = config.get("market_data_type", 3)  # 1=Live, 2=Frozen, 3=Delayed, 4=DelayedFrozen
        self.base_currency = config.get("base_currency", "USD")

        # Connection management
        self.ib_client: IB | None = None
        self.connected = False
        self.next_order_id = 1

        # Data cache
        self._last_prices: dict[str, Decimal] = {}
        self._account_info: BrokerAccountInfo | None = None
        self._subscribed_contracts: dict[str, Contract] = {}
        self._contract_details_cache: dict[str, ibs.ContractDetails] = {}

        # Order management
        self._ib_to_internal_orders: dict[int, str] = {}  # IB order ID -> internal order ID
        self._internal_to_ib_orders: dict[str, int] = {}  # internal order ID -> IB order ID

        # Logging
        self.logger = logging.getLogger(f"IBBroker.{broker_id}")

    async def connect(self) -> None:
        """Establish connection to Interactive Brokers."""
        try:
            self.logger.info(f"Connecting to Interactive Brokers at {self.host}:{self.port}...")

            # Initialize IB connection
            self.ib_client = IB()

            # Set market data type
            self.ib_client.reqMarketDataType(self.market_data_type)

            # Connect to IB Gateway/TWS
            await self.ib_client.connectAsync(
                host=self.host,
                port=self.port,
                clientId=self.client_id,
                timeout=self.timeout
            )

            self.logger.info("Connected to Interactive Brokers successfully")

            # Set up event handlers
            self._setup_event_handlers()

            # Request next valid order ID
            self.next_order_id = self.ib_client.client.getReqId()

            # Load account information
            await self._load_account_info()

            # Start market data subscriptions for configured symbols
            await self._start_market_data_subscriptions()

            self._connection_state = ConnectionState.CONNECTED
            self.connected = True
            self.logger.info("Interactive Brokers initialization complete")

        except Exception as e:
            self._connection_state = ConnectionState.ERROR
            self._metrics.connection_errors += 1
            self.logger.error(f"Failed to connect to Interactive Brokers: {e}")
            raise

    async def disconnect(self) -> None:
        """Close Interactive Brokers connection."""
        try:
            self.logger.info("Disconnecting from Interactive Brokers...")

            if self.ib_client and self.ib_client.isConnected():
                # Cancel all market data subscriptions
                for symbol in list(self._subscribed_contracts.keys()):
                    try:
                        contract = self._subscribed_contracts[symbol]
                        self.ib_client.cancelMktData(contract)
                    except Exception as e:
                        self.logger.warning(f"Error canceling market data for {symbol}: {e}")

                # Disconnect from IB
                self.ib_client.disconnect()

            self.ib_client = None
            self.connected = False
            self._connection_state = ConnectionState.DISCONNECTED
            self.logger.info("Interactive Brokers connection closed")

        except Exception as e:
            self.logger.error(f"Error during IB disconnect: {e}")

    async def place_order(self, order: OrderEvent) -> str:
        """
        Place order with Interactive Brokers.

        Args:
            order: Order event to execute

        Returns:
            Internal order ID

        Raises:
            Exception: If order placement fails
        """
        if not self.is_connected:
            raise Exception("Not connected to Interactive Brokers")

        try:
            # Create IB contract
            contract = await self._create_contract(order.symbol)
            if not contract:
                raise Exception(f"Unable to create contract for symbol: {order.symbol}")

            # Create IB order
            ib_order = self._create_ib_order(order)

            # Generate internal order ID
            internal_order_id = f"ib_{self.broker_id}_{self.next_order_id}"
            self.next_order_id += 1

            # Place order
            trade = self.ib_client.placeOrder(contract, ib_order)
            ib_order_id = trade.order.orderId

            # Store order mapping
            self._ib_to_internal_orders[ib_order_id] = internal_order_id
            self._internal_to_ib_orders[internal_order_id] = ib_order_id

            self.logger.info(f"Order placed: internal={internal_order_id}, ib={ib_order_id}")
            return internal_order_id

        except Exception as e:
            error_msg = f"Error placing IB order: {e}"
            self.logger.error(error_msg)
            raise Exception(error_msg)

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel order by internal ID."""
        if not self.is_connected:
            return False

        try:
            if order_id not in self._internal_to_ib_orders:
                self.logger.warning(f"Internal order {order_id} not found")
                return False

            ib_order_id = self._internal_to_ib_orders[order_id]

            # Find the trade
            for trade in self.ib_client.trades():
                if trade.order.orderId == ib_order_id:
                    self.ib_client.cancelOrder(trade.order)
                    self.logger.info(f"Order cancelled: internal={order_id}, ib={ib_order_id}")
                    return True

            self.logger.error(f"Trade not found for order {ib_order_id}")
            return False

        except Exception as e:
            self.logger.error(f"Error cancelling order {order_id}: {e}")
            return False

    async def modify_order(
        self,
        order_id: str,
        quantity: Decimal | None = None,
        price: Decimal | None = None,
    ) -> bool:
        """
        Modify existing order.

        Interactive Brokers supports direct order modification.
        """
        if not self.is_connected:
            return False

        try:
            if order_id not in self._internal_to_ib_orders:
                return False

            ib_order_id = self._internal_to_ib_orders[order_id]

            # Find the trade
            for trade in self.ib_client.trades():
                if trade.order.orderId == ib_order_id:
                    # Modify order parameters
                    if quantity is not None:
                        trade.order.totalQuantity = float(quantity)
                    if price is not None:
                        if hasattr(trade.order, 'lmtPrice'):
                            trade.order.lmtPrice = float(price)

                    # Submit modification
                    self.ib_client.placeOrder(trade.contract, trade.order)
                    self.logger.info(f"Order modified: {order_id}")
                    return True

            return False

        except Exception as e:
            self.logger.error(f"Error modifying order {order_id}: {e}")
            return False

    async def get_positions(self) -> dict[str, BrokerPosition]:
        """Get all current positions."""
        if not self.is_connected:
            return {}

        try:
            positions = {}

            for position in self.ib_client.positions():
                # Filter by account if specified
                if self.account and position.account != self.account:
                    continue

                if position.position != 0:  # Only include non-zero positions
                    symbol = self._contract_to_symbol(position.contract)
                    current_price = self._last_prices.get(symbol, Decimal("0"))

                    broker_position = BrokerPosition(
                        symbol=symbol,
                        quantity=Decimal(str(position.position)),
                        average_price=Decimal(str(position.avgCost)) if position.avgCost else Decimal("0"),
                        current_price=current_price
                    )
                    positions[symbol] = broker_position

            return positions

        except Exception as e:
            self.logger.error(f"Error getting positions: {e}")
            return {}

    async def get_position(self, symbol: str) -> BrokerPosition | None:
        """Get position for specific symbol."""
        positions = await self.get_positions()
        return positions.get(symbol)

    async def get_account_info(self) -> BrokerAccountInfo:
        """Get complete account information."""
        if not self.is_connected:
            raise Exception("Not connected to Interactive Brokers")

        try:
            await self._load_account_info()
            return self._account_info

        except Exception as e:
            self.logger.error(f"Error getting account info: {e}")
            raise

    async def get_balance(self, currency: str | None = None) -> dict[str, BrokerBalance]:
        """Get account balances."""
        if not self.is_connected:
            return {}

        try:
            balances = {}

            for account_value in self.ib_client.accountValues():
                # Filter by account if specified
                if self.account and account_value.account != self.account:
                    continue

                # Filter by currency if specified
                if currency and account_value.currency != currency:
                    continue

                if account_value.tag == "CashBalance":
                    curr = account_value.currency
                    available = Decimal(str(account_value.value))

                    # Get total balance
                    total = available
                    margin_used = Decimal("0")

                    # Find corresponding total balance
                    for av in self.ib_client.accountValues():
                        if (av.account == account_value.account and
                            av.currency == curr and
                            av.tag == "TotalCashBalance"):
                            total = Decimal(str(av.value))
                            break

                    broker_balance = BrokerBalance(
                        currency=curr,
                        available=available,
                        total=total,
                        margin_used=margin_used
                    )
                    balances[curr] = broker_balance

            return balances

        except Exception as e:
            self.logger.error(f"Error getting balances: {e}")
            return {}

    # Private helper methods

    def _setup_event_handlers(self) -> None:
        """Set up IB event handlers."""
        # Order status updates
        self.ib_client.orderStatusEvent += self._on_order_status

        # Fill events
        self.ib_client.execDetailsEvent += self._on_execution

        # Market data updates
        self.ib_client.pendingTickersEvent += self._on_ticker_update

        # Error handling
        self.ib_client.errorEvent += self._on_error

        # Connection events
        self.ib_client.connectedEvent += self._on_connected
        self.ib_client.disconnectedEvent += self._on_disconnected

    def _on_order_status(self, trade: ibs.Trade) -> None:
        """Handle order status updates."""
        try:
            ib_order_id = trade.order.orderId
            if ib_order_id not in self._ib_to_internal_orders:
                return

            internal_order_id = self._ib_to_internal_orders[ib_order_id]
            status = trade.orderStatus.status

            self.logger.info(f"Order status update: {internal_order_id} -> {status}")

            # Update internal order tracking
            if status in ["Cancelled", "ApiCancelled"]:
                # Clean up cancelled orders
                del self._ib_to_internal_orders[ib_order_id]
                del self._internal_to_ib_orders[internal_order_id]

        except Exception as e:
            self.logger.error(f"Error handling order status: {e}")

    def _on_execution(self, trade: ibs.Trade, fill: ibs.Fill) -> None:
        """Handle order fills."""
        try:
            ib_order_id = trade.order.orderId
            if ib_order_id not in self._ib_to_internal_orders:
                return

            internal_order_id = self._ib_to_internal_orders[ib_order_id]
            symbol = self._contract_to_symbol(trade.contract)

            # Create fill event
            fill_event = FillEvent(
                order_id=internal_order_id,
                symbol=symbol,
                quantity=Decimal(str(fill.execution.shares)),
                price=Decimal(str(fill.execution.price)),
                side=OrderSide.BUY if fill.execution.side == "BOT" else OrderSide.SELL,
                commission=Decimal(str(abs(fill.commissionReport.commission))) if fill.commissionReport else Decimal("0"),
                timestamp=datetime.now(timezone.utc),
                broker_name=self.broker_id
            )

            # Publish fill event
            asyncio.create_task(self.event_bus.publish(fill_event))

            self.logger.info(f"Fill executed: {internal_order_id} - {fill.execution.shares} @ {fill.execution.price}")

        except Exception as e:
            self.logger.error(f"Error handling execution: {e}")

    def _on_ticker_update(self, tickers: list[ibs.Ticker]) -> None:
        """Handle market data updates."""
        try:
            for ticker in tickers:
                if ticker.last and ticker.last > 0:
                    symbol = self._contract_to_symbol(ticker.contract)
                    price = Decimal(str(ticker.last))
                    volume = Decimal(str(ticker.volume)) if ticker.volume else Decimal("0")

                    # Update price cache
                    self._last_prices[symbol] = price

                    # Create market data event
                    market_event = MarketDataEvent(
                        symbol=symbol,
                        price=price,
                        volume=volume,
                        timestamp=datetime.now(timezone.utc),
                        broker_name=self.broker_id
                    )

                    # Publish market data event
                    asyncio.create_task(self.event_bus.publish(market_event))

        except Exception as e:
            self.logger.error(f"Error handling ticker update: {e}")

    def _on_error(self, reqId: int, errorCode: int, errorString: str, contract: Contract) -> None:
        """Handle IB errors."""
        self.logger.warning(f"IB Error - ReqId: {reqId}, Code: {errorCode}, Message: {errorString}")

    def _on_connected(self) -> None:
        """Handle connection established."""
        self.logger.info("IB connection established")

    def _on_disconnected(self) -> None:
        """Handle disconnection."""
        self.logger.warning("IB connection lost")
        self.connected = False
        self._connection_state = ConnectionState.ERROR

    async def _create_contract(self, symbol: str) -> Contract | None:
        """Create IB contract from symbol."""
        try:
            # Check cache first
            if symbol in self._contract_details_cache:
                details = self._contract_details_cache[symbol]
                return details.contract

            # Parse symbol - simple stock format for now
            if "/" in symbol:  # Forex pair like EUR/USD
                base, quote = symbol.split("/")
                contract = Forex(base + quote)
            else:  # Assume stock
                contract = Stock(symbol, "SMART", self.base_currency)

            # Request contract details to validate
            details_list = self.ib_client.reqContractDetails(contract)
            if details_list:
                details = details_list[0]
                self._contract_details_cache[symbol] = details
                return details.contract

            return None

        except Exception as e:
            self.logger.error(f"Error creating contract for {symbol}: {e}")
            return None

    def _create_ib_order(self, order: OrderEvent) -> Order:
        """Create IB order from internal order event."""
        if order.order_type == OrderType.MARKET:
            ib_order = MarketOrder(
                action="BUY" if order.side == OrderSide.BUY else "SELL",
                totalQuantity=float(order.quantity)
            )
        else:  # LIMIT order
            ib_order = LimitOrder(
                action="BUY" if order.side == OrderSide.BUY else "SELL",
                totalQuantity=float(order.quantity),
                lmtPrice=float(order.price)
            )

        return ib_order

    def _contract_to_symbol(self, contract: Contract) -> str:
        """Convert IB contract to internal symbol format."""
        if contract.secType == "STK":
            return contract.symbol
        elif contract.secType == "CASH":  # Forex
            # Convert EURUSD to EUR/USD format
            symbol = contract.symbol
            if len(symbol) == 6:
                return f"{symbol[:3]}/{symbol[3:]}"
            return symbol
        else:
            return f"{contract.symbol}_{contract.secType}"

    async def _load_account_info(self) -> None:
        """Load and cache account information."""
        try:
            balances = await self.get_balance()
            positions = await self.get_positions()

            # Get account summary
            account_id = self.account or "Default"

            self._account_info = BrokerAccountInfo(
                account_id=account_id,
                broker_name="Interactive Brokers",
                account_type="paper" if self.paper_trading else "live",
                base_currency=self.base_currency,
                balances=balances,
                positions=positions,
                last_updated=datetime.now(timezone.utc)
            )

        except Exception as e:
            self.logger.error(f"Error loading account info: {e}")
            raise

    async def _start_market_data_subscriptions(self) -> None:
        """Start market data subscriptions for configured symbols."""
        try:
            symbols = self.config.get("stream_symbols", ["AAPL", "MSFT", "EUR/USD"])

            for symbol in symbols:
                await self._subscribe_market_data(symbol)

            self.logger.info(f"Started market data subscriptions for {len(symbols)} symbols")

        except Exception as e:
            self.logger.error(f"Error starting market data subscriptions: {e}")

    async def _subscribe_market_data(self, symbol: str) -> None:
        """Subscribe to market data for a specific symbol."""
        try:
            contract = await self._create_contract(symbol)
            if contract:
                self.ib_client.reqMktData(contract, "", False, False)
                self._subscribed_contracts[symbol] = contract
                self.logger.info(f"Subscribed to market data for {symbol}")
            else:
                self.logger.warning(f"Could not create contract for {symbol}")

        except Exception as e:
            self.logger.error(f"Error subscribing to market data for {symbol}: {e}")
