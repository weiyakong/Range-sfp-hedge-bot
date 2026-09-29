import test from 'node:test';
import assert from 'node:assert/strict';
import { ALLOWED_EXCHANGES, ALLOWED_OPERATIONS, createReadOnlyClient, assertAllowedOperation } from '../src/index.js';

test('only approved exchanges are exposed', () => {
  assert.deepEqual([...ALLOWED_EXCHANGES].sort(), ['binance', 'bybit', 'okx']);
});

test('dangerous/private operations are not allowlisted', () => {
  for (const forbidden of ['createOrder','cancelOrder','fetchBalance','withdraw','transfer','setLeverage','setMarginMode']) {
    assert.equal(ALLOWED_OPERATIONS.has(forbidden), false, forbidden);
    assert.throws(() => assertAllowedOperation(forbidden), /not allowed/i);
  }
});

test('approved public operations are allowlisted', () => {
  for (const allowed of ['fetchTicker','fetchOrderBook','fetchTrades','fetchFundingRate','fetchFundingRateHistory','fetchOpenInterest','fetchOpenInterestHistory','fetchLiquidations']) {
    assert.equal(ALLOWED_OPERATIONS.has(allowed), true, allowed);
  }
});

test('read-only client does not expose credentials or trading methods', () => {
  const client = createReadOnlyClient('binance');
  for (const property of ['apiKey','secret','password','createOrder','cancelOrder','withdraw','transfer']) {
    assert.equal(property in client, false, property);
  }
  assert.equal(client.exchangeId, 'binance');
});

test('unsupported exchanges and constructor options are rejected', () => {
  assert.throws(() => createReadOnlyClient('kraken'), /exchange is not allowed/i);
  assert.throws(() => createReadOnlyClient('binance', { apiKey: 'x' }), /does not accept credentials or custom options/i);
});
