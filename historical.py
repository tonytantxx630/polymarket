#!/usr/bin/env python3
"""
Historical Data Fetcher for Polymarket

Fetches historical market data going back to 2023.
"""

import json
import csv
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from polymarket import PolymarketClient


class HistoricalDataFetcher:
    """Fetch historical data from Polymarket."""
    
    def __init__(self, output_dir: str = "./data"):
        self.client = PolymarketClient()
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def get_all_markets_with_history(self) -> List[Dict]:
        """
        Get all markets that have price history data.
        The CLOB API only returns history for markets that were actively traded.
        """
        # Get closed markets (typically have complete history)
        markets = self.client.get_markets(closed=True, limit=1000)
        
        markets_with_history = []
        for m in markets:
            token_ids = m.get('clobTokenIds')
            if isinstance(token_ids, str):
                token_ids = json.loads(token_ids)
            
            if token_ids:
                # Try to get price history for first token
                try:
                    history = self.client.get_price_history(token_ids[0], fidelity=1440)
                    if history.get('history'):
                        m['_token_id'] = token_ids[0]
                        m['_history_count'] = len(history['history'])
                        m['_history_start'] = history['history'][0]['t']
                        m['_history_end'] = history['history'][-1]['t']
                        markets_with_history.append(m)
                except Exception:
                    pass
        
        return markets_with_history
    
    def fetch_price_history(
        self,
        token_id: str,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None
    ) -> List[Dict]:
        """
        Fetch price history for a token.
        
        Args:
            token_id: CLOB token ID
            start_ts: Start timestamp (Unix). If None, fetches all available.
            end_ts: End timestamp (Unix)
        
        Returns:
            List of {timestamp, price} dicts
        """
        params = {"interval": "max", "fidelity": 1440}
        if start_ts:
            params["startTs"] = start_ts
        if end_ts:
            params["endTs"] = end_ts
        
        resp = self.client.session.get(
            f"{self.client.CLOB_API}/prices-history",
            params={"market": token_id, **params}
        )
        resp.raise_for_status()
        data = resp.json()
        
        return data.get("history", [])
    
    def fetch_market_prices(
        self,
        condition_id: str,
        start_date: str = "2023-01-01",
        end_date: Optional[str] = None
    ) -> Dict:
        """
        Fetch all prices for a market from start_date to end_date.
        
        Args:
            condition_id: Market condition ID
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD), defaults to today
        
        Returns:
            Dict with token prices and history
        """
        # Get market info
        market = self.client.get_market(condition_id)
        if not market:
            return {"error": "Market not found"}
        
        token_ids = market.get('clobTokenIds')
        if isinstance(token_ids, str):
            token_ids = json.loads(token_ids)
        
        if not token_ids:
            return {"error": "No token IDs found"}
        
        # Parse dates
        start_ts = int(datetime.fromisoformat(start_date.replace("Z", "+00:00")).timestamp())
        if end_date:
            end_ts = int(datetime.fromisoformat(end_date.replace("Z", "+00:00")).timestamp())
        else:
            end_ts = None
        
        result = {
            "market": market.get("question"),
            "condition_id": condition_id,
            "start_date": start_date,
            "end_date": end_date or datetime.now().isoformat(),
            "tokens": {}
        }
        
        for token_id in token_ids:
            try:
                history = self.fetch_price_history(token_id, start_ts, end_ts)
                result["tokens"][token_id] = {
                    "history": history,
                    "data_points": len(history)
                }
            except Exception as e:
                result["tokens"][token_id] = {"error": str(e)}
        
        return result
    
    def export_to_csv(self, history: List[Dict], filename: str):
        """Export price history to CSV."""
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['timestamp', 'date', 'price'])
            writer.writeheader()
            
            for item in history:
                ts = item.get('t')
                writer.writerow({
                    'timestamp': ts,
                    'date': datetime.utcfromtimestamp(ts).isoformat() if ts else '',
                    'price': item.get('p')
                })
        
        print(f"Exported to {filepath}")
        return filepath
    
    def get_historical_markets_summary(self) -> Dict:
        """Get summary of markets with historical data."""
        markets = self.get_all_markets_with_history()
        
        # Group by year/month
        by_date = {}
        for m in markets:
            start = datetime.utcfromtimestamp(m['_history_start'])
            key = start.strftime("%Y-%m")
            if key not in by_date:
                by_date[key] = []
            by_date[key].append({
                "question": m.get("question", "")[:60],
                "condition_id": m.get("conditionId"),
                "token_id": m.get("_token_id"),
                "data_points": m.get("_history_count"),
                "start": start.isoformat(),
                "end": datetime.utcfromtimestamp(m['_history_end']).isoformat()
            })
        
        return {
            "total_markets": len(markets),
            "by_month": by_date
        }


def main():
    fetcher = HistoricalDataFetcher()
    
    print("Fetching markets with historical data...")
    summary = fetcher.get_historical_markets_summary()
    
    print(f"\nTotal markets with price history: {summary['total_markets']}")
    print("\nMarkets by month:")
    for month, markets in sorted(summary['by_date'].items()):
        print(f"\n{month}: {len(markets)} markets")
        for m in markets[:3]:
            print(f"  - {m['question']}")
            print(f"    {m['start'][:10]} to {m['end'][:10]} ({m['data_points']} points)")


if __name__ == "__main__":
    main()
