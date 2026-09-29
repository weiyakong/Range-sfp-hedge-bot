import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import readline from 'node:readline';

function startServer() {
  const child = spawn(process.execPath, ['src/mcp-server.js'], {
    cwd: new URL('..', import.meta.url),
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  const rl = readline.createInterface({ input: child.stdout, crlfDelay: Infinity });
  const messages = [];
  rl.on('line', (line) => messages.push(JSON.parse(line)));
  return { child, messages };
}

function send(child, message) {
  child.stdin.write(`${JSON.stringify(message)}\n`);
}

async function waitFor(messages, id, timeoutMs = 3000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const found = messages.find((message) => message.id === id);
    if (found) return found;
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  throw new Error(`Timed out waiting for MCP response id=${id}`);
}

test('MCP server exposes only the project read-only tools', async (t) => {
  const { child, messages } = startServer();
  t.after(() => child.kill());

  send(child, { jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2025-06-18' } });
  const init = await waitFor(messages, 1);
  assert.equal(init.result.serverInfo.name, 'range-sfp-ccxt-readonly');

  send(child, { jsonrpc: '2.0', method: 'notifications/initialized' });
  send(child, { jsonrpc: '2.0', id: 2, method: 'tools/list' });
  const listed = await waitFor(messages, 2);
  assert.deepEqual(listed.result.tools.map((tool) => tool.name).sort(), [
    'ccxt_capabilities',
    'ccxt_find_usdt_perpetuals',
    'ccxt_public_call',
  ]);

  send(child, { jsonrpc: '2.0', id: 3, method: 'tools/call', params: { name: 'ccxt_capabilities', arguments: {} } });
  const capabilities = await waitFor(messages, 3);
  assert.equal(capabilities.result.isError, undefined);
  assert.match(capabilities.result.content[0].text, /"binance"/);
});

test('MCP server rejects credential-like input before any CCXT call', async (t) => {
  const { child, messages } = startServer();
  t.after(() => child.kill());

  send(child, { jsonrpc: '2.0', id: 10, method: 'initialize', params: { protocolVersion: '2025-06-18' } });
  await waitFor(messages, 10);

  send(child, {
    jsonrpc: '2.0', id: 11, method: 'tools/call',
    params: {
      name: 'ccxt_public_call',
      arguments: {
        exchange: 'binance',
        operation: 'fetchTicker',
        args: ['BTC/USDT:USDT', { apiKey: 'forbidden' }],
      },
    },
  });
  const response = await waitFor(messages, 11);
  assert.equal(response.result.isError, true);
  assert.match(response.result.content[0].text, /credential-like field is forbidden/i);
});
