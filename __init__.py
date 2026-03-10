"""Polymarket helpers package (Python).

Preferred imports:
  from polymarket import PolymarketClient
  from polymarket.polymarket import PolymarketClient
"""

from .polymarket import PolymarketClient, get_client

__all__ = ["PolymarketClient", "get_client"]
