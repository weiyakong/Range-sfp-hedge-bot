# Atomic futures features

This reusable pipeline reads the validated canonical BTCUSDT futures 4H, 12H,
and 1D candle manifests and materializes contract-defined candle and adjacent-pair
features. It does not consume macro labels or segment boundaries.

Implemented families:

- complete-candle geometry and directional volume;
- adjacent close movement, log movement, speed, direction, and alternation;
- true range plus reset-aware ATR14 SMA and Wilder forms;
- range/body overlap, neutral extensions, and symmetric penetration.

Each output manifest embeds a feature dictionary, exact candle-manifest checksum,
output checksums, QA result, and code provenance. Outputs are year-partitioned
Zstandard Parquet outside Git.

```bash
python3 research/btc_macro_nautilus/atomic_features/build_atomic_features.py \
  --data-root /path/to/Range-sfp-hedge-bot-data \
  --repo-root .
```
