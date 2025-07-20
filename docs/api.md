# Silvertine API Documentation

This document describes the REST API and WebSocket endpoints for the Silvertine trading system.

## API Overview

The Silvertine API provides programmatic access to:
- Trading operations (orders, positions, strategies)
- Real-time market data and system status
- Configuration and monitoring
- Risk management controls

### Base URL
- **Development**: `http://localhost:8000`
- **Production**: `https://your-domain.com`

### Authentication
All API endpoints require JWT authentication via the `Authorization` header:
```
Authorization: Bearer <jwt_token>
```

## REST API Endpoints

### Authentication

#### POST /auth/login
Authenticate and receive JWT token.

**Request Body:**
```json
{
  "username": "string",
  "password": "string"
}
```

**Response:**
```json
{
  "access_token": "string",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### System Management

#### GET /api/v1/system/status
Get current system status and health.

**Response:**
```json
{
  "status": "running",
  "uptime": 3600,
  "version": "0.1.0",
  "components": {
    "event_bus": "connected",
    "database": "connected",
    "exchanges": {
      "binance_testnet": "connected",
      "interactive_brokers": "disconnected"
    }
  }
}
```

#### POST /api/v1/system/emergency-stop
Emergency stop all trading activities.

**Response:**
```json
{
  "message": "Emergency stop activated",
  "timestamp": "2024-01-15T14:30:00Z",
  "stopped_strategies": ["strategy_1", "strategy_2"]
}
```

### Strategy Management

#### GET /api/v1/strategies
List all available strategies.

**Response:**
```json
{
  "strategies": [
    {
      "id": "strategy_1",
      "name": "Moving Average Crossover",
      "status": "running",
      "pnl": 234.56,
      "trades_today": 5
    }
  ]
}
```

#### POST /api/v1/strategies/{strategy_id}/start
Start a specific strategy.

**Path Parameters:**
- `strategy_id`: Strategy identifier

**Response:**
```json
{
  "message": "Strategy started successfully",
  "strategy_id": "strategy_1",
  "started_at": "2024-01-15T14:30:00Z"
}
```

#### POST /api/v1/strategies/{strategy_id}/stop
Stop a specific strategy.

### Position Management

#### GET /api/v1/positions
Get current positions.

**Query Parameters:**
- `exchange` (optional): Filter by exchange
- `symbol` (optional): Filter by symbol

**Response:**
```json
{
  "positions": [
    {
      "symbol": "BTCUSDT",
      "side": "long",
      "size": 0.5,
      "entry_price": 45000.0,
      "current_price": 45500.0,
      "unrealized_pnl": 250.0,
      "realized_pnl": 0.0
    }
  ]
}
```

#### GET /api/v1/positions/{symbol}
Get position details for a specific symbol.

### Order Management

#### POST /api/v1/orders
Place a new order.

**Request Body:**
```json
{
  "symbol": "BTCUSDT",
  "side": "buy",
  "type": "limit",
  "quantity": 0.1,
  "price": 45000.0,
  "time_in_force": "GTC",
  "strategy_id": "strategy_1"
}
```

**Response:**
```json
{
  "order_id": "order_123",
  "status": "submitted",
  "submitted_at": "2024-01-15T14:30:00Z"
}
```

#### GET /api/v1/orders
List orders with optional filtering.

**Query Parameters:**
- `status` (optional): Filter by order status
- `symbol` (optional): Filter by symbol
- `limit` (optional): Limit number of results

#### DELETE /api/v1/orders/{order_id}
Cancel an existing order.

### Performance Metrics

#### GET /api/v1/performance/metrics
Get current performance metrics.

**Response:**
```json
{
  "total_pnl": 1234.56,
  "daily_pnl": 123.45,
  "max_drawdown": -5.2,
  "sharpe_ratio": 1.85,
  "win_rate": 0.65,
  "total_trades": 250,
  "avg_trade_duration": 4.5
}
```

#### GET /api/v1/performance/equity-curve
Get equity curve data for charting.

**Query Parameters:**
- `period`: Time period (1d, 1w, 1m, 3m, 1y)
- `interval`: Data interval (1m, 5m, 1h, 1d)

## WebSocket API

### Connection
Connect to WebSocket endpoint:
```
ws://localhost:8000/ws/{channel}
```

### Authentication
Send JWT token immediately after connection:
```json
{
  "type": "auth",
  "token": "your_jwt_token"
}
```

### Available Channels

#### `/ws/market-data`
Real-time market data updates.

**Message Format:**
```json
{
  "type": "market_data",
  "symbol": "BTCUSDT",
  "price": 45123.45,
  "volume": 1234.56,
  "timestamp": "2024-01-15T14:30:00Z"
}
```

#### `/ws/positions`
Real-time position updates.

**Message Format:**
```json
{
  "type": "position_update",
  "symbol": "BTCUSDT",
  "side": "long",
  "size": 0.5,
  "unrealized_pnl": 250.0,
  "timestamp": "2024-01-15T14:30:00Z"
}
```

#### `/ws/signals`
Trading signal notifications.

**Message Format:**
```json
{
  "type": "signal",
  "strategy_id": "strategy_1",
  "symbol": "BTCUSDT",
  "signal": "buy",
  "strength": 0.85,
  "timestamp": "2024-01-15T14:30:00Z"
}
```

#### `/ws/system-events`
System status and event notifications.

**Message Format:**
```json
{
  "type": "system_event",
  "event": "strategy_started",
  "strategy_id": "strategy_1",
  "message": "Strategy started successfully",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

## Error Handling

### HTTP Status Codes
- `200 OK`: Successful request
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

### Error Response Format
```json
{
  "error": {
    "code": "INVALID_SYMBOL",
    "message": "The specified symbol is not supported",
    "details": {
      "symbol": "INVALID",
      "supported_symbols": ["BTCUSDT", "ETHUSDT"]
    }
  }
}
```

## Rate Limiting

API endpoints are rate limited to prevent abuse:
- **Authentication**: 5 requests per minute
- **Trading Operations**: 100 requests per minute
- **Market Data**: 1000 requests per minute
- **System Operations**: 20 requests per minute

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1642248000
```

## SDK Examples

### Python SDK Usage
```python
import asyncio
from silvertine_sdk import SilvertineClient

async def main():
    client = SilvertineClient(
        base_url="http://localhost:8000",
        username="your_username",
        password="your_password"
    )
    
    # Get system status
    status = await client.get_system_status()
    print(f"System status: {status.status}")
    
    # Place an order
    order = await client.place_order(
        symbol="BTCUSDT",
        side="buy",
        type="limit",
        quantity=0.1,
        price=45000.0
    )
    print(f"Order placed: {order.order_id}")
    
    # Subscribe to real-time data
    async def on_market_data(data):
        print(f"Market data: {data.symbol} @ {data.price}")
    
    await client.subscribe_market_data(on_market_data)

if __name__ == "__main__":
    asyncio.run(main())
```

### WebSocket Client Example
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/market-data');

ws.onopen = function() {
    // Authenticate
    ws.send(JSON.stringify({
        type: 'auth',
        token: 'your_jwt_token'
    }));
};

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Market data:', data);
};
```

## See Also

- [Architecture Documentation](architecture.md) - System architecture overview
- [Deployment Guide](deployment.md) - Production deployment instructions
- [Development Guide](development.md) - Development workflow and best practices