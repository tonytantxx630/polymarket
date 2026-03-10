#!/usr/bin/env python3
"""
CLI for Polymarket data fetching.
"""

import argparse
import json
import sys
from polymarket import PolymarketClient
from historical import HistoricalDataFetcher


def cmd_markets(args):
    client = PolymarketClient()
    markets = client.get_markets(limit=args.limit, closed=args.closed)
    
    for m in markets:
        print(f"\n{ m.get('question', 'N/A')}")
        print(f"  ID: {m.get('conditionId')}")
        print(f"  Slug: {m.get('slug')}")
        print(f"  Volume: ${m.get('volume', 0):,.2f}")
        print(f"  End: {m.get('endDateIso')}")
        
        if args.verbose:
            token_ids = m.get('clobTokenIds')
            if isinstance(token_ids, str):
                token_ids = json.loads(token_ids)
            print(f"  Tokens: {token_ids}")


def cmd_price_history(args):
    client = PolymarketClient()
    history = client.get_price_history(
        args.token_id,
        interval=args.interval,
        fidelity=args.fidelity,
        start_ts=args.start_ts,
        end_ts=args.end_ts
    )
    
    data = history.get('history', [])
    print(f"Got {len(data)} data points")
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Saved to {args.output}")
    else:
        for point in data[:10]:
            print(f"  {point}")
        if len(data) > 10:
            print(f"  ... and {len(data) - 10} more")


def cmd_orderbook(args):
    client = PolymarketClient()
    ob = client.get_orderbook(args.token_id)
    
    print(f"Order Book for {args.token_id}")
    print(f"\nBids (BUY):")
    for order in ob.get('bids', [])[:5]:
        print(f"  {order.get('price')} x {order.get('size')}")
    
    print(f"\nAsks (SELL):")
    for order in ob.get('asks', [])[:5]:
        print(f"  {order.get('price')} x {order.get('size')}")


def cmd_trades(args):
    client = PolymarketClient()
    trades = client.get_trades(
        limit=args.limit,
        asset=args.asset,
        account=args.account
    )
    
    print(f"Got {len(trades)} trades")
    for t in trades[:10]:
        print(f"  {t.get('timestamp')}: {t.get('side')} {t.get('size')} @ {t.get('price')}")
        print(f"    {t.get('title', 'N/A')[:50]}")


def cmd_search(args):
    client = PolymarketClient()
    results = client.search_markets(args.query, limit=args.limit)
    
    print(f"Found {len(results)} markets")
    for m in results:
        print(f"\n{m.get('question')}")
        print(f"  {m.get('slug')}")
        print(f"  Volume: ${m.get('volume', 0):,.2f}")


def cmd_events(args):
    client = PolymarketClient()
    events = client.get_events(limit=args.limit, closed=args.closed)
    
    for e in events:
        print(f"\n{e.get('title')}")
        print(f"  ID: {e.get('id')}")
        print(f"  Slug: {e.get('slug')}")
        print(f"  Volume: ${e.get('volume', 0):,.2f}")


def main():
    parser = argparse.ArgumentParser(description="Polymarket CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command")
    
    # Markets
    p_markets = subparsers.add_parser("markets", help="List markets")
    p_markets.add_argument("--limit", type=int, default=10)
    p_markets.add_argument("--closed", action="store_true")
    p_markets.add_argument("-v", "--verbose", action="store_true")
    p_markets.set_defaults(func=cmd_markets)
    
    # Price history
    p_price = subparsers.add_parser("price-history", help="Get price history")
    p_price.add_argument("token_id", help="Token ID")
    p_price.add_argument("--interval", default="max")
    p_price.add_argument("--fidelity", type=int, default=1440)
    p_price.add_argument("--start-ts", type=int)
    p_price.add_argument("--end-ts", type=int)
    p_price.add_argument("--output", "-o", help="Output JSON file")
    p_price.set_defaults(func=cmd_price_history)
    
    # Orderbook
    p_ob = subparsers.add_parser("orderbook", help="Get order book")
    p_ob.add_argument("token_id", help="Token ID")
    p_ob.set_defaults(func=cmd_orderbook)
    
    # Trades
    p_trades = subparsers.add_parser("trades", help="Get trades")
    p_trades.add_argument("--limit", type=int, default=10)
    p_trades.add_argument("--asset", help="Filter by asset")
    p_trades.add_argument("--account", help="Filter by account")
    p_trades.set_defaults(func=cmd_trades)
    
    # Search
    p_search = subparsers.add_parser("search", help="Search markets")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--limit", type=int, default=10)
    p_search.set_defaults(func=cmd_search)
    
    # Events
    p_events = subparsers.add_parser("events", help="List events")
    p_events.add_argument("--limit", type=int, default=10)
    p_events.add_argument("--closed", action="store_true")
    p_events.set_defaults(func=cmd_events)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    args.func(args)


if __name__ == "__main__":
    main()
