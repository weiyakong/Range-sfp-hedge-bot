# Stage 2I-A: raw 4H pivots

This stage builds an unfiltered population of strict five-bar BTCUSDT 4H pivots and transparent candle, neighbor-pivot, local-geometry, and fixed-horizon context.

It does not assign importance, remove micro fluctuations, construct zones or trends, or run a trading test. `causal__*` fields are known by `available_from`; `postevent__*` fields are diagnostic only and must not be used as pivot-time predictors.

## Run

```bash
python3 research/btc_macro_nautilus/stage2i_a_raw_4h_pivots/build_stage2i_a.py \
  --data-root /Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data \
  --repo-root /Users/yeshevika/Documents/Codex/2026-07-27/new-chat/work/range-sfp-hedge-bot-clone \
  --mode production
```

Use `--mode smoke --output-dir /tmp/stage2i_a_smoke` before production. The production output is atomically published at `DATA_ROOT/research/stage2i_a_raw_4h_pivots/` only after internal QA passes.

## Raw definition

- HIGH: center high is strictly greater than the highs of the two candles on each side.
- LOW: center low is strictly less than the lows of the two candles on each side.
- Equal extrema do not pass.
- A center candle passing both tests produces two events.
- Incomplete candles are excluded and break a contiguous run; windows never bridge them or another gap.
- `available_from` is the close of the second right-hand 4H candle.

Neighbor relations exclude the other event on a dual-event candle. If a neighboring candle contains both event types, HIGH precedes LOW as a deterministic tie-break only; neither event is removed or semantically preferred.

Fixed-horizon upward/downward excursions are non-negative distances from pivot price. Signed close displacement is stored separately. Local path length and efficiency reuse close-to-close path geometry; endpoint move itself is measured between raw pivot prices.

## Tests

```bash
python3 -m unittest research/btc_macro_nautilus/stage2i_a_raw_4h_pivots/test_build_stage2i_a.py
python3 -m unittest research/btc_macro_nautilus/stage2i_a_raw_4h_pivots/test_review_stage2i_a.py
```

## Diagnostic structure review

The non-labeling Stage 2I-A review is reproducible with:

```bash
python3 research/btc_macro_nautilus/stage2i_a_raw_4h_pivots/review_stage2i_a.py \
  --data-root /Users/yeshevika/Documents/Codex/Range-sfp-hedge-bot-data \
  --repo-root /Users/yeshevika/Documents/Codex/2026-07-27/new-chat/work/range-sfp-hedge-bot-clone \
  --mode production
```

It creates diagnostic tables/charts under `DATA_ROOT/research/stage2i_a_raw_4h_pivots/pivot_structure_review/` and a machine-readable summary beside the frozen Stage A artifacts. It does not alter the Stage A Parquet or implement Stage B.
