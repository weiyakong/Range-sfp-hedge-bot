#!/usr/bin/env node

import readline from 'node:readline';
import {
  ALLOWED_EXCHANGES,
  ALLOWED_OPERATIONS,
  capabilityMatrix,
  createReadOnlyClient,
  findUsdtPerpetualMarkets,
} from './index.js';

const SERVER_INFO = { name: 'range-sfp-ccxt-readonly', version: '0.1.0' };
const CREDENTIAL_KEYS = /^(api[_-]?key|secret|password|passphrase|token|private[_-]?key|wallet|uid)$/i;

function send(message) {
  process.stdout.write(`${JSON.stringify(message)}\n`);
}

function fail(id, code, message, data) {
  send({ jsonrpc: '2.0', id, error: { code, message, ...(data === undefined ? {} : { data }) } });
}

function assertNoCredentials(value, path = '$') {
  if (Array.isArray(value)) {
    value.forEach((item, index) => assertNoCredentials(item, `${path}[${index}]`));
    return;
  }
  if (!value || typeof value !== 'object') return;
  for (const [key, item] of Object.entries(value)) {
    if (CREDENTIAL_KEYS.test(key)) throw new Error(`Credential-like field is forbidden: ${path}.${key}`);
    assertNoCredentials(item, `${path}.${key}`);
  }
}

const TOOLS = [
  {
    name: 'ccxt_capabilities',
    description: 'Return the read-only CCXT capability matrix for Binance, Bybit, and OKX. No network call.',
    inputSchema: { type: 'object', properties: {}, additionalProperties: false },
  },
  {
    name: 'ccxt_find_usdt_perpetuals',
    description: 'Discover active USDT-settled perpetual swap markets for a base asset on one approved exchange.',
    inputSchema: {
      type: 'object', required: ['exchange'], additionalProperties: false,
      properties: {
        exchange: { type: 'string', enum: ALLOWED_EXCHANGES },
        base: { type: 'string', default: 'BTC' },
      },
    },
  },
  {
    name: 'ccxt_public_call',
    description: 'Call one allowlisted public CCXT unified method. Credentials and private/trading methods are impossible through this tool.',
    inputSchema: {
      type: 'object', required: ['exchange', 'operation'], additionalProperties: false,
      properties: {
        exchange: { type: 'string', enum: ALLOWED_EXCHANGES },
        operation: { type: 'string', enum: [...ALLOWED_OPERATIONS] },
        args: { type: 'array', default: [] },
      },
    },
  },
];

async function findUsdtPerpetuals(exchangeId, base = 'BTC') {
  return findUsdtPerpetualMarkets(exchangeId, base);
}

function toolResult(value) {
  return { content: [{ type: 'text', text: JSON.stringify(value, null, 2) }] };
}
async function handleToolCall(name, args = {}) {
  assertNoCredentials(args);
  if (name === 'ccxt_capabilities') return toolResult(capabilityMatrix());
  if (name === 'ccxt_find_usdt_perpetuals') {
    return toolResult(await findUsdtPerpetuals(args.exchange, args.base ?? 'BTC'));
  }
  if (name === 'ccxt_public_call') {
    const client = createReadOnlyClient(args.exchange);
    try {
      const callArgs = Array.isArray(args.args) ? args.args : [];
      return toolResult(await client.call(args.operation, ...callArgs));
    } finally {
      await client.close();
    }
  }
  throw new Error(`Unknown tool: ${name}`);
}

async function handleRequest(message) {
  const id = message.id;
  const method = message.method;
  if (method === 'initialize') {
    const protocolVersion = message.params?.protocolVersion ?? '2025-06-18';
    send({ jsonrpc: '2.0', id, result: {
      protocolVersion,
      capabilities: { tools: { listChanged: false } },
      serverInfo: SERVER_INFO,
    } });
    return;
  }
  if (method === 'ping') {
    send({ jsonrpc: '2.0', id, result: {} });
    return;
  }
  if (method === 'tools/list') {
    send({ jsonrpc: '2.0', id, result: { tools: TOOLS } });
    return;
  }
  if (method === 'tools/call') {
    try {
      const result = await handleToolCall(message.params?.name, message.params?.arguments ?? {});
      send({ jsonrpc: '2.0', id, result });
    } catch (error) {
      send({ jsonrpc: '2.0', id, result: {
        content: [{ type: 'text', text: String(error?.message ?? error) }],
        isError: true,
      } });
    }
    return;
  }
  if (method?.startsWith('notifications/')) return;
  fail(id, -32601, `Method not found: ${method}`);
}

const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
rl.on('line', async (line) => {
  if (!line.trim()) return;
  try {
    const message = JSON.parse(line);
    if (message.jsonrpc !== '2.0') throw new Error('Expected JSON-RPC 2.0');
    await handleRequest(message);
  } catch (error) {
    fail(null, -32700, 'Parse error', String(error?.message ?? error));
  }
});
