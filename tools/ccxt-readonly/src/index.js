import ccxt from 'ccxt';

export const ALLOWED_EXCHANGES = Object.freeze(['binance', 'bybit', 'okx']);

export const ALLOWED_OPERATIONS = new Set([
  'fetchTicker',
  'fetchOrderBook',
  'fetchTrades',
  'fetchFundingRate',
  'fetchFundingRateHistory',
  'fetchOpenInterest',
  'fetchOpenInterestHistory',
  'fetchLiquidations',
  'fetchLiquidationsHistory',
]);

export function assertAllowedOperation(operation) {
  if (!ALLOWED_OPERATIONS.has(operation)) {
    throw new Error(`Operation is not allowed by the read-only policy: ${operation}`);
  }
}

function buildExchange(exchangeId) {
  if (!ALLOWED_EXCHANGES.includes(exchangeId)) {
    throw new Error(`Exchange is not allowed by the read-only policy: ${exchangeId}`);
  }
  const Exchange = ccxt[exchangeId];
  if (typeof Exchange !== 'function') {
    throw new Error(`CCXT exchange implementation is unavailable: ${exchangeId}`);
  }
  return new Exchange({ enableRateLimit: true });
}

export function createReadOnlyClient(exchangeId, options) {
  if (options !== undefined) {
    throw new Error('Read-only client does not accept credentials or custom options');
  }
  const exchange = buildExchange(exchangeId);
  return Object.freeze({
    exchangeId,
    supports(operation) {
      assertAllowedOperation(operation);
      return Boolean(exchange.has?.[operation]);
    },
    async call(operation, ...args) {
      assertAllowedOperation(operation);
      if (!exchange.has?.[operation]) {
        throw new Error(`${exchangeId} does not report support for ${operation}`);
      }
      return exchange[operation](...args);
    },
    async close() {
      if (typeof exchange.close === 'function') await exchange.close();
    },
  });
}

export function capabilityMatrix() {
  return Object.fromEntries(ALLOWED_EXCHANGES.map((exchangeId) => {
    const exchange = buildExchange(exchangeId);
    return [exchangeId, Object.fromEntries([...ALLOWED_OPERATIONS].map((operation) => [operation, Boolean(exchange.has?.[operation])]))];
  }));
}
