# Official Binance BTCUSDT USD-M funding contracts

Schema version: `binance-usdm-funding-v1`.

The only source is `GET https://fapi.binance.com/fapi/v1/fundingRate` with
`symbol=BTCUSDT`. The requested start and end are read from
`strict_futures_1m_manifest.json`; they are not inferred from the current date.

Every successful response body is stored byte-for-byte as an immutable raw
page. A page is checkpointed immediately after its atomic write. Pagination
continues at one millisecond after the last event actually returned. An empty
response for the remaining bounded window is retained as the proof that the
collector reached the requested end.

The normalized CSV has exactly these columns:

- `symbol`
- `funding_time_ms`
- `funding_time_utc`
- `funding_rate`
- `mark_price`

The source JSON spellings of `fundingRate` and `markPrice` are written directly
to CSV as text. No floating-point conversion or rounding is permitted.
Duplicate timestamps are excluded from normalized output and reported. No
event is interpolated or synthesized.

An unusual interval is defined for review as any consecutive delta different
from the modal observed delta. This flag does not assert that data is missing;
the manifest retains every interval and surrounding source events.
