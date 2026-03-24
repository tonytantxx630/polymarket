"""
Polymarket Arbitrage Screener (Read-Only)

Screens for arbitrage opportunities in political prediction markets.
Identifies mispricings between complementary markets and computes edge signals.

Usage:
    python -m polymarket.arbitrage_screener [--category politics] [--min-volume 10000]
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from polymarket import PolymarketClient


# Theme keywords for clustering
THEME_KEYWORDS = {
    "iran": ["iran", "persian", "tehran"],
    "russia_ukraine": ["russia", "ukraine", "kiev", "moscow", "putin"],
    "us_election_2026": ["2026", "election", "congress", "senate", "house", "gop", "democrat"],
    "china_taiwan": ["china", "taiwan", "beijing", "xi", "south china sea"],
    "nato_europe": ["nato", "europe", "eu", "european union", "baltic"],
    "middle_east": ["israel", "gaza", "hezbollah", "syria", "saudi", "iraq"],
    "climate": ["climate", "warming", "carbon", "emissions"],
    "economy": ["recession", "inflation", "fed", "interest rate", "gdp"],
}


@dataclass
class Market:
    """Represents a Polymarket market with pricing data."""
    condition_id: str
    question: str
    slug: str
    volume: float
    liquidity: float
    closed: bool
    outcome: Optional[str]
    end_date: Optional[str]
    tokens: Dict[str, str] = field(default_factory=dict)  # {"yes": token_id, "no": token_id}
    orderbook: Dict[str, Dict] = field(default_factory=dict)  # {"yes": {...}, "no": {...}}
    fees: Dict[str, int] = field(default_factory=dict)  # {"yes": bps, "no": bps}
    
    @property
    def theme(self) -> str:
        """Infer theme from question."""
        q_lower = self.question.lower()
        for theme, keywords in THEME_KEYWORDS.items():
            if any(kw in q_lower for kw in keywords):
                return theme
        return "other"


@dataclass
class ArbitrageSignal:
    """Represents a detected arbitrage opportunity."""
    market_a: Market
    market_b: Market
    signal_type: str  # "complementary", "conditional", "basis"
    price_a: float
    price_b: float
    combined_prob: float
    expected_prob: float
    edge: float
    edge_pct: float
    fees_included: bool = False
    
    def __str__(self) -> str:
        return (
            f"  • {self.signal_type.upper()}: {self.market_a.question[:50]}... "
            f"vs {self.market_b.question[:50]}...\n"
            f"    Prices: {self.price_a:.3f} / {self.price_b:.3f} | "
            f"Combined: {self.combined_prob:.3f} | Edge: {self.edge_pct:.1f}%"
        )


class ArbitrageScreener:
    """Screen Polymarket for arbitrage opportunities."""
    
    def __init__(
        self,
        client: Optional[PolymarketClient] = None,
        min_volume: float = 10000,
        output_dir: Optional[Path] = None,
    ):
        self.client = client or PolymarketClient()
        self.min_volume = min_volume
        self.output_dir = output_dir or Path(__file__).parent / "outputs"
        self.output_dir.mkdir(exist_ok=True)
        
        # Cache
        self._markets: List[Market] = []
        self._clusters: Dict[str, List[Market]] = {}
    
    def fetch_markets(
        self,
        category: Optional[str] = None,
        limit: int = 200,
        active_only: bool = True,
    ) -> List[Market]:
        """Fetch markets from Polymarket."""
        print(f"Fetching markets (category={category}, limit={limit})...")
        
        # Use get_markets for direct market access
        markets_data = self.client.get_markets(
            limit=limit,
            closed=not active_only,
            category=category,
        )
        
        markets = []
        for m in markets_data:
            try:
                volume = float(m.get("volume") or 0)
                if volume < self.min_volume:
                    continue
                
                # Extract token IDs
                token_ids = m.get("clobTokenIds")
                if isinstance(token_ids, str):
                    token_ids = json.loads(token_ids)
                
                tokens = {}
                if token_ids:
                    # Usually [yes_token_id, no_token_id] or [token_id]
                    tokens["yes"] = token_ids[0] if len(token_ids) > 0 else None
                    tokens["no"] = token_ids[1] if len(token_ids) > 1 else token_ids[0]
                
                market = Market(
                    condition_id=m.get("conditionId", ""),
                    question=m.get("question", ""),
                    slug=m.get("slug", ""),
                    volume=volume,
                    liquidity=float(m.get("liquidity") or 0),
                    closed=m.get("closed", False),
                    outcome=m.get("outcome"),
                    end_date=m.get("endDate"),
                    tokens=tokens,
                )
                markets.append(market)
            except Exception as e:
                print(f"  Warning: Failed to parse market: {e}")
                continue
        
        print(f"  Fetched {len(markets)} markets above ${self.min_volume:,} volume")
        self._markets = markets
        return markets
    
    def cluster_markets(self, markets: Optional[List[Market]] = None) -> Dict[str, List[Market]]:
        """Cluster markets by theme."""
        markets = markets or self._markets
        
        clusters: Dict[str, List[Market]] = {}
        for m in markets:
            theme = m.theme
            if theme not in clusters:
                clusters[theme] = []
            clusters[theme].append(m)
        
        # Sort clusters by total volume
        sorted_clusters = {}
        for theme in sorted(clusters.keys(), key=lambda t: sum(m.volume for m in clusters[t]), reverse=True):
            sorted_clusters[theme] = clusters[theme]
        
        self._clusters = sorted_clusters
        
        print("\nClusters:")
        for theme, ms in sorted_clusters.items():
            total_vol = sum(m.volume for m in ms)
            print(f"  • {theme}: {len(ms)} markets, ${total_vol:,.0f} volume")
        
        return sorted_clusters
    
    def fetch_orderbooks(self, markets: Optional[List[Market]] = None) -> List[Market]:
        """Fetch live order books for markets, fall back to fill-derived prices."""
        import time as time_module
        markets = markets or self._markets
        
        print(f"\nFetching orderbooks/prices for {len(markets)} markets...")
        
        # Get recent timestamp for fills
        end_ts = int(time_module.time())
        start_ts = end_ts - 24 * 3600  # Last 24 hours
        
        for i, m in enumerate(markets):
            if not m.tokens.get("yes"):
                continue
            
            yes_token = m.tokens["yes"]
            no_token = m.tokens.get("no")
            
            # Try orderbook first
            try:
                ob_yes = self.client.get_orderbook(yes_token)
                m.orderbook["yes"] = ob_yes
            except Exception as e:
                m.orderbook["yes"] = {"bids": [], "asks": [], "error": str(e)}
            
            # Try fee rate
            try:
                m.fees["yes"] = self.client.get_fee_rate_bps(yes_token)
            except:
                m.fees["yes"] = 0
            
            # Try NO token orderbook
            if no_token:
                try:
                    ob_no = self.client.get_orderbook(no_token)
                    m.orderbook["no"] = ob_no
                except Exception as e:
                    m.orderbook["no"] = {"bids": [], "asks": [], "error": str(e)}
                
                try:
                    m.fees["no"] = self.client.get_fee_rate_bps(no_token)
                except:
                    m.fees["no"] = 0
            
            # If orderbook empty, try fill-derived price
            ob = m.orderbook.get("yes", {})
            if not ob.get("bids") and not ob.get("asks"):
                try:
                    fills = self.client.get_fills_subgraph(yes_token, start_ts, end_ts)
                    if fills:
                        # Derive price from last fill
                        last_fill = fills[-1]
                        maker_amt = int(last_fill["makerAmountFilled"])
                        taker_amt = int(last_fill["takerAmountFilled"])
                        
                        if last_fill["makerAssetId"] == yes_token:
                            # Maker was selling YES
                            price = taker_amt / maker_amt if maker_amt > 0 else 0
                        else:
                            # Maker was buying YES (selling USDC)
                            price = maker_amt / taker_amt if taker_amt > 0 else 0
                        
                        # Store as synthetic orderbook
                        m.orderbook["yes"] = {
                            "bids": [{"price": str(price * 0.999), "size": "1000000"}],  # Slight discount for bid
                            "asks": [{"price": str(price * 1.001), "size": "1000000"}],   # Slight premium for ask
                            "fill_price": price,
                            "fill_source": "subgraph",
                        }
                except Exception as e:
                    pass
            
            # Rate limit protection
            if (i + 1) % 10 == 0:
                time_module.sleep(0.3)
        
        # Count successes
        with_prices = sum(
            1 for m in markets 
            if (m.orderbook.get("yes", {}).get("bids") or m.orderbook.get("yes", {}).get("fill_price"))
        )
        print(f"  Successfully got pricing for {with_prices}/{len(markets)} markets")
        return markets
    
    def _get_best_prices(self, market: Market) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Get best bid, ask, midpoint for YES using `/price` (preferred).

        We prefer `/price` because it matches the UI top-of-book more reliably.
        """
        tok = market.tokens.get("yes")
        if not tok:
            return None, None, None

        try:
            tob = self.client.get_top_of_book(tok)
            bid = float(tob.get("bid") or 0)
            ask = float(tob.get("ask") or 0)
            if bid <= 0 and ask <= 0:
                return None, None, None
            mid = (bid + ask) / 2
            return bid, ask, mid
        except Exception:
            return None, None, None
    
    def _adjust_for_fees(self, price: float, fee_bps: int, is_buy: bool) -> float:
        """Adjust price for fees."""
        # Buy: pay ask, fees reduce effective price
        # Sell: receive bid, fees reduce effective proceeds
        fee_multiplier = 1 - (fee_bps / 10000)
        return price * fee_multiplier
    
    def find_complementary_pairs(self) -> List[ArbitrageSignal]:
        """Find buy-side complementary opportunities using **asks only**.

        Since we're assuming no inventory to sell, we only consider:
          buy YES at YES_ask  and buy NO at NO_ask.

        In a frictionless binary market, YES + NO = 1.
        With only buys, a potential arb-like mispricing is when:
          YES_ask + NO_ask < 1 - buffer
        """
        signals: List[ArbitrageSignal] = []

        for m in self._markets:
            yes_tok = m.tokens.get("yes")
            no_tok = m.tokens.get("no")
            if not yes_tok or not no_tok:
                continue

            try:
                yes_tob = self.client.get_top_of_book(yes_tok)
                no_tob = self.client.get_top_of_book(no_tok)
                yes_ask = float(yes_tob.get("ask") or 0)
                no_ask = float(no_tob.get("ask") or 0)
            except Exception:
                continue

            if yes_ask <= 0 or no_ask <= 0:
                continue

            combined = yes_ask + no_ask
            expected = 1.0
            edge = expected - combined
            edge_pct = edge * 100

            # Buffer: 0.5% by default (tune later)
            if edge_pct > 0.5:
                market_b = Market(
                    condition_id=m.condition_id + "-no",
                    question=f"NO side of: {m.question}",
                    slug=m.slug + "-no",
                    volume=m.volume,
                    liquidity=m.liquidity,
                    closed=m.closed,
                    outcome=None,
                    end_date=m.end_date,
                    tokens={"yes": no_tok},
                )

                signals.append(
                    ArbitrageSignal(
                        market_a=m,
                        market_b=market_b,
                        signal_type="complementary_buy_asks",
                        price_a=yes_ask,
                        price_b=no_ask,
                        combined_prob=combined,
                        expected_prob=expected,
                        edge=edge,
                        edge_pct=edge_pct,
                        fees_included=False,
                    )
                )

        signals.sort(key=lambda s: s.edge_pct, reverse=True)
        return signals
    
    def find_theme_mispricings(self) -> List[ArbitrageSignal]:
        """Find mispricings within themed clusters."""
        signals = []
        
        for theme, markets in self._clusters.items():
            if len(markets) < 2:
                continue
            
            # Get all markets with orderbook data
            with_data = [m for m in markets if m.orderbook.get("yes", {}).get("bids")]
            if len(with_data) < 2:
                continue
            
            # Compare prices within theme
            prices = []
            for m in with_data:
                _, yes_ask, yes_mid = self._get_best_prices(m)
                if yes_ask:
                    prices.append((m, yes_ask))
            
            # Find outliers (significantly higher/lower than peers)
            if len(prices) < 2:
                continue
            
            avg_price = sum(p for _, p in prices) / len(prices)
            
            for m, price in prices:
                deviation = price - avg_price
                deviation_pct = (deviation / avg_price) * 100 if avg_price > 0 else 0
                
                # Flag if >10% deviation from theme average
                if abs(deviation_pct) > 10:
                    # Find a peer to compare against
                    peer = min(prices, key=lambda x: abs(x[1] - avg_price))
                    
                    signal = ArbitrageSignal(
                        market_a=m,
                        market_b=peer[0],
                        signal_type="theme_mispricing",
                        price_a=price,
                        price_b=peer[1],
                        combined_prob=price,
                        expected_prob=peer[1],
                        edge=deviation,
                        edge_pct=deviation_pct,
                    )
                    signals.append(signal)
        
        signals.sort(key=lambda s: abs(s.edge_pct), reverse=True)
        return signals
    
    def generate_report(self) -> str:
        """Generate arbitrage screening report."""
        lines = []
        lines.append("=" * 70)
        lines.append("POLYMARKET ARBITRAGE SCREENER REPORT")
        lines.append(f"Generated: {datetime.utcnow().isoformat()}")
        lines.append("=" * 70)
        
        # Summary
        lines.append(f"\nMarkets screened: {len(self._markets)}")
        lines.append(f"Clusters identified: {len(self._clusters)}")
        
        # Complementary pairs (YES/NO)
        comp_signals = self.find_complementary_pairs()
        lines.append(f"\n{'='*70}")
        lines.append(f"COMPLEMENTARY PAIRS (YES + NO should = $1.00)")
        lines.append(f"{'='*70}")
        
        if comp_signals:
            for sig in comp_signals[:10]:  # Top 10
                lines.append(str(sig))
        else:
            lines.append("  No significant complementary mispricings detected.")
        
        # Theme mispricings
        theme_signals = self.find_theme_mispricings()
        lines.append(f"\n{'='*70}")
        lines.append(f"THEME MISPRICINGS (>10% deviation from cluster average)")
        lines.append(f"{'='*70}")
        
        if theme_signals:
            for sig in theme_signals[:10]:  # Top 10
                lines.append(str(sig))
        else:
            lines.append("  No significant theme mispricings detected.")
        
        # Disclaimer
        lines.append(f"\n{'='*70}")
        lines.append("DISCLAIMER")
        lines.append("This is informational only, not financial advice.")
        lines.append("Edge calculations are estimates; actual execution may differ.")
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def save_output(self, report: str, filename: Optional[str] = None) -> Path:
        """Save report to file."""
        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"arbitrage_report_{timestamp}.txt"
        
        filepath = self.output_dir / filename
        filepath.write_text(report)
        return filepath
    
    def run(
        self,
        category: Optional[str] = None,
        min_volume: float = 10000,
    ) -> str:
        """Run full screening workflow."""
        self.min_volume = min_volume
        
        # Step 1: Fetch markets
        self.fetch_markets(category=category)
        
        # Step 2: Cluster
        self.cluster_markets()
        
        # Step 3: Fetch orderbooks
        self.fetch_orderbooks()
        
        # Step 4: Generate report
        report = self.generate_report()
        
        # Step 5: Save
        filepath = self.save_output(report)
        print(f"\nReport saved to: {filepath}")
        
        return report


def main():
    parser = argparse.ArgumentParser(description="Polymarket Arbitrage Screener")
    parser.add_argument("--category", type=str, default="politics", help="Market category")
    parser.add_argument("--min-volume", type=float, default=10000, help="Minimum market volume ($)")
    parser.add_argument("--limit", type=int, default=200, help="Max markets to fetch")
    parser.add_argument("--output", type=str, help="Output file path")
    
    args = parser.parse_args()
    
    screener = ArbitrageScreener()
    report = screener.run(
        category=args.category,
        min_volume=args.min_volume,
    )
    
    print("\n" + report)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
