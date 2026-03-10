/**
 * CLI for Polymarket API testing
 * Usage: node src/cli.js <command> [args]
 */

import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import PolymarketClient from './api/client.js';

const __dirname = dirname(fileURLToPath(import.meta.url));

// Load config if exists
let config = {};
try {
  config = JSON.parse(readFileSync(join(__dirname, '../config.json'), 'utf-8'));
} catch (e) {
  // No config file, use defaults
}

const client = new PolymarketClient(config);

const commands = {
  // Markets
  'markets': async (args) => {
    const markets = await client.getMarkets({ limit: 10, ...parseArgs(args) });
    console.log(JSON.stringify(markets, null, 2));
  },

  'market': async (args) => {
    const [slugOrCid] = args;
    const market = await client.getMarketDetails(slugOrCid);
    console.log(JSON.stringify(market, null, 2));
  },

  'prices': async (args) => {
    const [slugOrCid] = args;
    const result = await client.getMarketPrices(slugOrCid);
    console.log(JSON.stringify(result, null, 2));
  },

  // Events
  'events': async (args) => {
    const events = await client.getEvents({ limit: 10, ...parseArgs(args) });
    console.log(JSON.stringify(events, null, 2));
  },

  // Market data
  'orderbook': async (args) => {
    const [tokenId] = args;
    const orderbook = await client.getOrderBook(tokenId);
    console.log(JSON.stringify(orderbook, null, 2));
  },

  'history': async (args) => {
    const [tokenId, interval = '1h', startTs, endTs] = args;
    const history = await client.getPriceHistory({
      market: tokenId,
      interval,
      startTs: startTs ? parseInt(startTs) : undefined,
      endTs: endTs ? parseInt(endTs) : undefined,
    });
    console.log(JSON.stringify(history, null, 2));
  },

  'trades': async (args) => {
    const [addressOrCid, limit = '50'] = args;
    let trades;
    if (addressOrCid.length === 66 || addressOrCid.startsWith('0x')) {
      // Likely an Ethereum address
      trades = await client.getUserTrades(addressOrCid, { limit: parseInt(limit) });
    } else {
      // Assume condition ID
      trades = await client.getMarketTrades(addressOrCid, { limit: parseInt(limit) });
    }
    console.log(JSON.stringify(trades, null, 2));
  },

  'positions': async (args) => {
    const [addressOrCid] = args;
    let positions;
    if (addressOrCid.length === 66 || addressOrCid.startsWith('0x')) {
      positions = await client.getUserPositions(addressOrCid);
    } else {
      positions = await client.getMarketPositions(addressOrCid);
    }
    console.log(JSON.stringify(positions, null, 2));
  },

  // Search
  'search': async (args) => {
    const [query, ...rest] = args;
    const markets = await client.searchMarkets(query);
    console.log(JSON.stringify(markets.slice(0, 10), null, 2));
  },

  'help': () => {
    console.log(`
Polymarket CLI

Commands:
  markets [limit]           List open markets
  market <slug-or-cid>     Get market details
  prices <slug-or-cid>     Get current prices for a market
  events [limit]           List events
  orderbook <tokenId>      Get orderbook for a token
  history <tokenId> [interval] [startTs] [endTs]  Get price history
  trades <address-or-cid>  Get trades for user or market
  positions <address-or-cid>  Get positions for user or market
  search <query>           Search markets

Examples:
  node src/cli.js markets limit=5
  node src/cli.js prices trump-wins-2024
  node src/cli.js history 0x123... 1h
  node src/cli.js trades 0xabc...
`);
  },
};

function parseArgs(args) {
  const result = {};
  for (const arg of args) {
    const [key, value] = arg.split('=');
    if (key && value !== undefined) {
      result[key] = isNaN(value) ? value : Number(value);
    }
  }
  return result;
}

async function main() {
  const [cmd, ...args] = process.argv.slice(2);
  
  if (!cmd || cmd === 'help') {
    commands.help();
    return;
  }

  if (commands[cmd]) {
    try {
      await commands[cmd](args);
    } catch (e) {
      console.error('Error:', e.message);
      process.exit(1);
    }
  } else {
    console.error(`Unknown command: ${cmd}`);
    commands.help();
    process.exit(1);
  }
}

main();
