/**
 * Polymarket API Client
 * 
 * @example
 * import PolymarketClient from '@tonytan/polymarket';
 * 
 * const client = new PolymarketClient();
 * const markets = await client.getMarkets({ limit: 10 });
 * const prices = await client.getMarketPrices('trump-wins-2024');
 * const history = await client.getPriceHistory({ 
 *   market: '0x123...', 
 *   interval: '1h',
 *   startTs: Date.now() - 7 * 24 * 60 * 60 * 1000 // 7 days ago
 * });
 */

export { default as PolymarketClient, BASE_URLS } from './api/client.js';
