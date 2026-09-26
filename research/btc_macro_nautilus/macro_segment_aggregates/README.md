# Futures macro-segment aggregates

This pipeline joins the approved `macro_legs_log20.csv` futures segments to
validated 4H, 12H, and 1D atomic features without changing macro labels or
creating new points. It uses only whole canonical candles guaranteed inside
each boundary: exact pivots use their exact timestamp; unresolved pivots use
the conservative candidate-window interior required by the v5 contract.

The output preserves source macro direction and provenance. The approved macro
legs source has no impulse/correction class field, so `known_macro_class` is
intentionally null rather than inferred.

```bash
python3 research/btc_macro_nautilus/macro_segment_aggregates/build_macro_segment_aggregates.py \
  --data-root /path/to/Range-sfp-hedge-bot-data \
  --repo-root .
```

Progress buckets, extremum-update metrics, and fragment-inclusive metrics remain
deferred until their required contract definitions/artifacts are available.
