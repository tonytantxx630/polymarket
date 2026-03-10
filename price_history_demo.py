#!/usr/bin/env python3
"""Polymarket CLOB API – Price History demo.

Tony asked for:
- use `from polymarket.polymarket import PolymarketClient`
- write functions to retrieve historical prices for a prediction market
- test it and show the test result

This script:
1) finds an active market via `search_markets()`
2) extracts its CLOB token IDs
3) calls `GET https://clob.polymarket.com/prices-history`
4) prints a small sample of the returned history

Run:
  python3 polymarket/price_history_demo.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from polymarket.polymarket import PolymarketClient


@dataclass
class MarketPick:
    question: str
    condition_id: str
    token_ids: List[str]
    volume: float


def pick_market_via_search(
    query: str,
    *,
    min_volume: float = 100_000,
    active_only: bool = True,
    limit: int = 20,
) -> MarketPick:
    """Pick a single market using the Gamma API search workflow.

    Returns the highest-volume match (after filters) plus its token IDs.
    """

    client = PolymarketClient()
    results = client.search_markets(
        query,
        active_only=active_only,
        min_volume=min_volume,
        limit=limit,
    )
    markets = results.get("markets", [])
    if not markets:
        raise RuntimeError(f"No markets found for query={query!r} (min_volume={min_volume}).")

    # Choose the highest-volume market
    def vol(m: Dict[str, Any]) -> float:
        try:
            return float(m.get("volume") or 0)
        except Exception:
            return 0.0

    market = sorted(markets, key=vol, reverse=True)[0]

    token_ids = market.get("clobTokenIds")
    if isinstance(token_ids, str):
        token_ids = json.loads(token_ids)
    if not token_ids:
        raise RuntimeError("Selected market has no clobTokenIds.")

    return MarketPick(
        question=market.get("question") or "(unknown)",
        condition_id=market.get("conditionId") or "(unknown)",
        token_ids=list(token_ids),
        volume=vol(market),
    )


def get_price_history(
    token_id: str,
    *,
    interval: str = "1d",
    fidelity: int = 60,
    start_ts: Optional[int] = None,
    end_ts: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Retrieve historical price points for a CLOB token.

    Under the hood this calls:
      GET https://clob.polymarket.com/prices-history
        ?market=<token_id>&interval=<interval>&fidelity=<fidelity>

    Returns list entries like: {"t": <unix_seconds>, "p": <price_float>}
    """

    client = PolymarketClient()
    resp = client.get_price_history(
        token_id,
        interval=interval,
        fidelity=fidelity,
        start_ts=start_ts,
        end_ts=end_ts,
    )
    return resp.get("history", [])


def _fmt_point(pt: Dict[str, Any]) -> str:
    t = int(pt["t"])
    p = pt["p"]
    dt = datetime.fromtimestamp(t, tz=timezone.utc).isoformat()
    return f"{dt}  price={p}"


def demo() -> Tuple[MarketPick, List[Dict[str, Any]]]:
    # Pick a liquid market so history is likely non-empty.
    pick = pick_market_via_search("Bitcoin", min_volume=100_000, active_only=True)

    # Usually token_ids[0] corresponds to one outcome (YES/NO markets have 2 tokens)
    token_id = pick.token_ids[0]

    history = get_price_history(token_id, interval="1d", fidelity=60)
    return pick, history


if __name__ == "__main__":
    pick, history = demo()

    print("Picked market:")
    print(f"  question     : {pick.question}")
    print(f"  conditionId  : {pick.condition_id}")
    print(f"  volume (USD) : {pick.volume}")
    print(f"  token_ids    : {pick.token_ids[:2]}{' ...' if len(pick.token_ids) > 2 else ''}")

    print("\nPrice history result:")
    print(f"  points: {len(history)}")
    if history:
        print("  first:", _fmt_point(history[0]))
        print("  last :", _fmt_point(history[-1]))
        print("\n  sample (up to 5 points):")
        for pt in history[:5]:
            print("   -", _fmt_point(pt))
    else:
        print("  (empty history)")
