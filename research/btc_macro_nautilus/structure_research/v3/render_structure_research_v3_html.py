from __future__ import annotations

import argparse
import importlib
import json
import shutil
from html import escape
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd


UTC = "UTC"
PLOTLY_BUNDLE = Path(__file__).resolve().parent / "vendor" / "plotly-2.35.2.min.js"


def ensure_utc(value: object) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        return ts.tz_localize(UTC)
    return ts.tz_convert(UTC)


def load_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path) if path.suffix == ".csv" else pd.read_parquet(path)
    for column in frame.columns:
        if "time" in column or column.endswith("_datetime") or column.endswith("_at"):
            try:
                frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce", format="mixed")
            except Exception:
                pass
    return frame


def to_iso(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return ensure_utc(value).isoformat()


def copy_plotly_bundle(html_dir: Path) -> Path:
    vendor_dir = html_dir / "vendor"
    vendor_dir.mkdir(parents=True, exist_ok=True)
    target = vendor_dir / PLOTLY_BUNDLE.name
    if PLOTLY_BUNDLE.exists():
        shutil.copy2(PLOTLY_BUNDLE, target)
        return target
    try:
        plotly = importlib.import_module("plotly")
        plotly_root = Path(plotly.__file__).resolve().parent
        bundle_candidates = list(plotly_root.rglob("plotly.min.js"))
    except Exception:
        bundle_candidates = []
    if bundle_candidates:
        shutil.copy2(bundle_candidates[0], target)
        return target
    raise RuntimeError("local_plotly_bundle_not_found")
    return target


def rows_to_html_table(title: str, rows: Iterable[tuple[str, object]]) -> str:
    body = "".join(
        f"<tr><th>{escape(str(key))}</th><td>{escape('' if pd.isna(value) else str(value))}</td></tr>"
        for key, value in rows
    )
    return f"""
    <section class="panel">
      <h2>{escape(title)}</h2>
      <table class="meta">{body}</table>
    </section>
    """


def make_line_trace(name: str, x: list[object], y: list[object], color: str, yaxis: str = "y", width: float = 2.0, dash: str = "solid", visible: bool = True, meta: Optional[dict] = None) -> dict:
    return {
        "type": "scatter",
        "mode": "lines",
        "name": name,
        "x": x,
        "y": y,
        "line": {"color": color, "width": width, "dash": dash},
        "yaxis": yaxis,
        "hovertemplate": "%{x}<br>%{y}<extra>" + escape(name) + "</extra>",
        "visible": visible,
        "meta": meta or {},
    }


def make_marker_trace(name: str, x: list[object], y: list[object], color: str, symbol: str, yaxis: str = "y") -> dict:
    return {
        "type": "scatter",
        "mode": "markers",
        "name": name,
        "x": x,
        "y": y,
        "yaxis": yaxis,
        "marker": {"color": color, "symbol": symbol, "size": 9},
        "hovertemplate": "%{x}<br>%{y}<extra>" + escape(name) + "</extra>",
    }


def make_candlestick_trace(bars: pd.DataFrame) -> dict:
    return {
        "type": "candlestick",
        "name": "BTCUSDT",
        "x": bars["open_datetime"].apply(to_iso).tolist(),
        "open": bars["open"].astype(float).tolist(),
        "high": bars["high"].astype(float).tolist(),
        "low": bars["low"].astype(float).tolist(),
        "close": bars["close"].astype(float).tolist(),
        "increasing": {"line": {"color": "#10b981"}},
        "decreasing": {"line": {"color": "#ef4444"}},
        "yaxis": "y",
        "hovertemplate": "open=%{open}<br>high=%{high}<br>low=%{low}<br>close=%{close}<extra>BTCUSDT</extra>",
    }


def dynamic_boundary_traces(dynamic_candidates: pd.DataFrame) -> list[dict]:
    traces: list[dict] = []
    if dynamic_candidates.empty:
        return traces
    palette = {"A": "#2563eb", "B": "#7c3aed", "C": "#ea580c"}
    for method in ["A", "B", "C"]:
        for window in ["18", "42", "84"]:
            subset = dynamic_candidates[
                (dynamic_candidates["method"].astype(str) == method)
                & (dynamic_candidates["window_size_bars"].astype(str) == window)
            ].sort_values("candidate_available_at")
            if subset.empty:
                continue
            upper_x: list[object] = []
            upper_y: list[object] = []
            lower_x: list[object] = []
            lower_y: list[object] = []
            mid_x: list[object] = []
            midpoint_y: list[object] = []
            for row in subset.itertuples(index=False):
                history_start = to_iso(getattr(row, "history_start_time", getattr(row, "candidate_available_at")))
                history_end = to_iso(getattr(row, "history_end_time", getattr(row, "candidate_available_at")))
                ts = to_iso(row.candidate_available_at)
                upper_x.extend([history_start, history_end, ts, None])
                lower_x.extend([history_start, history_end, ts, None])
                mid_x.extend([history_start, history_end, ts, None])
                upper_y.extend([
                    float(getattr(row, "upper_at_history_start", row.upper_at_history_end)),
                    float(row.upper_at_history_end),
                    float(row.upper_projected_current),
                    None,
                ])
                lower_y.extend([
                    float(getattr(row, "lower_at_history_start", row.lower_at_history_end)),
                    float(row.lower_at_history_end),
                    float(row.lower_projected_current),
                    None,
                ])
                midpoint_y.extend([
                    float(getattr(row, "mid_at_history_start", (float(getattr(row, "upper_at_history_start", row.upper_at_history_end)) + float(getattr(row, "lower_at_history_start", row.lower_at_history_end))) / 2.0)),
                    float(getattr(row, "mid_at_history_end", (float(row.upper_at_history_end) + float(row.lower_at_history_end)) / 2.0)),
                    float(getattr(row, "mid_projected_current", (float(row.upper_projected_current) + float(row.lower_projected_current)) / 2.0)),
                    None,
                ])
            color = palette[method]
            meta = {"method": method, "window": window, "trace_group": "dynamic_range"}
            traces.append(make_line_trace(f"range_{method}_{window}_upper", upper_x, upper_y, color=color, width=1.5, visible=window == "18", meta=meta))
            traces.append(make_line_trace(f"range_{method}_{window}_lower", lower_x, lower_y, color=color, width=1.5, visible=window == "18", meta=meta))
            traces.append(make_line_trace(f"range_{method}_{window}_mid", mid_x, midpoint_y, color=color, width=1.0, dash="dot", visible=window == "18", meta=meta))
    return traces


def subset_timeframe(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, time_columns: list[str]) -> pd.DataFrame:
    if frame.empty:
        return frame
    for column in time_columns:
        if column in frame.columns:
            series = pd.to_datetime(frame[column], utc=True, errors="coerce", format="mixed")
            mask = (series >= start) & (series <= end)
            filtered = frame.loc[mask].copy()
            if not filtered.empty:
                return filtered
    return frame.iloc[0:0].copy()


def canonical_leg_trace(canonical_legs: pd.DataFrame) -> list[dict]:
    traces: list[dict] = []
    if canonical_legs.empty:
        return traces
    bull_x: list[object] = []
    bull_y: list[object] = []
    bear_x: list[object] = []
    bear_y: list[object] = []
    for leg in canonical_legs.itertuples(index=False):
        target_x = bull_x if str(leg.direction) == "up" else bear_x
        target_y = bull_y if str(leg.direction) == "up" else bear_y
        target_x.extend([to_iso(leg.start_time), to_iso(leg.end_time), None])
        target_y.extend([float(leg.start_price), float(leg.end_price), None])
    if bull_x:
        traces.append(make_line_trace("canonical_bull_legs", bull_x, bull_y, color="#34d399", width=4.0))
    if bear_x:
        traces.append(make_line_trace("canonical_bear_legs", bear_x, bear_y, color="#fb7185", width=4.0))
    return traces


def excursion_traces(excursions: pd.DataFrame) -> list[dict]:
    traces: list[dict] = []
    if excursions.empty:
        return traces
    wick = excursions[excursions["wick_outside"] == True]
    close = excursions[excursions["close_outside"] == True]
    if not wick.empty:
        traces.append(
            make_marker_trace(
                "wick_excursions",
                wick["observation_time"].apply(to_iso).tolist(),
                pd.Series([0.0] * len(wick)).tolist(),
                color="#f59e0b",
                symbol="triangle-up",
                yaxis="y3",
            )
        )
    if not close.empty:
        traces.append(
            make_marker_trace(
                "close_excursions",
                close["observation_time"].apply(to_iso).tolist(),
                pd.Series([1.0] * len(close)).tolist(),
                color="#111827",
                symbol="diamond",
                yaxis="y3",
            )
        )
    return traces


def fibtime_shapes(fibtime_events: pd.DataFrame) -> list[dict]:
    shapes: list[dict] = []
    if fibtime_events.empty:
        return shapes
    for row in fibtime_events.itertuples(index=False):
        color = "#2563eb" if str(row.event_type) == "fibtime_confirmed" else "#94a3b8"
        shapes.append(
            {
                "type": "line",
                "xref": "x",
                "yref": "paper",
                "x0": to_iso(row.event_time),
                "x1": to_iso(row.event_time),
                "y0": 0.42,
                "y1": 1.0,
                "line": {"color": color, "width": 1, "dash": "dot"},
            }
        )
    return shapes


def base_layout(title: str) -> dict:
    return {
        "title": {"text": title, "x": 0.03},
        "dragmode": "pan",
        "hovermode": "x unified",
        "template": "plotly_white",
        "margin": {"l": 60, "r": 30, "t": 80, "b": 40},
        "legend": {"orientation": "h", "y": 1.08, "x": 0.01},
        "xaxis": {
            "domain": [0.0, 1.0],
            "anchor": "y",
            "rangeslider": {"visible": True},
            "rangeselector": {
                "buttons": [
                    {"count": 1, "label": "1y", "step": "year", "stepmode": "backward"},
                    {"count": 3, "label": "3y", "step": "year", "stepmode": "backward"},
                    {"count": 5, "label": "5y", "step": "year", "stepmode": "backward"},
                    {"step": "all", "label": "All"},
                ]
            },
        },
        "xaxis2": {"domain": [0.0, 1.0], "anchor": "y2", "matches": "x", "showticklabels": False},
        "xaxis3": {"domain": [0.0, 1.0], "anchor": "y3", "matches": "x", "showticklabels": False},
        "xaxis4": {"domain": [0.0, 1.0], "anchor": "y4", "matches": "x"},
        "yaxis": {"domain": [0.45, 1.0], "title": "Price", "fixedrange": False},
        "yaxis2": {"domain": [0.26, 0.40], "title": "Volume", "fixedrange": False},
        "yaxis3": {"domain": [0.15, 0.23], "title": "ATR / Markers", "fixedrange": False},
        "yaxis4": {"domain": [0.0, 0.11], "title": "Speed / Efficiency", "fixedrange": False},
    }


def overview_figure(
    market_4h: pd.DataFrame,
    canonical_legs: pd.DataFrame,
    dynamic_candidates: pd.DataFrame,
    excursions: pd.DataFrame,
    fibtime_events: pd.DataFrame,
    causal_4h: pd.DataFrame,
) -> dict:
    traces: list[dict] = []
    if not market_4h.empty:
        traces.append(make_candlestick_trace(market_4h))
        traces.extend(canonical_leg_trace(canonical_legs))
        traces.append(
            {
                "type": "bar",
                "name": "volume",
                "x": market_4h["open_datetime"].apply(to_iso).tolist(),
                "y": market_4h["volume"].fillna(0.0).astype(float).tolist() if "volume" in market_4h.columns else [],
                "yaxis": "y2",
                "marker": {"color": "#94a3b8"},
            }
        )
        if "atr14_wilder" in market_4h.columns:
            traces.append(make_line_trace("atr14_wilder", market_4h["open_datetime"].apply(to_iso).tolist(), market_4h["atr14_wilder"].astype(float).tolist(), color="#f59e0b", yaxis="y3"))
    traces.extend(dynamic_boundary_traces(dynamic_candidates))
    traces.extend(excursion_traces(excursions))
    if not causal_4h.empty:
        speed = causal_4h[causal_4h["window_size_bars"] == 18].sort_values("open_datetime")
        if not speed.empty:
            traces.append(make_line_trace("speed_pct_per_day_signed", speed["open_datetime"].apply(to_iso).tolist(), speed["speed_pct_per_day_signed"].astype(float).tolist(), color="#0f766e", yaxis="y4"))
            traces.append(make_line_trace("close_path_efficiency", speed["open_datetime"].apply(to_iso).tolist(), speed["close_path_efficiency"].astype(float).tolist(), color="#7c3aed", yaxis="y4"))
    layout = base_layout("BTCUSDT structure research v3 overview")
    layout["shapes"] = fibtime_shapes(fibtime_events)
    return {"data": traces, "layout": layout}


def subset_around_leg(leg_row: pd.Series, bars: pd.DataFrame, padding_days: int) -> pd.DataFrame:
    start = ensure_utc(leg_row["start_time"]) - pd.Timedelta(days=padding_days)
    end = ensure_utc(leg_row["end_time"]) + pd.Timedelta(days=padding_days)
    return bars[(bars["open_datetime"] >= start) & (bars["open_datetime"] <= end)].copy()


def leg_figure(
    leg_row: pd.Series,
    bars: pd.DataFrame,
    canonical_legs: pd.DataFrame,
    dynamic_candidates: pd.DataFrame,
    excursions: pd.DataFrame,
    causal_4h: pd.DataFrame,
) -> dict:
    traces: list[dict] = []
    traces.append(make_candlestick_trace(bars))
    local_legs = canonical_legs[
        (pd.to_datetime(canonical_legs["start_time"], utc=True) >= ensure_utc(leg_row["start_time"]) - pd.Timedelta(days=10))
        & (pd.to_datetime(canonical_legs["start_time"], utc=True) <= ensure_utc(leg_row["end_time"]) + pd.Timedelta(days=10))
    ].copy()
    traces.extend(canonical_leg_trace(local_legs))
    traces.append(
        {
            "type": "bar",
            "name": "volume",
            "x": bars["open_datetime"].apply(to_iso).tolist(),
            "y": bars["volume"].fillna(0.0).astype(float).tolist() if "volume" in bars.columns else [],
            "yaxis": "y2",
            "marker": {"color": "#94a3b8"},
        }
    )
    if "atr14_wilder" in bars.columns:
        traces.append(make_line_trace("atr14_wilder", bars["open_datetime"].apply(to_iso).tolist(), bars["atr14_wilder"].astype(float).tolist(), color="#f59e0b", yaxis="y3"))
    traces.extend(dynamic_boundary_traces(dynamic_candidates))
    traces.extend(excursion_traces(excursions))
    if not causal_4h.empty:
        traces.append(make_line_trace("speed_pct_per_day_signed", causal_4h["open_datetime"].apply(to_iso).tolist(), causal_4h["speed_pct_per_day_signed"].astype(float).tolist(), color="#0f766e", yaxis="y4"))
        traces.append(make_line_trace("close_path_efficiency", causal_4h["open_datetime"].apply(to_iso).tolist(), causal_4h["close_path_efficiency"].astype(float).tolist(), color="#7c3aed", yaxis="y4"))
    layout = base_layout(f"Leg {leg_row['canonical_leg_id']}")
    return {"data": traces, "layout": layout}


def html_shell(title: str, subtitle: str, figure: dict, tables: list[str], links: list[tuple[str, str]], bundle_rel: str, selector_html: str = "") -> str:
    nav = "".join(f'<a class="nav-link" href="{escape(href)}">{escape(label)}</a>' for label, href in links)
    fig_json = json.dumps(figure, ensure_ascii=False)
    tables_html = "".join(tables)
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>{escape(title)}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f8fafc;
      color: #0f172a;
    }}
    .wrap {{
      max-width: 1600px;
      margin: 0 auto;
      padding: 20px;
    }}
    .panel {{
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 18px;
      padding: 18px 20px;
      margin-bottom: 16px;
      box-shadow: 0 18px 38px rgba(15, 23, 42, 0.06);
    }}
    .nav {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 14px;
    }}
    .nav-link {{
      text-decoration: none;
      color: #0f172a;
      border: 1px solid #cbd5e1;
      background: #f8fafc;
      padding: 9px 12px;
      border-radius: 12px;
    }}
    .selector {{
      margin-top: 12px;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
    }}
    .selector select {{
      border-radius: 10px;
      padding: 9px 12px;
      border: 1px solid #cbd5e1;
      background: #ffffff;
    }}
    #chart {{
      min-height: 82vh;
    }}
    .meta {{
      width: 100%;
      border-collapse: collapse;
    }}
    .meta th, .meta td {{
      padding: 8px 10px;
      border-top: 1px solid #e2e8f0;
      text-align: left;
      vertical-align: top;
    }}
    .meta th {{
      width: 280px;
      color: #475569;
      font-weight: 600;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="panel">
      <h1>{escape(title)}</h1>
      <p>{escape(subtitle)}</p>
      <div class="nav">{nav}</div>
      <div class="selector">{selector_html}</div>
    </section>
    <section class="panel">
      <div id="chart"></div>
    </section>
    {tables_html}
  </div>
  <script src="{escape(bundle_rel)}"></script>
  <script>
    const figure = {fig_json};
    const chart = document.getElementById("chart");
    const methodControl = document.getElementById("method-filter");
    const windowControl = document.getElementById("window-filter");
    let yLock = false;
    function traceVisibleForFilters(trace, methodValue, windowValue) {{
      const meta = trace.meta || {{}};
      if (!meta.trace_group || meta.trace_group !== "dynamic_range") return true;
      const methodOk = methodValue === "All" || meta.method === methodValue;
      const windowOk = windowValue === "All" || String(meta.window) === String(windowValue);
      return methodOk && windowOk;
    }}
    function applyDynamicFilters(gd) {{
      const methodValue = methodControl ? methodControl.value : "All";
      const windowValue = windowControl ? windowControl.value : "All";
      const update = gd.data.map((trace) => traceVisibleForFilters(trace, methodValue, windowValue));
      Plotly.restyle(gd, {{visible: update}});
    }}
    function autoRangeVisibleY(gd) {{
      if (yLock) return;
      const trace = gd.data.find((item) => item.type === "candlestick");
      if (!trace || !trace.x || !trace.high || !trace.low) return;
      const range = gd.layout.xaxis.range;
      let highs = [];
      let lows = [];
      for (let i = 0; i < trace.x.length; i += 1) {{
        const x = new Date(trace.x[i]).getTime();
        const inRange = !range || (x >= new Date(range[0]).getTime() && x <= new Date(range[1]).getTime());
        if (inRange) {{
          highs.push(trace.high[i]);
          lows.push(trace.low[i]);
        }}
      }}
      if (!highs.length || !lows.length) return;
      const pad = Math.max((Math.max(...highs) - Math.min(...lows)) * 0.06, 1);
      yLock = true;
      Plotly.relayout(gd, {{
        "yaxis.range": [Math.min(...lows) - pad, Math.max(...highs) + pad]
      }}).finally(() => {{ yLock = false; }});
    }}
    Plotly.newPlot(chart, figure.data, figure.layout, {{
      scrollZoom: true,
      displayModeBar: true,
      responsive: true,
      dragmode: "pan",
      hovermode: "x unified"
    }}).then((gd) => {{
      applyDynamicFilters(gd);
      autoRangeVisibleY(gd);
      gd.on("plotly_relayout", (event) => {{
        if (event["xaxis.range[0]"] || event["xaxis.autorange"]) autoRangeVisibleY(gd);
      }});
      if (methodControl) methodControl.addEventListener("change", () => applyDynamicFilters(gd));
      if (windowControl) windowControl.addEventListener("change", () => applyDynamicFilters(gd));
    }});
  </script>
</body>
</html>
"""


def selector_block(label: str, options: list[tuple[str, str]]) -> str:
    if not options:
        return ""
    option_html = "".join(f'<option value="{escape(href)}">{escape(name)}</option>' for name, href in options)
    return f"""
    <label>{escape(label)}
      <select onchange="if (this.value) window.location.href=this.value;">
        <option value="">Открыть…</option>
        {option_html}
      </select>
    </label>
    """


def filter_controls_block() -> str:
    return """
    <label>Method
      <select id="method-filter">
        <option value="All">All</option>
        <option value="A">A</option>
        <option value="B">B</option>
        <option value="C">C</option>
      </select>
    </label>
    <label>Window
      <select id="window-filter">
        <option value="All">All</option>
        <option value="18">18</option>
        <option value="42">42</option>
        <option value="84">84</option>
      </select>
    </label>
    """


def write_html(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=["smoke", "full"], required=True)
    args = parser.parse_args()

    dataset_dir = args.dataset_dir
    summary_path = dataset_dir / "structure_research_summary_v3.json"
    qa_path = dataset_dir / "structure_research_qa_v3.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    qa = json.loads(qa_path.read_text(encoding="utf-8")) if qa_path.exists() else {}
    allowed_statuses = {"success", "complete_with_known_coverage_limits"}
    if summary.get("status") not in allowed_statuses or qa.get("critical_failures"):
        raise RuntimeError("dataset_qa_not_green_html_not_created")

    html_dir = dataset_dir / "html"
    html_dir.mkdir(parents=True, exist_ok=True)
    bundle_target = copy_plotly_bundle(html_dir)

    market_4h = load_table(dataset_dir / "market_bars_4h.parquet")
    market_15m = load_table(dataset_dir / "market_bars_15m.parquet")
    canonical_legs = load_table(dataset_dir / "structure_canonical_legs.csv")
    dynamic_candidates = load_table(dataset_dir / "dynamic_range_candidates_4h_causal.parquet")
    excursions = load_table(dataset_dir / "dynamic_range_excursions_4h.parquet")
    fibtime_events = load_table(dataset_dir / "fibtime_events_v3.csv")
    smoke_cases = load_table(dataset_dir / "smoke_case_candidates.csv")
    coverage = load_table(dataset_dir / "coverage_by_leg_timeframe.csv")
    causal_4h = load_table(dataset_dir / "market_features_rolling_4h_causal.parquet")
    static_features = load_table(dataset_dir / "structure_leg_features_static.csv")
    decision_parent = load_table(dataset_dir / "decision_parent_reference_candidates.csv")

    overview = overview_figure(market_4h, canonical_legs, dynamic_candidates, excursions, fibtime_events, causal_4h)
    overview_tables = [
        rows_to_html_table(
            "Summary",
            [
                ("status", summary.get("status", "")),
                ("canonical_leg_count", summary.get("canonical_leg_count", "")),
                ("dynamic_range_candidate_count", summary.get("dynamic_range_candidate_count", "")),
                ("excursion_observation_count", summary.get("excursion_observation_count", "")),
                ("retrospective_15m_rows", summary.get("retrospective_15m_rows", "")),
            ],
        ),
        rows_to_html_table(
            "QA",
            [
                ("critical_failures", ", ".join(qa.get("critical_failures", []))),
                ("warnings", ", ".join(qa.get("warnings", []))),
            ],
        ),
    ]

    smoke_options = [(str(row["case_id"]), f"smoke_cases/{row['case_id']}.html") for _, row in smoke_cases.iterrows()] if not smoke_cases.empty else []
    leg_options = [(str(row["canonical_leg_id"]), f"legs/{row['canonical_leg_id']}.html") for _, row in canonical_legs.iterrows()]
    selector_html = selector_block("Smoke case", smoke_options) + selector_block("Leg", leg_options) + filter_controls_block()
    overview_html = html_shell(
        "BTCUSDT structure research v3",
        "Основной обзор на 4H. Масштабирование, панорамирование и ручной просмотр доступны через Plotly modebar и мышь.",
        overview,
        overview_tables,
        [("Index", "index.html")],
        bundle_target.relative_to(html_dir).as_posix(),
        selector_html=selector_html,
    )
    write_html(html_dir / "overview_4h.html", overview_html)

    for _, case_row in smoke_cases.iterrows():
        case_id = str(case_row["case_id"])
        case_bars = market_4h.copy()
        case_legs = canonical_legs.copy()
        case_candidates = dynamic_candidates.copy()
        case_excursions = excursions.copy()
        case_causal = causal_4h.copy()
        case_fibtime = fibtime_events.copy()
        leg_id = str(case_row.get("canonical_leg_id", "") or "")
        range_candidate_id = str(case_row.get("range_candidate_id", "") or "")
        if leg_id and not canonical_legs.empty:
            leg_row = canonical_legs[canonical_legs["canonical_leg_id"].astype(str) == leg_id].iloc[0]
            local_start = ensure_utc(leg_row["start_time"]) - pd.Timedelta(days=14)
            local_end = ensure_utc(leg_row["end_time"]) + pd.Timedelta(days=14)
        elif range_candidate_id and not dynamic_candidates.empty:
            candidate_row = dynamic_candidates[dynamic_candidates["range_candidate_id"].astype(str) == range_candidate_id].iloc[0]
            center = ensure_utc(candidate_row["candidate_available_at"])
            local_start = center - pd.Timedelta(days=10)
            local_end = center + pd.Timedelta(days=10)
        else:
            local_start = market_4h["open_datetime"].min() if not market_4h.empty else pd.Timestamp("2026-01-01T00:00:00Z")
            local_end = market_4h["open_datetime"].max() if not market_4h.empty else pd.Timestamp("2026-01-10T00:00:00Z")
        case_bars = subset_timeframe(market_4h, local_start, local_end, ["open_datetime"])
        case_legs = subset_timeframe(canonical_legs, local_start, local_end, ["start_time", "end_time"])
        case_candidates = subset_timeframe(dynamic_candidates, local_start, local_end, ["candidate_available_at", "history_end_time"])
        case_excursions = subset_timeframe(excursions, local_start, local_end, ["observation_time"])
        case_causal = subset_timeframe(causal_4h, local_start, local_end, ["open_datetime"])
        case_fibtime = subset_timeframe(fibtime_events, local_start, local_end, ["event_time", "available_at_time"])
        case_figure = overview_figure(case_bars, case_legs, case_candidates, case_excursions, case_fibtime, case_causal)
        case_html = html_shell(
            f"Smoke case {case_id}",
            "Страница отдельного smoke-case без текстовых подписей поверх свечей.",
            case_figure,
            [rows_to_html_table("Case metadata", [(key, case_row.get(key, "")) for key in case_row.index])],
            [("Index", "../index.html"), ("Overview 4H", "../overview_4h.html")],
            "../" + bundle_target.relative_to(html_dir).as_posix(),
            selector_html=selector_block("Другой smoke case", [(name, f"{name}.html") for name, _ in smoke_options]) + selector_block("Leg", [(name, f"../legs/{name}.html") for name, _ in leg_options]) + filter_controls_block(),
        )
        write_html(html_dir / "smoke_cases" / f"{case_id}.html", case_html)

    static_by_leg = static_features.set_index("canonical_leg_id").to_dict("index") if not static_features.empty else {}
    for _, leg_row in canonical_legs.iterrows():
        leg_id = str(leg_row["canonical_leg_id"])
        local_start = ensure_utc(leg_row["start_time"]) - pd.Timedelta(days=14)
        local_end = ensure_utc(leg_row["end_time"]) + pd.Timedelta(days=14)
        bars = subset_timeframe(market_15m, local_start, local_end, ["open_datetime"]) if not market_15m.empty else pd.DataFrame()
        if bars.empty:
            bars = subset_timeframe(market_4h, local_start, local_end, ["open_datetime"])
        leg_dynamic = subset_timeframe(dynamic_candidates, local_start, local_end, ["candidate_available_at", "history_end_time"])
        leg_excursions = subset_timeframe(excursions, local_start, local_end, ["observation_time"])
        leg_causal = subset_timeframe(causal_4h, local_start, local_end, ["open_datetime"]) if not causal_4h.empty else pd.DataFrame()
        figure = leg_figure(leg_row, bars, canonical_legs, leg_dynamic, leg_excursions, leg_causal)
        leg_tables = [
            rows_to_html_table("Leg metadata", list(leg_row.items())),
            rows_to_html_table("Static metrics", list(static_by_leg.get(leg_id, {}).items())[:16]),
        ]
        if not decision_parent.empty:
            related = decision_parent[decision_parent["current_leg_id"].astype(str) == leg_id].head(12)
            if not related.empty:
                first_related = related.iloc[0]
                leg_tables.append(rows_to_html_table("Decision support sample", [(key, first_related.get(key, "")) for key in related.columns[:12]]))
        leg_html = html_shell(
            f"Leg {leg_id}",
            "Детальная страница ноги: если доступны 15m, они используются вместо 4H.",
            figure,
            leg_tables,
            [("Index", "../index.html"), ("Overview 4H", "../overview_4h.html")],
            "../" + bundle_target.relative_to(html_dir).as_posix(),
            selector_html=selector_block("Другой leg", [(name, f"{name}.html") for name, _ in leg_options]) + selector_block("Smoke case", [(name, f"../smoke_cases/{name}.html") for name, _ in smoke_options]) + filter_controls_block(),
        )
        write_html(html_dir / "legs" / f"{leg_id}.html", leg_html)

    smoke_index = """<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><title>Smoke cases</title></head><body><h1>Smoke cases</h1><ul>""" + "".join(
        f'<li><a href="{escape(str(row["case_id"]))}.html">{escape(str(row["case_id"]))}</a></li>' for _, row in smoke_cases.iterrows()
    ) + """</ul><p><a href="../index.html">Назад</a></p></body></html>"""
    write_html(html_dir / "smoke_cases" / "index.html", smoke_index)

    legs_index = """<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><title>Leg pages</title></head><body><h1>Leg pages</h1><ul>""" + "".join(
        f'<li><a href="{escape(str(row["canonical_leg_id"]))}.html">{escape(str(row["canonical_leg_id"]))}</a></li>' for _, row in canonical_legs.iterrows()
    ) + """</ul><p><a href="../index.html">Назад</a></p></body></html>"""
    write_html(html_dir / "legs" / "index.html", legs_index)

    index_rows = [
        ("4H bars", len(market_4h)),
        ("15M bars", len(market_15m)),
        ("canonical legs", len(canonical_legs)),
        ("coverage rows", len(coverage)),
    ]
    index_html = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><title>Structure research v3</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{{font-family:ui-sans-serif,system-ui,sans-serif;background:#f8fafc;color:#0f172a;margin:0}}.wrap{{max-width:980px;margin:0 auto;padding:24px}}.panel{{background:#fff;border:1px solid #e2e8f0;border-radius:18px;padding:18px 20px;margin-bottom:16px}}</style></head>
<body><div class="wrap">
<section class="panel"><h1>Structure research v3</h1><p>Навигация по офлайн-Plotly страницам.</p>
<p><a href="overview_4h.html">Overview 4H</a></p>
<p><a href="smoke_cases/index.html">Smoke cases</a></p>
<p><a href="legs/index.html">Leg pages</a></p></section>
{rows_to_html_table("Coverage", index_rows)}
</div></body></html>"""
    write_html(html_dir / "index.html", index_html)


if __name__ == "__main__":
    main()
