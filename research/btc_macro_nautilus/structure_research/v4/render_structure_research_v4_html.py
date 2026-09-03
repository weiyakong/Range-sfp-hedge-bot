from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd

from structure_research_v4.io import ensure_directory, load_table


VENDOR_SOURCE = Path("/Users/yeshevika/Documents/Codex/2026-07-17/new-chat/work/vendor/plotly-2.35.2.min.js")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", required=True)
    return parser.parse_args()


def _page(title: str, figure_payload: dict, metadata_html: str) -> str:
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>{title}</title>
  <script src="../vendor/plotly-2.35.2.min.js"></script>
  <style>
    body {{ font-family: sans-serif; margin: 0; background: #f6f6f1; color: #1f2937; }}
    .wrap {{ padding: 16px; }}
    #chart {{ width: 100%; height: 85vh; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 6px; text-align: left; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>{title}</h1>
    <div id="chart"></div>
    {metadata_html}
  </div>
  <script>
    const payload = {json.dumps(figure_payload)};
    Plotly.newPlot('chart', payload.data, payload.layout, {{
      scrollZoom: true,
      dragmode: 'pan',
      displayModeBar: true,
      responsive: true
    }});
  </script>
</body>
</html>"""


def _candles(frame: pd.DataFrame) -> dict:
    return {
        "type": "candlestick",
        "x": frame["open_datetime"].astype(str).tolist(),
        "open": frame["open"].astype(float).tolist(),
        "high": frame["high"].astype(float).tolist(),
        "low": frame["low"].astype(float).tolist(),
        "close": frame["close"].astype(float).tolist(),
        "name": "BTCUSDT",
    }


def main() -> int:
    args = parse_args()
    dataset_dir = Path(args.dataset_dir)
    html_dir = ensure_directory(dataset_dir / "html")
    ensure_directory(html_dir / "smoke_cases")
    ensure_directory(html_dir / "legs")
    ensure_directory(html_dir / "vendor")
    shutil.copy2(VENDOR_SOURCE, html_dir / "vendor" / VENDOR_SOURCE.name)

    bars = load_table(dataset_dir / "market_bars_4h.parquet").tail(200)
    candidates = load_table(dataset_dir / "dynamic_range_candidates_4h_causal.parquet").tail(60)
    legs = load_table(dataset_dir / "structure_canonical_legs.csv").tail(20)
    fibtime = load_table(dataset_dir / "fibtime_events_v4.csv").tail(30)

    traces = [_candles(bars)]
    for method in ["A", "B", "C"]:
        chunk = candidates[candidates["method"] == method].tail(10)
        if chunk.empty:
            continue
        traces.append(
            {
                "type": "scatter",
                "mode": "lines",
                "x": chunk["candidate_available_at"].astype(str).tolist(),
                "y": chunk["upper_projected_current"].astype(float).tolist(),
                "name": f"{method} upper",
            }
        )
        traces.append(
            {
                "type": "scatter",
                "mode": "lines",
                "x": chunk["candidate_available_at"].astype(str).tolist(),
                "y": chunk["lower_projected_current"].astype(float).tolist(),
                "name": f"{method} lower",
            }
        )
    for _, event in fibtime.iterrows():
        if pd.isna(event["available_at_time"]):
            continue
        traces.append(
            {
                "type": "scatter",
                "mode": "markers",
                "x": [str(event["available_at_time"])],
                "y": [float(bars["close"].iloc[-1])],
                "name": str(event["event_type"]),
            }
        )
    layout = {"hovermode": "x unified"}
    overview = _page("Overview 4H", {"data": traces, "layout": layout}, legs.to_html(index=False))
    (html_dir / "overview_4h.html").write_text(overview, encoding="utf-8")
    (html_dir / "index.html").write_text('<html><body><a href="overview_4h.html">Overview 4H</a></body></html>', encoding="utf-8")
    (html_dir / "smoke_cases" / "index.html").write_text('<html><body><a href="../overview_4h.html">Back</a></body></html>', encoding="utf-8")
    for leg in legs.to_dict(orient="records"):
        subset = bars[(bars["open_datetime"] >= leg["start_time"]) & (bars["open_datetime"] <= leg["end_time"])]
        page = _page(
            f"Leg {leg['canonical_leg_id']}",
            {"data": [_candles(subset if not subset.empty else bars.tail(20))], "layout": layout},
            pd.DataFrame([leg]).to_html(index=False),
        )
        (html_dir / "legs" / f"{leg['canonical_leg_id']}.html").write_text(page, encoding="utf-8")
    (html_dir / "legs" / "index.html").write_text(
        "<html><body>" + "".join(f'<a href="{leg_id}.html">{leg_id}</a><br/>' for leg_id in legs["canonical_leg_id"].tolist()) + "</body></html>",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
