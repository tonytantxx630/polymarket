/**
 * Polymarket API Client
 * 
 * Provides access to:
 * - Gamma API: Markets, events, search (public)
 * - Data API: Positions, trades, activity (public)
 * - CLOB API: Orderbook, prices, historical (public endpoints)
 */

const BASE_URLS = {
  gamma: 'https://gamma-api.polymarket.com',
  data: 'https://data-api.polymarket.com',
  clob: 'https://clob.polymarket.com',
};

class PolymarketClient {
  constructor(options = {}) {
    this.apiKey = options.apiKey;
    this.apiSecret = options.apiSecret;
    this.apiPassphrase = options.apiPassphrase;
  }

  // ============ GAMMA API (Markets, Events, Search) ============

  async getMarkets(params = {}) {
    // GET /markets
    // Params: closed, archived, limit, cursor, sortBy, order
    return this._request('gamma', 'GET', '/markets', params);
  }

  async getEvents(params = {}) {
    // GET /events
    // Params: limit, cursor, closed, archived
    return this._request('gamma', 'GET', '/events', params);
  }

  async getEvent(eventId) {
    // GET /events/{eventId}
    return this._request('gamma', 'GET', `/events/${eventId}`);
  }

  async getMarketsByCondition(conditionId) {
    // GET /markets?conditionId={conditionId}
    return this._request('gamma', 'GET', '/markets', { conditionId });
  }

  async getMarketsBySlug(slug) {
    // GET /markets?slug={slug}
    return this._request('gamma', 'GET', '/markets', { slug });
  }

  async searchMarkets(query, params = {}) {
    // GET /markets?search={query}
    return this._request('gamma', 'GET', '/markets', { search: query, ...params });
  }

  async getMarketsByTag(tag, params = {}) {
    // GET /markets?tag={tag}
    return this._request('gamma', 'GET', '/markets', { tag, ...params });
  }

  async getToken(tokenId) {
    // GET /tokens/{tokenId}
    return this._request('gamma', 'GET', `/tokens/${tokenId}`);
  }

  async getCondition(conditionId) {
    // GET /conditions/{conditionId}
    return this._request('gamma', 'GET', `/conditions/${conditionId}`);
  }

  // ============ DATA API (Positions, Trades, Activity) ============

  async getUserPositions(address) {
    // GET /api positions?address={address}
    return this._request('data', 'GET', '/api/positions', { address });
  }

  async getUserTrades(address, params = {}) {
    // GET /api trades?address={address}
    // Params: limit, beforeTimestamp, afterTimestamp
    return this._request('data', 'GET', '/api/trades', { address, ...params });
  }

  async getUserActivity(address, params = {}) {
    // GET /api activity?address={address}
    return this._request('data', 'GET', '/api/activity', { address, ...params });
  }

  async getMarketTrades(marketCid, params = {}) {
    // GET /api/trades?condition_id={marketCid}
    return this._request('data', 'GET', '/api/trades', { condition_id: marketCid, ...params });
  }

  async getMarketPositions(marketCid) {
    // GET /api/positions?condition_id={marketCid}
    return this._request('data', 'GET', '/api/positions', { condition_id: marketCid });
  }

  async getOpenInterest(marketCid) {
    // GET /api/positions?condition_id={marketCid}
    const positions = await this.getMarketPositions(marketCid);
    // Sum up all positions for open interest
    return positions.reduce((sum, p) => sum + (parseFloat(p.volume) || 0), 0);
  }

  // ============ CLOB API (Orderbook, Prices, Historical) ============

  async getOrderBook(tokenId) {
    // GET /orderbook?token_id={tokenId}
    return this._request('clob', 'GET', '/orderbook', { token_id: tokenId });
  }

  async getPrice(tokenId) {
    // GET /price?token_id={tokenId}
    return this._request('clob', 'GET', '/price', { token_id: tokenId });
  }

  async getPrices(tokenIds) {
    // GET /prices?token_ids={tokenIds}
    const ids = Array.isArray(tokenIds) ? tokenIds.join(',') : tokenIds;
    return this._request('clob', 'GET', '/prices', { token_ids: ids });
  }

  async getPriceHistory(params) {
    // GET /prices-history
    // Required: market (token id)
    // Optional: startTs, endTs (unix timestamps in SECONDS), interval (1m/1h/1d/1w/max), fidelity
    // Note: startTs/endTs interval too long will error - fetch in chunks
    return this._request('clob', 'GET', '/prices-history', params);
  }

  async getPriceHistoryRange(tokenId, interval = '1h', daysBack = 7) {
    // Helper to get price history for a date range
    const endTs = Math.floor(Date.now() / 1000);
    const startTs = endTs - (daysBack * 24 * 60 * 60);
    
    return this.getPriceHistory({
      market: tokenId,
      interval,
      startTs,
      endTs,
    });
  }

  async getMidpoint(tokenId) {
    // GET /midpoint?token_id={tokenId}
    return this._request('clob', 'GET', '/midpoint', { token_id: tokenId });
  }

  async getSpread(tokenId) {
    // GET /spread?token_id={tokenId}
    return this._request('clob', 'GET', '/spread', { token_id: tokenId });
  }

  async getFeeRate(tokenId) {
    // GET /fee-rate?token_id={tokenId}
    return this._request('clob', 'GET', '/fee-rate', { token_id: tokenId });
  }

  // ============ AUTHENTICATED ENDPOINTS (require wallet/keys) ============

  async placeOrder(order) {
    // POST /orders
    // Requires: maker, signer, taker, tokenId, makerAmount, takerAmount, expiration, nonce, side, signature
    if (!this.apiKey) throw new Error('API key required for order placement');
    return this._request('clob', 'POST', '/orders', order, true);
  }

  async cancelOrder(orderId) {
    // DELETE /orders/{orderId}
    if (!this.apiKey) throw new Error('API key required for order cancellation');
    return this._request('clob', 'DELETE', `/orders/${orderId}`, {}, true);
  }

  async getUserOrders(address) {
    // GET /orders?address={address}
    if (!this.apiKey) throw new Error('API key required for user orders');
    return this._request('clob', 'GET', '/orders', { address }, true);
  }

  // ============ HELPER METHODS ============

  async getMarketDetails(marketCidOrSlug) {
    // Try by slug first, then by condition ID
    try {
      const markets = await this.getMarketsBySlug(marketCidOrSlug);
      if (markets.length) return markets[0];
    } catch (e) {}
    
    const markets = await this.getMarketsByCondition(marketCidOrSlug);
    return markets[0] || null;
  }

  async getMarketPrices(marketCidOrSlug) {
    const market = await this.getMarketDetails(marketCidOrSlug);
    if (!market) throw new Error('Market not found');
    
    const tokens = market.tokens || [];
    const prices = {};
    
    for (const token of tokens) {
      const tokenId = token.token_id;
      try {
        const priceData = await this.getPrice(tokenId);
        prices[token.outcome] = {
          tokenId,
          price: priceData.price,
          ...priceData,
        };
      } catch (e) {
        prices[token.outcome] = { tokenId, error: e.message };
      }
    }
    
    return { market, prices };
  }

  // ============ REQUEST HANDLER ============

  async _request(api, method, path, params = {}, authenticated = false) {
    const baseUrl = BASE_URLS[api];
    
    // Build URL with query string for GET requests
    let url = `${baseUrl}${path}`;
    if (method === 'GET' && params && Object.keys(params).length > 0) {
      const searchParams = new URLSearchParams();
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== null) {
          searchParams.append(key, String(value));
        }
      }
      url += '?' + searchParams.toString();
    }
    
    const config = {
      method,
      headers: {
        'Content-Type': 'application/json',
      },
    };
    
    if (method !== 'GET' && params) {
      config.body = JSON.stringify(params);
    }

    if (authenticated && this.apiKey) {
      // Add authentication headers
      config.headers['POLY_API_KEY'] = this.apiKey;
      // Note: Full auth requires signature generation
    }

    const response = await fetch(url, {
      ...config,
      params: config.params,
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Polymarket API error (${response.status}): ${error}`);
    }

    return response.json();
  }
}

export default PolymarketClient;
export { PolymarketClient, BASE_URLS };
