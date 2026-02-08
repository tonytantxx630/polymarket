import { describe, it, expect } from 'vitest';
import { fetchMarkets, fetchAllHistoricalMarkets } from './gamma';

describe('Polymarket Gamma API', () => {
  it('should fetch active markets', async () => {
    const markets = await fetchMarkets({ active: true, closed: false, limit: 5 });
    expect(Array.isArray(markets)).toBe(true);
    expect(markets.length).toBeGreaterThan(0);
    expect(markets[0].active).toBe(true);
    expect(markets[0].closed).toBe(false);
  });

  it('should fetch inactive/closed markets', async () => {
    const markets = await fetchMarkets({ active: false, closed: true, limit: 5 });
    expect(Array.isArray(markets)).toBe(true);
    expect(markets.length).toBeGreaterThan(0);
    // Inactive markets should have closed: true
    expect(markets[0].closed).toBe(true);
  });

  it('should fetch a combined batch of historical data', async () => {
    const data = await fetchAllHistoricalMarkets(2);
    expect(data.active).toBeDefined();
    expect(data.inactive).toBeDefined();
    expect(data.active.length).toBeLessThanOrEqual(2);
    expect(data.inactive.length).toBeLessThanOrEqual(2);
  });
});
