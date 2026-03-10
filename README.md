# Polymarket API Client

A Python client for accessing Polymarket data APIs.

## APIs Used

| API | Purpose | Auth |
|-----|---------|------|
| Gamma API | Markets, events, tags, series | None |
| CLOB API | Orderbook, prices, price history | None (public endpoints) |
| Data API | Trades, positions, activity | None |

## Installation

```bash
pip install requests python-dotenv
```

## Usage

```python
from polymarket import PolymarketClient

client = PolymarketClient()

# Get markets
markets = client.get_markets(limit=10)

# Get market info
market = client.get_market("condition_id_here")

# Get price history
prices = client.get_price_history(
    token_id="token_id_here",
    interval="max",  # max, 1h, 15m, 5m, 1m
    start_ts=1672531200  # optional start timestamp
)

# Get trades
trades = client.get_trades(limit=100)

# Get orderbook
orderbook = client.get_orderbook("token_id_here")

# Get events
events = client.get_events(limit=10)

# Get positions for an address
positions = client.get_positions("0x...")
```

## Environment Variables

- `POLYMARKET_API_KEY` - Optional API key for authenticated endpoints

## References

- [Polymarket API Docs](https://docs.polymarket.com)
- [Gamma API](https://gamma-api.polymarket.com)
- [CLOB API](https://clob.polymarket.com)
- [Data API](https://data-api.polymarket.com)
