import PolymarketClient from '../src/api/client.js';

const client = new PolymarketClient();

async function test() {
  console.log('🧪 Testing Polymarket API...\n');

  // Test 1: Get markets
  console.log('1. Fetching markets...');
  const markets = await client.getMarkets({ limit: 3 });
  console.log(`   Found ${markets.length} markets`);
  if (markets.length) {
    console.log(`   Sample: ${markets[0].question?.slice(0, 50)}...`);
  }

  // Test 2: Get events
  console.log('\n2. Fetching events...');
  const events = await client.getEvents({ limit: 3 });
  console.log(`   Found ${events.length} events`);

  // Test 3: Get prices for first market
  if (markets.length) {
    console.log('\n3. Fetching prices for first market...');
    const slug = markets[0].slug;
    try {
      const prices = await client.getMarketPrices(slug);
      console.log(`   Prices:`, JSON.stringify(prices.prices, null, 2));
    } catch (e) {
      console.log(`   Error: ${e.message}`);
    }
  }

  // Test 4: Price history (if we have a token)
  console.log('\n4. Testing price history...');
  try {
    // Use a known token ID or first market's token
    const testToken = markets[0]?.tokens?.[0]?.token_id || '0x123';
    const history = await client.getPriceHistory({
      market: testToken,
      interval: '1h',
    });
    console.log(`   History points: ${history.history?.length || 0}`);
  } catch (e) {
    console.log(`   Error: ${e.message}`);
  }

  console.log('\n✅ Tests complete!');
}

test().catch(console.error);
