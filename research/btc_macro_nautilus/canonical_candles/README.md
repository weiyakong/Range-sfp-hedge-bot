# Canonical futures candles

This pipeline builds Binance USDT-M `BTCUSDT` 4H, 12H, and 1D candles directly
and independently from the strict 1-minute source manifest. It writes year-partitioned
Zstandard Parquet outside Git and records source/output checksums in a manifest for
each resolution.

```bash
python3 research/btc_macro_nautilus/canonical_candles/build_canonical_futures_candles.py \
  --source-manifest /path/to/strict_futures_1m_manifest.json \
  --data-root /path/to/Range-sfp-hedge-bot-data \
  --repo-root .
```

Intervals use UTC half-open boundaries. Incomplete intervals are retained with their
actual constituent count and an explicit reason. The known 2019-09-08 19:00 UTC gap
is never synthesized.
