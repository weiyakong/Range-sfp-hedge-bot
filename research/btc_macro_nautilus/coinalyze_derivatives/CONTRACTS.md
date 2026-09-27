# Coinalyze BTC derivatives collector contracts

Schema version: `coinalyze-btc-derivatives-v1`.

This is an additive data layer. It does not read, rewrite, or classify Stage 2I
price-action outputs.

## Market discovery

The collector must call `GET /v1/future-markets` before selecting symbols. The
response uses exchange codes, so `GET /v1/exchanges` is then used only to
resolve those codes to names. A market is a candidate only when
`base_asset == "BTC"`, `is_perpetual == true`, and its resolved exchange is
Binance, Bybit, or OKX (case-insensitive exact match, where available). Symbol
identifiers and exchange codes are never hardcoded in source code.

### Canonical selection policy

The canonical selection policy literal is:
`selection_policy = "primary_usdt_v1"`

An eligible primary market candidate must strictly satisfy:
- `exchange` ∈ {`Binance`, `Bybit`, `OKX`} (case-insensitive exact match);
- `base_asset == "BTC"`;
- `quote_asset == "USDT"`;
- `is_perpetual == true`.

Only markets satisfying all four criteria are eligible to have `selected == true`.

### No non-USDT fallback

If an eligible BTC/USDT perpetual is absent for a given target exchange:
- no market is selected for that exchange (`selected` count is strictly 0);
- there is strictly NO fallback to USDC;
- there is strictly NO fallback to USD;
- there is strictly NO fallback to any other quote asset;
- no synthetic or placeholder selected row is created.

Non-USDT BTC perpetual markets (such as USDC or coin-margined contracts) may be
retained in the discovery snapshot as unselected alternatives (`selected == false`),
but they never become a primary selected market in V1.

### Canonical selection reasons

Exact canonical literals are:
- For selected primary market (`selected == true`):
  `selection_reason = "primary_usdt_perpetual"`
  (prefix matching like `startsWith("primary_")` is invalid);
- For unselected candidate markets (`selected == false`):
  `selection_reason = "alternative_perpetual"` (or `"candidate"`).

### Exactly-one-where-available invariant

For each target exchange represented in the discovery catalog:
- if eligible BTC/USDT perpetual candidates > 0:
  `selected == true` must hold for **exactly one** market;
- if eligible BTC/USDT perpetual candidates == 0:
  `selected == true` must hold for **zero** markets.

Unconditional presence of all three target exchanges is not required (`where available`).

### Deterministic winner ranking

Among eligible BTC/USDT perpetual candidates for a given exchange, the primary
market is chosen deterministically by:
1. Stable-margin preference (`margined == "STABLE"` ranked ahead of non-stable);
2. Deterministic alphabetical tie-break on `coinalyze_symbol`.

This ranking applies exclusively among eligible BTC/USDT perpetual candidates.
Non-USDT markets do not participate in primary market ranking.

Backfill and smoke runs always refresh discovery. Continuous cycles reuse a
validated discovery manifest for at most 24 hours, then refresh it. This avoids
archiving the full market catalog every minute while still detecting symbol or
exchange changes automatically.

Discovery fields:

- `coinalyze_symbol`, `exchange`, `exchange_code`, `symbol_on_exchange`, `base_asset`,
  `quote_asset`, `margined`, `is_perpetual`, `expire_at`,
  `oi_lq_vol_denominated_in`;
- every `has_*_data` flag returned by Coinalyze;
- `selected`, `selection_policy`, and `selection_reason`.

## API datasets

Only these endpoints are in scope:

| dataset | endpoint | USD conversion | normalized value |
|---|---|---:|---|
| `open_interest` | `/open-interest-history` | true | history close `c` -> `oi_usd` |
| `liquidations` | `/liquidation-history` | true | `l` -> `long_liquidations_usd`, `s` -> `short_liquidations_usd` |
| `funding_rate` | `/funding-rate-history` | n/a | history close `c` -> `funding_rate` |
| `predicted_funding_rate` | `/predicted-funding-rate-history` | n/a | history close `c` -> `predicted_funding_rate` |

Backfill intervals are exactly `4hour`, `1hour`, `15min`, and `1min`. The
request starts at Unix epoch and ends at the run's fixed UTC cutoff, allowing
the API to return its maximum retained history without inventing earlier data.
Continuous mode requests only `1min`, starting one minute after the last
persisted timestamp for each dataset/symbol partition (or a bounded bootstrap
window when no partition exists).

Each symbol consumes one rate-limit unit. The client permits at most 40 units
in any rolling 60-second window. HTTP 429 is retried only after the
`Retry-After` delay (or a conservative default if the header is invalid).

## RAW

Root: `DATA_ROOT/raw/coinalyze_derivatives/`.

Every successful or failed HTTP exchange is saved as a new, immutable JSON
envelope. The envelope contains a request ID, UTC collection time, endpoint,
non-secret parameters, HTTP status/headers, and the parsed source payload or
error. API credentials are header-only and never serialized. Files are written
to a temporary path, fsynced, then atomically promoted to a unique final name.

## NORMALIZED

Root: `DATA_ROOT/normalized/coinalyze_derivatives/`.

Parquet partitions are separated by dataset, interval, exchange, and symbol.
They use this explicit schema:

| field | type | nullable | contract |
|---|---|---:|---|
| `timestamp_utc` | timestamp[us, UTC] | no | source `t`, interpreted as Unix seconds |
| `exchange` | string | no | discovery provenance |
| `coinalyze_symbol` | string | no | discovery provenance |
| `symbol_on_exchange` | string | no | discovery provenance |
| `interval` | string | no | Coinalyze interval |
| `source` | string | no | exact API endpoint name |
| `dataset` | string | no | one of the four in-scope datasets |
| `oi_usd` | float64 | yes | never zero-filled |
| `long_liquidations_usd` | float64 | yes | never zero-filled |
| `short_liquidations_usd` | float64 | yes | never zero-filled |
| `funding_rate` | float64 | yes | source decimal value |
| `predicted_funding_rate` | float64 | yes | source decimal value |
| `availability_state` | string | no | `available` or `source_null` |
| `raw_request_id` | string | no | RAW provenance link |
| `collected_at_utc` | timestamp[us, UTC] | no | collector observation time |

The unique key is `(timestamp_utc, exchange, coinalyze_symbol, interval,
source)`. Rewrites are atomic; reruns merge and deduplicate by this key. A real
source zero remains zero. A missing/null field remains null and is marked
`source_null`.

## Coverage and failures

Root: `DATA_ROOT/manifests/coinalyze_derivatives/`.

Coverage is recorded per dataset/symbol/interval with requested bounds, first
and last source timestamp, row count, duplicate count, null-value count,
explicit internal gap ranges, trailing lag/missing-interval count, HTTP/error
state, RAW request ID/path, and normalized partition path. A series whose last
source point is at least one full interval behind the request cutoff is marked
`stale` (combined with internal-gap state where applicable). Empty and failed
endpoints remain explicit coverage entries; they are not materialized as
numeric rows.

## Reproducibility and PA join

Every run manifest records the schema/collector version, run ID, fixed UTC
cutoff, Git commit, dirty-worktree state, CLI configuration, discovery artifact,
and coverage artifact. Future PA joins use UTC event timestamps plus exchange,
symbol, and interval; exchange series remain separate until a later explicitly
specified aggregation stage.
