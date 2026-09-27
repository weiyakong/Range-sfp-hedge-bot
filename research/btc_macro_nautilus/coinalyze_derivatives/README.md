# Coinalyze BTC derivatives layer

This directory contains a read-only market-data collector for one dynamically
discovered BTC perpetual on each supported target exchange (Binance, Bybit,
OKX). It stores Coinalyze source responses separately from normalized Parquet
and never aggregates exchanges.

See `CONTRACTS.md` for the table, provenance, missing-data, resume, and
rate-limit contracts. No trading endpoint is used.

The implementation intentionally uses the Python standard library for HTTP and
`.env` parsing. Parquet uses the existing repository `pyarrow` stack; no new
dependency is required.

## Commands

Run the required real-data smoke before a full backfill:

```bash
python3 research/btc_macro_nautilus/coinalyze_derivatives/collect_coinalyze_derivatives.py \
  --mode smoke \
  --data-root /path/to/Range-sfp-hedge-bot-data
```

Then backfill all four datasets and intervals for the three selected markets:

```bash
python3 research/btc_macro_nautilus/coinalyze_derivatives/collect_coinalyze_derivatives.py \
  --mode backfill \
  --data-root /path/to/Range-sfp-hedge-bot-data
```

Continuous collection can run either as an idempotent one-shot cycle under the
user's scheduler or as a foreground polling process. Each cycle discovers
markets again, reads each 1-minute partition's last timestamp, and requests
only the missing tail. Running it manually once starts today's local history
without modifying the operating system's scheduler:

```bash
python3 research/btc_macro_nautilus/coinalyze_derivatives/collect_coinalyze_derivatives.py \
  --mode continuous \
  --data-root /path/to/Range-sfp-hedge-bot-data
```

For a long-running foreground collector, add
`--continuous-poll-seconds 60`. Stop it with `Ctrl-C`; the next invocation
resumes from the last atomically saved minute.

The process uses `COINALYZE_API_KEY` from the environment or repository-local
`.env`. It never places the key in a URL or artifact.
