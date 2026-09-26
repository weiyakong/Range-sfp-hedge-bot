# Canonical futures candles

This pipeline builds Binance USDT-M `BTCUSDT` candles directly
and independently from the strict 1-minute source manifest. It writes year-partitioned
Zstandard Parquet outside Git and records source/output checksums in a manifest for
each resolution.

```bash
python3 research/btc_macro_nautilus/canonical_candles/build_canonical_futures_candles.py \
  --source-manifest /path/to/strict_futures_1m_manifest.json \
  --data-root /path/to/Range-sfp-hedge-bot-data \
  --repo-root . \
  --resolutions 3m 5m 15m
```

Intervals use UTC half-open boundaries. Incomplete intervals are retained with their
actual constituent count and an explicit reason. The known 2019-09-08 19:00 UTC gap
is never synthesized. `start_time` is the UTC bar-open timestamp and `end_time` is
exclusive. Existing 4h, 12h, and 1d outputs can still be built by selecting those
resolutions explicitly.
