"""
Polymarket API Client

Access Polymarket markets, events, positions, trades, prices, and order books.
"""

import os
import time
from typing import Optional, List, Dict, Any, Tuple

import requests


class PolymarketClient:
    """Client for Polymarket APIs.

    This is a *read-only* wrapper in the current workspace: markets/events,
    prices/history, orderbooks, trades, positions.

    For fills + orderbook-related events, we also support the Polymarket
    orderbook subgraph (GraphQL) via Goldsky.
    """

    GAMMA_API = "https://gamma-api.polymarket.com"
    CLOB_API = "https://clob.polymarket.com"
    DATA_API = "https://data-api.polymarket.com"

    # Orderbook subgraph (GraphQL) — good for fills history.
    # Can be overridden per-call, or via env var POLYMARKET_SUBGRAPH_ORDERBOOK.
    SUBGRAPH_ORDERBOOK = (
        "https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw"
        "/subgraphs/orderbook-subgraph/0.0.1/gn"
    )

    # Subgraph encodes USDC as assetId "0". Conditional shares use 1e8 units.
    USDC_ASSET_ID = "0"
    SHARE_DECIMALS = 8
    USDC_DECIMALS = 6
    
    def __init__(self, api_key: Optional[str] = None, *, timeout: Tuple[float, float] = (5.0, 30.0), max_retries: int = 2):
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"Authorization": f"Bearer {api_key}"})

    def _request_json(self, method: str, url: str, *, params: Optional[Dict[str, Any]] = None, json: Any = None, timeout: Optional[Tuple[float, float]] = None) -> Any:
        """HTTP helper with default timeout + small retry for transient failures."""
        t = timeout or self.timeout
        last_err: Optional[BaseException] = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.request(method, url, params=params, json=json, timeout=t)
                resp.raise_for_status()
                return resp.json()
            except requests.HTTPError as e:
                last_err = e
                status = getattr(e.response, "status_code", None)
                # Retry 429/5xx only (idempotent endpoints)
                if status in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                raise
            except (requests.Timeout, requests.ConnectionError) as e:
                last_err = e
                if attempt < self.max_retries:
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                raise
        raise RuntimeError(f"request failed after retries: {last_err}")
    
    # ==================== MARKETS (Gamma API) ====================
    
    def get_markets(
        self,
        limit: int = 100,
        closed: Optional[bool] = None,
        offset: Optional[int] = None,
        cursor: Optional[int] = None,
        **kwargs,
    ) -> List[Dict]:
        """Get markets list (Gamma API).

        Notes on pagination (important):
        - In practice, Gamma's `/markets` supports **offset-based pagination** via the
          `offset` query param. This returns a *different* page.
        - The `cursor` param is accepted by this client for backwards compatibility,
          but may be ignored by the public endpoint.

        Args:
            limit: Number of markets to return
            closed: Filter by closed markets
            offset: Offset for pagination (recommended)
            cursor: Pagination cursor (may be ignored by Gamma)
            **kwargs: Additional filters (category, slug, tag_id, etc.)
        """
        params = {"limit": limit, **kwargs}
        if closed is not None:
            params["closed"] = closed
        if offset is not None:
            params["offset"] = offset
        if cursor is not None:
            params["cursor"] = cursor

        return self._request_json("GET", f"{self.GAMMA_API}/markets", params=params)
    
    def get_market(self, condition_id: str) -> Optional[Dict[str, Any]]:
        """Get single market by condition ID."""
        data = self._request_json("GET", f"{self.GAMMA_API}/markets", params={"conditionId": condition_id})
        return data[0] if data else None
    
    def get_market_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """Get market by slug."""
        data = self._request_json("GET", f"{self.GAMMA_API}/markets", params={"slug": slug})
        return data[0] if data else None
    
    def search_markets(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search markets by query (Gamma /markets?search=...).

        Note: this is *not* the same as the public-search workflow; see
        `search_markets_workflow` for higher-recall search.
        """
        return self._request_json(
            "GET",
            f"{self.GAMMA_API}/markets",
            params={"search": query, "limit": limit},
        )
    
    # ==================== EVENTS (Gamma API) ====================
    
    def get_events(
        self,
        limit: int = 50,
        closed: Optional[bool] = None,
        offset: Optional[int] = None,
        **kwargs,
    ) -> List[Dict]:
        """Get events list (Gamma API).

        Gamma supports offset-based pagination via the `offset` query param.

        Args:
            limit: Number of events to return
            closed: Filter by closed events
            offset: Offset for pagination
            **kwargs: Additional filters
        """
        params = {"limit": limit, **kwargs}
        if closed is not None:
            params["closed"] = closed
        if offset is not None:
            params["offset"] = offset

        return self._request_json("GET", f"{self.GAMMA_API}/events", params=params)
    
    def get_event(self, event_id: str) -> Dict:
        """Get single event by ID."""
        return self._request_json("GET", f"{self.GAMMA_API}/events/{event_id}")
    
    # ==================== PUBLIC SEARCH (NEW!) ====================
    
    def public_search(
        self,
        query: str,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Search markets using the public search endpoint.
        
        This is the BEST method for finding markets by keyword.
        Unlike /markets search, this reliably returns all matching markets.
        
        Args:
            query: Natural language search query (e.g., "airline bankruptcy 2026")
            limit: Max number of events to return
        
        Returns:
            Dict with 'events' (list), 'pagination' info
        """
        return self._request_json(
            "GET",
            f"{self.GAMMA_API}/public-search",
            params={"q": query, "limit": limit},
        )
    
    def search_markets_public(
        self,
        query: str,
        limit: int = 20
    ) -> List[Dict]:
        """
        Search markets using public search endpoint and return flat market list.
        
        Args:
            query: Search query
            limit: Max events to search
        
        Returns:
            List of market dicts from all matching events
        """
        data = self.public_search(query, limit)
        events = data.get("events", [])
        
        markets = []
        for event in events:
            event_markets = event.get("markets", [])
            for m in event_markets:
                m["_event_title"] = event.get("title")
                m["_event_slug"] = event.get("slug")
            markets.extend(event_markets)
        
        return markets
    
    def search_markets_workflow(
        self,
        query: str,
        active_only: bool = False,
        resolved_only: bool = False,
        limit: int = 50,
        min_volume: float = 0,
        include_event_info: bool = True
    ) -> Dict[str, Any]:
        """
        Reusable workflow for searching Polymarket markets.
        
        This is the main entry point for market searches - handles all the logic
        of finding markets via public search and filtering results.
        
        Args:
            query: Natural language search query (e.g., "Citi earnings", "Bitcoin price")
            active_only: Only return active (non-closed) markets
            resolved_only: Only return resolved markets
            limit: Max events to search
            min_volume: Filter by minimum volume (USD)
            include_event_info: Include event title/slug in market data
        
        Returns:
            Dict with:
                - 'events': List of matching events
                - 'markets': Flat list of matching markets
                - 'summary': Search stats (total, active, resolved, by_event)
        """
        # Step 1: Search via public search endpoint
        data = self.public_search(query, limit)
        events = data.get("events", [])
        
        # Step 2: Extract markets from events
        markets = []
        for event in events:
            event_markets = event.get("markets", [])
            for m in event_markets:
                if include_event_info:
                    m["_event_title"] = event.get("title")
                    m["_event_slug"] = event.get("slug")
                    m["_event_volume"] = event.get("volume", 0)
            markets.extend(event_markets)
        
        # Step 3: Filter by status
        if active_only:
            markets = [m for m in markets if not m.get("closed")]
        elif resolved_only:
            markets = [m for m in markets if m.get("closed")]
        
        # Step 4: Filter by volume
        if min_volume > 0:
            markets = [m for m in markets 
                      if float(m.get("volume", 0) or 0) >= min_volume]
        
        # Step 5: Build summary
        active_count = sum(1 for m in markets if not m.get("closed"))
        resolved_count = sum(1 for m in markets if m.get("closed"))
        
        # Group by event
        by_event = {}
        for m in markets:
            event_title = m.get("_event_title", "Unknown")
            if event_title not in by_event:
                by_event[event_title] = []
            by_event[event_title].append(m)
        
        return {
            "query": query,
            "events": events,
            "markets": markets,
            "summary": {
                "total_events": len(events),
                "total_markets": len(markets),
                "active_markets": active_count,
                "resolved_markets": resolved_count,
                "by_event": {k: len(v) for k, v in by_event.items()}
            }
        }
    
    def print_search_results(self, results: Dict[str, Any], show_details: bool = True) -> None:
        """
        Print search results in a readable format.
        
        Args:
            results: Output from search_markets_workflow()
            show_details: Show volume, status for each market
        """
        summary = results["summary"]
        markets = results["markets"]
        
        print(f"\n🔍 Search: \"{results['query']}\"")
        print(f"📊 Found: {summary['total_events']} events, {summary['total_markets']} markets")
        print(f"   Active: {summary['active_markets']} | Resolved: {summary['resolved_markets']}")
        
        if show_details and markets:
            print("\n" + "="*60)
            
            # Group by event for cleaner output
            current_event = None
            for m in markets:
                event_title = m.get("_event_title", "Unknown")
                if event_title != current_event:
                    current_event = event_title
                    print(f"\n📁 {event_title}")
                    print("-" * 50)
                
                q = m.get("question", "N/A")
                closed = m.get("closed")
                vol = float(m.get("volume", 0) or 0)
                outcome = m.get("outcome")
                
                status = "🔵 Active" if not closed else f"✅ Resolved: {outcome}"
                vol_str = f"${vol:,.0f}" if vol else "$0"
                
                print(f"  • {q}")
                print(f"    {status} | Vol: {vol_str}")
        
        print()
    
    # ==================== PRICES (CLOB API) ====================
    
    def _resample_price_history(
        self,
        history: List[Dict],
        target_fidelity: int,
    ) -> List[Dict]:
        """Resample CLOB price history into coarser time buckets.

        The Polymarket CLOB `/prices-history` endpoint can return *sparse* points for
        coarse fidelities (e.g. 1800s), so we fetch minute-level points then resample.

        Strategy: bucket by floor(t/target_fidelity)*target_fidelity and keep the
        last price in each bucket.
        """
        if not history:
            return []

        # Normalize + sort
        rows = []
        for pt in history:
            t = pt.get("t") or pt.get("timestamp")
            p = pt.get("p") or pt.get("price")
            if t is None or p is None:
                continue
            try:
                rows.append((int(t), float(p)))
            except Exception:
                continue
        rows.sort(key=lambda x: x[0])

        buckets: Dict[int, float] = {}
        for t, p in rows:
            bt = (t // target_fidelity) * target_fidelity
            buckets[bt] = p  # keep last within bucket

        return [{"t": t, "p": p} for t, p in sorted(buckets.items())]

    def get_price_history(
        self,
        token_id: str,
        interval: str = "max",
        fidelity: int = 1440,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
        *,
        source_fidelity: int = 60,
        resample: bool = True,
    ) -> Dict:
        """Get price history for a token.

        IMPORTANT: The CLOB API can return very few datapoints when you request a
        coarse fidelity directly (e.g. 30m / 1h / 1d). By default, we fetch at
        minute-level (source_fidelity=60) and resample to the requested fidelity.

        Args:
            token_id: CLOB token ID
            interval: max, 1h, 15m, 5m, 1m
            fidelity: target bucket size in seconds (1800=30m, 3600=hourly, 1440=daily)
            start_ts: Start timestamp (Unix)
            end_ts: End timestamp (Unix)
            source_fidelity: fetch granularity in seconds (default 60)
            resample: when True (default), fetch minute-level and resample to fidelity
        """

        # If someone asks for sub-minute, just pass through.
        if not resample or fidelity <= source_fidelity:
            params = {
                "market": token_id,
                "interval": interval,
                "fidelity": fidelity,
            }
            if start_ts:
                params["startTs"] = start_ts
            if end_ts:
                params["endTs"] = end_ts

            return self._request_json("GET", f"{self.CLOB_API}/prices-history", params=params)

        # Fetch minute-level, then resample.
        params = {
            "market": token_id,
            "interval": interval,
            "fidelity": source_fidelity,
        }
        if start_ts:
            params["startTs"] = start_ts
        if end_ts:
            params["endTs"] = end_ts

        raw = self._request_json("GET", f"{self.CLOB_API}/prices-history", params=params) or {}

        raw_hist = raw.get("history") or raw.get("data") or raw.get("prices") or []
        resampled = self._resample_price_history(raw_hist, target_fidelity=fidelity)

        # Preserve the existing return shape (dict with `history`).
        return {
            "history": resampled,
            "_meta": {
                "requested_fidelity": fidelity,
                "source_fidelity": source_fidelity,
                "raw_points": len(raw_hist),
                "resampled_points": len(resampled),
            },
        }
    
    def get_price(self, token_id: str) -> float:
        """Get current price for a token."""
        data = self._request_json("GET", f"{self.CLOB_API}/price", params={"token_id": token_id})
        return (data or {}).get("price", 0)
    
    def get_prices(self, token_ids: List[str]) -> Dict[str, float]:
        """Get current prices for multiple tokens."""
        return self._request_json(
            "GET",
            f"{self.CLOB_API}/prices",
            params={"token_ids": ",".join(token_ids)},
        )
    
    # ==================== FEES (CLOB API) ====================

    def get_fee_rate_bps(self, token_id: str) -> int:
        """Get the current base fee rate (in basis points) for a token.

        CLOB API endpoint:
          GET /fee-rate?token_id=...  (also documented as /fee-rate/{token_id})

        Returns:
          base_fee in bps (int). 0 means fee-free.

        Raises:
          requests.HTTPError on non-2xx.
        """
        data = self._request_json("GET", f"{self.CLOB_API}/fee-rate", params={"token_id": token_id}) or {}
        return int(data.get("base_fee") or 0)

    # ==================== ORDER BOOK (CLOB API) ====================

    def get_orderbook(self, token_id: str) -> Dict:
        """
        Get order book for a token.
        
        Note: This endpoint may not be available for all markets.
        Returns empty book if 404 or error.
        """
        try:
            resp = self.session.get(f"{self.CLOB_API}/orderbook", params={"token_id": token_id}, timeout=self.timeout)
            if resp.status_code == 404:
                return {"bids": [], "asks": [], "error": "Orderbook not available"}
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"bids": [], "asks": [], "error": str(e)}
    
    def get_orderbooks(self, token_ids: List[str]) -> Dict[str, Dict]:
        """Get order books for multiple tokens."""
        return self._request_json(
            "GET",
            f"{self.CLOB_API}/orderbooks",
            params={"token_ids": ",".join(token_ids)},
        )
    
    def get_midpoint(self, token_id: str) -> Optional[float]:
        """Get midpoint price."""
        resp = self.session.get(f"{self.CLOB_API}/midpoint", params={"token_id": token_id}, timeout=self.timeout)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json().get("midpoint")
    
    def get_spread(self, token_id: str) -> Optional[Dict]:
        """Get bid-ask spread."""
        resp = self.session.get(f"{self.CLOB_API}/spread", params={"token_id": token_id}, timeout=self.timeout)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    
    # ==================== TRADES (Data API) ====================
    
    def get_trades(
        self,
        limit: int = 100,
        order: str = "desc",
        asset: Optional[str] = None,
        account: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict]:
        """
        Get trade history.
        
        Args:
            limit: Number of trades
            order: asc or desc
            asset: Filter by token asset
            account: Filter by account address
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        """
        params = {"limit": limit, "order": order}
        if asset:
            params["asset"] = asset
        if account:
            params["account"] = account
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        
        return self._request_json("GET", f"{self.DATA_API}/trades", params=params)
    
    # ==================== POSITIONS (Data API) ====================
    
    def get_positions(self, account: str) -> List[Dict]:
        """Get positions for an account."""
        return self._request_json("GET", f"{self.DATA_API}/positions", params={"account": account})
    
    def get_position_history(self, account: str, limit: int = 100) -> List[Dict]:
        """Get position history for an account."""
        return self._request_json(
            "GET",
            f"{self.DATA_API}/position-history",
            params={"account": account, "limit": limit},
        )
    
    # ==================== MARKETS INFO (Data API) ====================
    
    def get_market_info(self, condition_id: str) -> Dict:
        """Get market info (volume, liquidity, etc.)."""
        return self._request_json("GET", f"{self.DATA_API}/info", params={"conditionId": condition_id})
    
    def get_markets_info(self, condition_ids: List[str]) -> Dict[str, Dict]:
        """Get info for multiple markets."""
        return self._request_json(
            "GET",
            f"{self.DATA_API}/markets-info",
            params={"conditionIds": ",".join(condition_ids)},
        )
    
    def get_volume_history(self, condition_id: str) -> Dict:
        """Get volume history for a market."""
        return self._request_json("GET", f"{self.DATA_API}/volume-history", params={"conditionId": condition_id})
    
    # ==================== SUBGRAPH (GraphQL: fills + order events) ====================

    def _gql_post(self, url: str, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """POST a GraphQL query and return `data`.

        This is intentionally small: subgraphs are best-effort read-only data
        sources and can occasionally fail.
        """
        resp = self.session.post(url, json={"query": query, "variables": variables}, timeout=self.timeout)
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("errors"):
            raise RuntimeError(f"GraphQL errors: {payload['errors']}")
        return payload.get("data") or {}

    def get_fills_subgraph(
        self,
        token_id: str,
        start_ts: int,
        end_ts: int,
        endpoint_url: Optional[str] = None,
        page_size: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Fetch fills involving `token_id` from the orderbook subgraph.

        Returns OrderFilledEvent rows (sorted asc by timestamp).
        """
        url = endpoint_url or os.environ.get("POLYMARKET_SUBGRAPH_ORDERBOOK") or self.SUBGRAPH_ORDERBOOK

        q = """
        query($token: String!, $start: BigInt!, $end: BigInt!, $first: Int!, $skip: Int!) {
          orderFilledEvents(
            first: $first,
            skip: $skip,
            orderBy: timestamp,
            orderDirection: asc,
            where: {
              or: [
                { timestamp_gte: $start, timestamp_lt: $end, makerAssetId: $token }
                { timestamp_gte: $start, timestamp_lt: $end, takerAssetId: $token }
              ]
            }
          ) {
            id
            timestamp
            makerAssetId
            takerAssetId
            makerAmountFilled
            takerAmountFilled
            transactionHash
            orderHash
            maker
            taker
            fee
          }
        }
        """

        out: List[Dict[str, Any]] = []
        skip = 0
        while True:
            data = self._gql_post(
                url,
                q,
                {
                    "token": token_id,
                    "start": str(start_ts),
                    "end": str(end_ts),
                    "first": page_size,
                    "skip": skip,
                },
            )
            batch = data.get("orderFilledEvents") or []
            if not batch:
                break
            out.extend(batch)
            skip += len(batch)
            if len(batch) < page_size:
                break

        return out

    def get_orders_matched_subgraph(
        self,
        token_id: str,
        start_ts: int,
        end_ts: int,
        endpoint_url: Optional[str] = None,
        page_size: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Fetch OrdersMatchedEvent rows from the orderbook subgraph.

        This subgraph exposes `OrdersMatchedEvent` (not placed/canceled events).
        Useful as an additional event stream if you want match-level details.
        """
        url = endpoint_url or os.environ.get("POLYMARKET_SUBGRAPH_ORDERBOOK") or self.SUBGRAPH_ORDERBOOK

        q = """
        query($token: String!, $start: BigInt!, $end: BigInt!, $first: Int!, $skip: Int!) {
          ordersMatchedEvents(
            first: $first,
            skip: $skip,
            orderBy: timestamp,
            orderDirection: asc,
            where: { timestamp_gte: $start, timestamp_lt: $end, tokenId: $token }
          ) {
            id
            timestamp
            tokenId
            maker
            taker
            makerAmount
            takerAmount
            transactionHash
          }
        }
        """

        out: List[Dict[str, Any]] = []
        skip = 0
        while True:
            data = self._gql_post(
                url,
                q,
                {
                    "token": token_id,
                    "start": str(start_ts),
                    "end": str(end_ts),
                    "first": page_size,
                    "skip": skip,
                },
            )
            batch = data.get("ordersMatchedEvents") or []
            if not batch:
                break
            out.extend(batch)
            skip += len(batch)
            if len(batch) < page_size:
                break

        return out

    @staticmethod
    def _floor_to_minute(ts: int) -> int:
        return ts - (ts % 60)

    def ohlcv_1m_from_fills(self, fills: List[Dict[str, Any]], day_start_ts: int, token_id: str) -> List[Dict[str, Any]]:
        """Derive 1-minute OHLCV bars from subgraph fills.

        - Price is computed from USDC/shares.
        - Volume is in shares.

        Output rows:
          {"t": <minute_start_unix>, "o":..., "h":..., "l":..., "c":..., "v":..., "trades": n}

        Notes:
        - This expects fills sorted ascending by timestamp (as returned by get_fills_subgraph).
        - Minutes with no trades are included with null OHLC and v=0.
        """
        buckets: Dict[int, Dict[str, Any]] = {}

        for ev in fills:
            ts = int(ev["timestamp"])
            if ts < day_start_ts or ts >= day_start_ts + 24 * 3600:
                continue

            maker_asset = ev["makerAssetId"]
            taker_asset = ev["takerAssetId"]
            maker_amt = int(ev["makerAmountFilled"])
            taker_amt = int(ev["takerAmountFilled"])

            if maker_asset == token_id and taker_asset == self.USDC_ASSET_ID:
                share_amt = maker_amt
                usdc_amt = taker_amt
            elif maker_asset == self.USDC_ASSET_ID and taker_asset == token_id:
                share_amt = taker_amt
                usdc_amt = maker_amt
            else:
                continue

            shares = share_amt / (10 ** self.SHARE_DECIMALS)
            usdc = usdc_amt / (10 ** self.USDC_DECIMALS)
            if not shares:
                continue
            price = usdc / shares

            t0 = self._floor_to_minute(ts)
            b = buckets.get(t0)
            if b is None:
                b = {"o": price, "h": price, "l": price, "c": price, "v": 0.0, "trades": 0}
                buckets[t0] = b
            else:
                b["h"] = max(b["h"], price)
                b["l"] = min(b["l"], price)
                b["c"] = price

            b["v"] += float(shares)
            b["trades"] += 1

        bars: List[Dict[str, Any]] = []
        for t in range(day_start_ts, day_start_ts + 24 * 3600, 60):
            b = buckets.get(t)
            if not b:
                bars.append({"t": t, "o": None, "h": None, "l": None, "c": None, "v": 0.0, "trades": 0})
            else:
                bars.append({"t": t, **b})
        return bars

    # ==================== UTILITY ====================

    def get_token_info(self, token_id: str) -> Dict:
        """Get token metadata."""
        return self._request_json("GET", f"{self.GAMMA_API}/tokens/{token_id}")
    
    def get_candidate_markets(
        self,
        category: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get candidate markets (for trading)."""
        params = {"limit": limit}
        if category:
            params["category"] = category
        return self._request_json("GET", f"{self.GAMMA_API}/candidate-markets", params=params)


    # ==================== COMBINED METHODS (Events + Markets API) ====================
    
    def search_markets_combined(
        self,
        query: str,
        include_active: bool = True,
        include_resolved: bool = True,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Search markets using both Events and Markets APIs.
        
        Args:
            query: Search query
            include_active: Include active markets
            include_resolved: Include resolved markets
            limit: Max results per API
        
        Returns:
            Dict with 'events' and 'markets' keys containing results
        """
        results = {
            "events": [],
            "markets": [],
            "summary": {
                "query": query,
                "active_count": 0,
                "resolved_count": 0
            }
        }
        
        # Search via Events API (good for finding related market groups)
        if include_active or include_resolved:
            # Get events matching query
            try:
                # Events API supports filtering by various params
                events_resp = self.session.get(
                    f"{self.GAMMA_API}/events",
                    params={"limit": limit, "search": query}
                )
                if events_resp.status_code == 200:
                    events = events_resp.json()
                    results["events"] = events
                    
                    # Count active vs resolved from events
                    for event in events:
                        if event.get("closed"):
                            results["summary"]["resolved_count"] += 1
                        else:
                            results["summary"]["active_count"] += 1
            except Exception as e:
                results["events_error"] = str(e)
        
        # Search via Markets API (good for individual market details)
        try:
            markets = self.search_markets(query, limit=limit)
            results["markets"] = markets
            
            # Further filter by active/resolved status
            if not include_active or not include_resolved:
                filtered = []
                for m in markets:
                    is_resolved = m.get("resolvedDate") or m.get("closed")
                    if include_resolved and is_resolved:
                        filtered.append(m)
                    elif include_active and not is_resolved:
                        filtered.append(m)
                results["markets"] = filtered
        except Exception as e:
            results["markets_error"] = str(e)
        
        return results
    
    def get_all_active_markets(
        self,
        category: Optional[str] = None,
        limit: int = 100,
        cursor: Optional[int] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get all currently active markets using both APIs.
        
        Args:
            category: Optional category filter
            limit: Max results
            cursor: Pagination cursor
            search: Optional search query
        
        Returns:
            Dict with 'events' (active event groups) and 'markets' (individual active markets)
        """
        results = {
            "events": [],
            "markets": [],
            "pagination": {"cursor": None, "has_more": False}
        }
        
        # Get active events (groups with at least one active market)
        try:
            events_params = {"limit": limit, "closed": "false"}
            if cursor:
                events_params["cursor"] = cursor
            if category:
                events_params["category"] = category
            if search:
                events_params["search"] = search
                
            events_resp = self.session.get(
                f"{self.GAMMA_API}/events",
                params=events_params
            )
            if events_resp.status_code == 200:
                events_data = events_resp.json()
                # Handle pagination if present
                if isinstance(events_data, dict):
                    results["events"] = events_data.get("events", events_data.get("data", []))
                    results["pagination"]["cursor"] = events_data.get("cursor")
                    results["pagination"]["has_more"] = events_data.get("hasMore", False)
                else:
                    results["events"] = events_data
        except Exception as e:
            results["events_error"] = str(e)
        
        # Get active markets (individual markets)
        try:
            markets_params = {"limit": limit, "closed": "false"}
            if cursor:
                markets_params["cursor"] = cursor
            if category:
                markets_params["category"] = category
            if search:
                markets_params["search"] = search
                
            markets_resp = self.session.get(
                f"{self.GAMMA_API}/markets",
                params=markets_params
            )
            if markets_resp.status_code == 200:
                markets_data = markets_resp.json()
                # Handle pagination if present
                if isinstance(markets_data, dict):
                    results["markets"] = markets_data.get("markets", markets_data.get("data", []))
                    results["pagination"]["cursor"] = markets_data.get("cursor", results["pagination"]["cursor"])
                    results["pagination"]["has_more"] = markets_data.get("hasMore", results["pagination"]["has_more"])
                else:
                    results["markets"] = markets_data
        except Exception as e:
            results["markets_error"] = str(e)
        
        # Add summary stats
        results["summary"] = {
            "total_events": len(results["events"]),
            "total_markets": len(results["markets"]),
            "category": category,
            "search": search
        }
        
        return results
    
    def get_active_markets_flat(
        self,
        category: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get a flat list of all active markets (convenience method).
        
        Args:
            category: Optional category filter
            limit: Max results
        
        Returns:
            List of active market dicts
        """
        # Use get_markets with closed=false
        markets = self.get_markets(
            limit=limit,
            closed=False,
            category=category
        )
        return markets
    
    def get_resolved_markets_flat(
        self,
        category: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get a flat list of resolved markets.
        
        Args:
            category: Optional category filter
            limit: Max results
        
        Returns:
            List of resolved market dicts
        """
        markets = self.get_markets(
            limit=limit,
            closed=True,
            category=category
        )
        return markets


# Convenience function for quick access
def get_client(api_key: Optional[str] = None) -> PolymarketClient:
    """Create a Polymarket client."""
    return PolymarketClient(api_key)


if __name__ == "__main__":
    # Example usage
    client = PolymarketClient()
    
    # Get some markets
    print("Fetching markets...")
    markets = client.get_markets(limit=5)
    for m in markets:
        print(f"  - {m.get('question', 'N/A')[:50]}...")
    
    # Get price history for first market if available
    if markets and markets[0].get('clobTokenIds'):
        token_ids = markets[0]['clobTokenIds']
        if isinstance(token_ids, str):
            import json
            token_ids = json.loads(token_ids)
        if token_ids:
            print(f"\nPrice history for first token: {token_ids[0]}")
            try:
                history = client.get_price_history(token_ids[0])
                print(f"  Data points: {len(history.get('history', []))}")
            except Exception as e:
                print(f"  Error: {e}")
