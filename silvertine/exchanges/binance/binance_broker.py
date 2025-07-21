"""
Binance Exchange Broker implementation.

Provides production-ready Binance integration with WebSocket streams, order management,
and comprehensive error handling using the official binance-connector library.
"""

import asyncio
import json
import logging
from datetime import datetime
from datetime import timezone
from decimal import Decimal
from typing import Any

from binance.spot import Spot
from binance.websocket.spot.websocket_stream import SpotWebsocketStreamClient

from ...core.event.events import MarketDataEvent
from ...core.event.events import OrderEvent
from ...core.event.events import OrderSide
from ...core.event.events import OrderType
from ..iexchange import AbstractBroker
from ..iexchange import BrokerAccountInfo
from ..iexchange import BrokerBalance
from ..iexchange import BrokerPosition
from ..iexchange import ConnectionState


class BinanceAPIException(Exception):
    """Binance API exception wrapper."""
    pass


class BinanceOrderException(Exception):
    """Binance order exception wrapper."""
    pass


class BinanceBroker(AbstractBroker):
    """
    Binance Exchange broker implementation using official binance-connector.

    Features:
    - Official binance-connector REST and WebSocket integration
    - Real-time WebSocket market data streams
    - Order management with comprehensive error handling
    - Testnet and production environment support
    - Rate limiting and connection management
    """

    def __init__(self, event_bus, broker_id: str = "binance", config: dict[str, Any] | None = None):
        """
        Initialize Binance broker.

        Args:
            event_bus: Event bus for communication
            broker_id: Unique broker identifier
            config: Binance-specific configuration
        """
        super().__init__(event_bus=event_bus, broker_id=broker_id, config=config)

        # Binance configuration
        self.api_key = config.get("api_key", "")
        self.api_secret = config.get("api_secret", "")
        self.testnet = config.get("testnet", True)  # Default to testnet for safety
        self.base_currency = config.get("base_currency", "USDT")

        # Determine base URL based on testnet setting
        if self.testnet:
            self.base_url = "https://testnet.binance.vision"
        else:
            self.base_url = "https://api.binance.com"

        # Connection management
        self.client: Spot | None = None
        self.ws_client: SpotWebsocketStreamClient | None = None
        self.connected = False

        # Market data cache
        self._last_prices: dict[str, Decimal] = {}
        self._account_info: BrokerAccountInfo | None = None

        # Order management
        self._symbol_info: dict[str, dict] = {}
        self._min_notional: dict[str, Decimal] = {}

        # Logging
        self.logger = logging.getLogger(f"BinanceBroker.{broker_id}")

    async def connect(self) -> None:
        """Establish connection to Binance."""
        try:
            self.logger.info(f"Connecting to Binance {'testnet' if self.testnet else 'mainnet'}...")

            # Initialize Spot client
            self.client = Spot(
                api_key=self.api_key,
                api_secret=self.api_secret,
                base_url=self.base_url
            )

            # Test connection
            server_time = self.client.time()
            self.logger.info(f"Connected to Binance server, time: {server_time}")

            # Load exchange info and symbol configurations
            await self._load_exchange_info()

            # Initialize WebSocket client for market data
            await self._initialize_websocket()

            # Update account information
            await self._update_account_info()

            self._connection_state = ConnectionState.CONNECTED
            self.connected = True
            self.logger.info("Binance connection established successfully")

        except Exception as e:
            self._connection_state = ConnectionState.ERROR
            self._metrics.connection_errors += 1
            self.logger.error(f"Failed to connect to Binance: {e}")
            raise

    async def disconnect(self) -> None:
        """Close Binance connection."""
        try:
            self.logger.info("Disconnecting from Binance...")

            # Stop WebSocket client
            if self.ws_client:
                self.ws_client.stop()
                self.ws_client = None

            # REST client doesn't need explicit disconnect
            self.client = None
            self.connected = False

            self._connection_state = ConnectionState.DISCONNECTED
            self.logger.info("Binance connection closed")

        except Exception as e:
            self.logger.error(f"Error during Binance disconnect: {e}")

    async def place_order(self, order: OrderEvent) -> str:
        """
        Place order with Binance.

        Args:
            order: Order event to execute

        Returns:
            Binance order ID

        Raises:
            BinanceOrderException: If order placement fails
        """
        if not self.is_connected:
            raise BinanceOrderException("Not connected to Binance")

        try:
            # Prepare order parameters
            params = {
                'symbol': order.symbol,
                'side': 'BUY' if order.side == OrderSide.BUY else 'SELL',
                'type': 'MARKET' if order.order_type == OrderType.MARKET else 'LIMIT',
                'quantity': float(order.quantity),
            }

            if order.order_type == OrderType.LIMIT:
                params['price'] = float(order.price)
                params['timeInForce'] = 'GTC'

            # Place order via Binance API
            result = self.client.new_order(**params)

            binance_order_id = str(result["orderId"])

            self.logger.info(f"Order placed successfully: {binance_order_id}")
            return binance_order_id

        except Exception as e:
            error_msg = f"Binance API error placing order: {e}"
            self.logger.error(error_msg)
            raise BinanceOrderException(error_msg)

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel order by ID."""
        if not self.is_connected:
            return False

        try:
            # Find the order in our active orders
            if order_id not in self._active_orders:
                self.logger.warning(f"Order {order_id} not found in active orders")
                return False

            order = self._active_orders[order_id]

            # Cancel via Binance API
            self.client.cancel_order(symbol=order.symbol, orderId=order_id)

            self.logger.info(f"Order cancelled successfully: {order_id}")
            return True

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

        Note: Binance doesn't support direct order modification.
        This implements cancel-and-replace logic.
        """
        if not self.is_connected:
            return False

        try:
            # Get original order
            if order_id not in self._active_orders:
                return False

            original_order = self._active_orders[order_id]

            # Cancel original order
            if not await self.cancel_order(order_id):
                return False

            # Create new order with modified parameters
            new_order = OrderEvent(
                symbol=original_order.symbol,
                side=original_order.side,
                quantity=quantity or original_order.quantity,
                price=price or original_order.price,
                order_type=original_order.order_type,
                time_in_force=original_order.time_in_force
            )

            # Place new order
            new_order_id = await self.place_order(new_order)

            self.logger.info(f"Order modified: {order_id} -> {new_order_id}")
            return True

        except Exception as e:
            self.logger.error(f"Error modifying order {order_id}: {e}")
            return False

    async def get_positions(self) -> dict[str, BrokerPosition]:
        """Get all current positions."""
        if not self.is_connected:
            return {}

        try:
            account_info = self.client.account()
            positions = {}

            for balance in account_info["balances"]:
                asset = balance["asset"]
                free = Decimal(balance["free"])
                locked = Decimal(balance["locked"])
                total = free + locked

                if total > 0:  # Only include non-zero positions
                    # For spot trading, create position representation
                    position = BrokerPosition(
                        symbol=asset,
                        quantity=total,
                        average_price=Decimal("0"),  # Not available for spot
                        current_price=self._last_prices.get(f"{asset}{self.base_currency}", Decimal("0"))
                    )
                    positions[asset] = position

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
            raise Exception("Not connected to Binance")

        try:
            await self._update_account_info()
            return self._account_info

        except Exception as e:
            self.logger.error(f"Error getting account info: {e}")
            raise

    async def get_balance(self, currency: str | None = None) -> dict[str, BrokerBalance]:
        """Get account balances."""
        if not self.is_connected:
            return {}

        try:
            account_info = self.client.account()
            balances = {}

            for balance in account_info["balances"]:
                asset = balance["asset"]

                # Filter by currency if specified
                if currency and asset != currency:
                    continue

                free = Decimal(balance["free"])
                locked = Decimal(balance["locked"])
                total = free + locked

                if total > 0 or asset == self.base_currency:  # Include base currency even if zero
                    broker_balance = BrokerBalance(
                        currency=asset,
                        available=free,
                        total=total,
                        margin_used=locked  # Locked balance as "margin used"
                    )
                    balances[asset] = broker_balance

            return balances

        except Exception as e:
            self.logger.error(f"Error getting balances: {e}")
            return {}

    # Private helper methods

    async def _load_exchange_info(self) -> None:
        """Load exchange info and symbol configurations."""
        try:
            exchange_info = self.client.exchange_info()

            for symbol_info in exchange_info["symbols"]:
                symbol = symbol_info["symbol"]
                self._symbol_info[symbol] = symbol_info

                # Extract minimum notional value
                for filter_info in symbol_info["filters"]:
                    if filter_info["filterType"] == "MIN_NOTIONAL":
                        self._min_notional[symbol] = Decimal(filter_info["minNotional"])
                        break

            self.logger.info(f"Loaded info for {len(self._symbol_info)} symbols")

        except Exception as e:
            self.logger.error(f"Error loading exchange info: {e}")
            raise

    async def _initialize_websocket(self) -> None:
        """Initialize WebSocket client for market data."""
        try:
            def message_handler(_, message):
                asyncio.create_task(self._handle_websocket_message(message))

            # Determine WebSocket URL based on testnet setting
            if self.testnet:
                stream_url = 'wss://stream.testnet.binance.vision'
            else:
                stream_url = 'wss://stream.binance.com:9443'

            self.ws_client = SpotWebsocketStreamClient(
                on_message=message_handler,
                stream_url=stream_url
            )

            # Start streaming for configured symbols
            symbols = self.config.get("stream_symbols", ["BTCUSDT", "ETHUSDT"])
            for symbol in symbols:
                self.ws_client.ticker(symbol=symbol.lower())

            self.logger.info(f"Started WebSocket streams for {len(symbols)} symbols")

        except Exception as e:
            self.logger.error(f"Error initializing WebSocket: {e}")

    async def _handle_websocket_message(self, message: dict[str, Any]) -> None:
        """Handle WebSocket message and update prices."""
        try:
            # Parse JSON message
            if isinstance(message, str):
                data = json.loads(message)
            else:
                data = message

            # Handle ticker stream messages
            if data.get("e") == "24hrTicker":
                symbol = data["s"]
                price = Decimal(data["c"])  # Current close price
                volume = Decimal(data["v"])  # Volume

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

                # Publish to event bus
                await self.event_bus.publish(market_event)

        except Exception as e:
            self.logger.error(f"Error processing WebSocket message: {e}")

    async def _update_account_info(self) -> None:
        """Update cached account information."""
        try:
            balances = await self.get_balance()
            positions = await self.get_positions()

            self._account_info = BrokerAccountInfo(
                account_id=self.broker_id,
                broker_name="Binance",
                account_type="spot",  # Binance spot trading
                base_currency=self.base_currency,
                balances=balances,
                positions=positions,
                last_updated=datetime.now(timezone.utc)
            )

        except Exception as e:
            self.logger.error(f"Error updating account info: {e}")
            raise
