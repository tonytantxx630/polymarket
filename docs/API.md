# Polymarket Gamma API Documentation

## Overview

Polymarket provides a hosted service called **Gamma** that indexes on-chain data and provides additional market metadata (categorization, indexed volume, etc.).

**Base URL:** `https://gamma-api.polymarket.com`

---

## Core Concepts

### Markets vs Events

| Concept | Description |
|---------|-------------|
| **Market** | The fundamental tradable unit. A single binary question with Yes/No outcomes. |
| **Event** | A container that groups one or more related markets together. |

**Single-Market Event:**
```
Event: Will Bitcoin reach $100,000 by December 2024?
└── Market: Will Bitcoin reach $100,000 by December 2024? (Yes/No)
```

**Multi-Market Event (Grouped):**
```
Event: Who will win the 2024 Presidential Election?
├── Market: Donald Trump? (Yes/No)
├── Market: Joe Biden? (Yes/No)
├── Market: Kamala Harris? (Yes/No)
└── Market: Other? (Yes/No)
```

---

## Key Discovery

**IMPORTANT:** The Events API and Markets API return DIFFERENT results for the same query:

- **Events API** - Better for finding market groups, searching by event title
- **Markets API** - Returns individual markets, but may miss some markets that only exist via Events API

**Recommendation:** Use Events API as primary, then extract markets from events.

---

## Endpoints

### 1. Get Events

**Endpoint:** `GET /events`

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `slug` | string | Unique event identifier (from URL) |
| `search` | string | Search by event title |
| `limit` | int | Number of results (default varies) |
| `offset` | int | Pagination offset |
| `active` | bool | Filter by active status |
| `closed` | bool | Filter by closed status |
| `tag_id` | int | Filter by category tag |
| `order` | string | Order field: `volume_24hr`, `volume`, `liquidity`, `start_date`, `end_date`, `competitive`, `closed_time` |
| `ascending` | bool | Sort direction (default: false) |
| `related_tags` | bool | Include related tags |
| `exclude_tag_id` | int | Exclude specific tag |

**Examples:**

```bash
# Fetch event by slug
curl "https://gamma-api.polymarket.com/events?slug=will-the-us-invade-venezuela-in-2025"

# Fetch by slug (path endpoint)
curl "https://gamma-api.polymarket.com/events/slug/will-the-us-invade-venezuela-in-2025"

# Search events
curl "https://gamma-api.polymarket.com/events?search=invade+Venezuela&limit=10"

# Get all active events
curl "https://gamma-api.polymarket.com/events?active=true&closed=false&limit=100"

# Get highest volume active events
curl "https://gamma-api.polymarket.com/events?active=true&closed=false&order=volume_24hr&ascending=false&limit=100"
```

---

### 2. Get Single Event

**Endpoint:** `GET /events/{event_id}`

**Examples:**

```bash
curl "https://gamma-api.polymarket.com/events/4690"
```

---

### 3. Get Markets

**Endpoint:** `GET /markets`

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `slug` | string | Unique market identifier |
| `conditionId` | string | Market condition ID (hash) |
| `search` | string | Search by market question |
| `limit` | int | Number of results |
| `offset` | int | Pagination offset |
| `active` | bool | Filter by active status |
| `closed` | bool | Filter by closed status |
| `category` | string | Filter by category |
| `tag_id` | int | Filter by tag |

**Examples:**

```bash
# Fetch market by slug
curl "https://gamma-api.polymarket.com/markets?slug=will-bitcoin-reach-150k"

# Fetch market by conditionId
curl "https://gamma-api.polymarket.com/markets?conditionId=0x62f31557..."

# Search markets (may miss some!)
curl "https://gamma-api.polymarket.com/markets?search=bitcoin&limit=10"

# Get all active markets
curl "https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=100"
```

---

### 4. Get Single Market

**Endpoint:** `GET /markets/{condition_id}`

---

### 5. Get Tags

**Endpoint:** `GET /tags`

```bash
curl "https://gamma-api.polymarket.com/tags?limit=100"
```

---

### 6. Get Sports (for sports markets)

**Endpoint:** `GET /sports`

Returns metadata for sports including tag IDs, images, resolution sources, and series information.

---

## Public Search (BEST METHOD)

**Endpoint:** `GET /public-search`

This is the **recommended** way to search for markets. Unlike the `/markets` search endpoint, this reliably returns all matching markets.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `q` | string | Natural language search query |
| `limit` | int | Max number of events to return |

**Response:** Contains `events` array, where each event has embedded `markets` array.

**Examples:**

```bash
# Search for markets
curl "https://gamma-api.polymarket.com/public-search?q=invade+Venezuela"

# Search with limit
curl "https://gamma-api.polymarket.com/public-search?q=bitcoin&limit=10"
```

**Python Example:**

```python
import requests

query = "airline bankruptcy 2026"
resp = requests.get("https://gamma-api.polymarket.com/public-search", params={"q": query})
data = resp.json()

events = data.get("events", [])
for event in events:
    print(f"Event: {event['title']}")
    for market in event.get("markets", []):
        print(f"  Market: {market['question']}")
```

**⚠️ Important:** Use this instead of `/markets?search=...` which may miss markets!

### Markets API Search Limitation

Some markets are ONLY accessible via the Events API. The Markets API search may return empty results even when markets exist.

**Example:** "Will the U.S. invade Venezuela by...?" markets
- Events API: ✅ Found via `slug=will-the-us-invade-venezuela-in-2025`
- Markets API: ❌ Search returns empty

**Workaround:** Always use Events API first, then extract markets from the event's `markets` array.

---

## API Response Structure

### Event Response

```json
{
  "id": "12345",
  "ticker": "will-the-us-invade-venezuela-in-2025",
  "slug": "will-the-us-invade-venezuela-in-2025",
  "title": "Will the U.S. invade Venezuela by...?",
  "description": "...",
  "startDate": "2025-01-01T00:00:00Z",
  "endDate": "2026-12-31T00:00:00Z",
  "volume": 13718628,
  "liquidity": 100000,
  "active": true,
  "closed": false,
  "archived": false,
  "category": "politics",
  "markets": [
    {
      "id": "...",
      "conditionId": "0x62f31557...",
      "question": "Will the U.S. invade Venezuela by December 31, 2025?",
      "slug": "...",
      "closed": true,
      "outcome": null,
      "resolvedDate": null,
      "volume": 5000000,
      "clobTokenIds": ["...", "..."]
    }
  ]
}
```

### Market Response

```json
{
  "id": "...",
  "conditionId": "0x62f31557...",
  "question": "Will the U.S. invade Venezuela by December 31, 2025?",
  "slug": "...",
  "endDate": "2025-12-31T00:00:00Z",
  "category": "politics",
  "volume": 5000000,
  "liquidity": 100000,
  "active": true,
  "closed": false,
  "outcomes": ["Yes", "No"],
  "outcomePrices": ["0.45", "0.55"],
  "clobTokenIds": ["53135...", "60869..."],
  "events": [...]
}
```

---

## Best Practices

1. **For individual markets:** Use slug method for direct lookups
2. **For category browsing:** Use tag filtering
3. **For complete discovery:** Use events endpoint with pagination
4. **Always use** `active=true&closed=false` unless you need historical data
5. **Use Events API first** - events contain their associated markets
6. **Store conditionIds** - Once found, cache them for direct access

---

## Other APIs

### CLOB API (Trading)

**Base URL:** `https://clob.polymarket.com`

- `/markets` - Get all markets from CLOB
- `/price?token_id=xxx` - Get current price
- `/prices-history?market=xxx` - Get price history
- `/orderbook?token_id=xxx` - Get order book

### Data API (Trades/Positions)

**Base URL:** `https://data-api.polymarket.com`

- `/trades` - Get trade history
- `/positions` - Get positions
- `/info?conditionId=xxx` - Get market info

---

## References

- Official Docs: https://docs.polymarket.com
- Gamma API: https://gamma-api.polymarket.com
- GitHub: https://github.com/Polymarket
