# CCXT Read-Only Gateway

Project-owned wrapper around CCXT for public market data only.

## Scope

- Exchanges: Binance, Bybit, OKX.
- No API keys or exchange credentials are accepted.
- Only an explicit allowlist of public read operations is exposed.
- Trading, account, transfer, withdrawal, leverage, and margin-changing operations are not exposed.
- This package is shared project infrastructure; MCP/CLI adapters may use it, but do not own the policy.

## Install

```bash
npm ci
```

## Validate without exchange API calls

```bash
npm test
npm run smoke:local
```

`smoke:local` only inspects CCXT's declared capabilities. It does not call Binance, Bybit, or OKX.

## External API calls

Real exchange smoke tests are a separate step and require explicit authorization for that task.
