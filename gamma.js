export async function fetchMarkets({ active = true, closed = false, limit = 20, offset = 0 } = {}) {
  const url = new URL('https://gamma-api.polymarket.com/markets');
  url.searchParams.set('active', active.toString());
  url.searchParams.set('closed', closed.toString());
  url.searchParams.set('limit', limit.toString());
  url.searchParams.set('offset', offset.toString());

  const response = await fetch(url.toString());
  if (!response.ok) {
    throw new Error(`Failed to fetch markets: ${response.statusText}`);
  }
  return await response.json();
}

export async function fetchAllHistoricalMarkets(batchSize = 100) {
  // Fetch a batch of both active and inactive markets
  const active = await fetchMarkets({ active: true, closed: false, limit: batchSize });
  const inactive = await fetchMarkets({ active: false, closed: true, limit: batchSize });
  
  return {
    active,
    inactive
  };
}
