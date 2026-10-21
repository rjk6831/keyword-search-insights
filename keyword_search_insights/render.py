"""Dependency-free terminal and machine-readable rendering."""

from __future__ import annotations

import csv
import html
import io
import json
from datetime import date
from typing import Sequence

from .core import Candle, Observation, serialize_rows


def render_table(candles: Sequence[Candle]) -> str:
    header = "bucket       open   high    low  close  n  observed             flags"
    rule = "-" * len(header)
    lines = [header, rule]
    for candle in candles:
        flags = []
        if candle.edge_bucket:
            flags.append("edge")
        if candle.source_partial:
            flags.append("source-partial")
        if candle.observations == 1:
            flags.append("single-point")
        lines.append(
            f"{candle.bucket_start:%Y-%m-%d} "
            f"{candle.open:6.1f} {candle.high:6.1f} {candle.low:6.1f} "
            f"{candle.close:6.1f} {candle.observations:2d} "
            f"{candle.observed_start:%Y-%m-%d}..{candle.observed_end:%Y-%m-%d} "
            f"{','.join(flags) or '-'}"
        )
    return "\n".join(lines)


def render_chart(candles: Sequence[Candle], height: int = 12) -> str:
    if not candles:
        return "(no candles)"
    low = min(item.low for item in candles)
    high = max(item.high for item in candles)
    span = high - low

    def level(value: float) -> int:
        if span == 0:
            return height // 2
        return round((value - low) * (height - 1) / span)

    grid = [[" " for _ in candles] for _ in range(height)]
    for column, candle in enumerate(candles):
        low_level, high_level = level(candle.low), level(candle.high)
        open_level, close_level = level(candle.open), level(candle.close)
        for row in range(low_level, high_level + 1):
            grid[height - 1 - row][column] = "│"
        body_low, body_high = sorted((open_level, close_level))
        symbol = "▲" if candle.close > candle.open else "▼" if candle.close < candle.open else "─"
        for row in range(body_low, body_high + 1):
            grid[height - 1 - row][column] = symbol

    lines = []
    for index, row in enumerate(grid):
        value = high - (span * index / (height - 1)) if height > 1 else high
        lines.append(f"{value:6.1f}  " + " ".join(row))
    lines.append("        " + " ".join("┬" for _ in candles))
    lines.append("        " + " ".join(str((i + 1) % 10) for i in range(len(candles))))
    lines.append("Legend: ▲ close>open  ▼ close<open  ─ unchanged; column numbers map to table rows")
    return "\n".join(lines)


def render_json(candles: Sequence[Candle]) -> str:
    return json.dumps(serialize_rows(candles), indent=2)


def render_csv(candles: Sequence[Candle]) -> str:
    rows = serialize_rows(candles)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0]) if rows else [])
    if rows:
        writer.writeheader()
        writer.writerows(rows)
    return output.getvalue().rstrip()


def render_html_report(
    term: str,
    profile_label: str,
    candles: Sequence[Candle],
    observations: Sequence[Observation],
    window_start: date,
    window_end: date,
    source_format: str,
    source_column: str,
    warnings: Sequence[str],
) -> str:
    """Return a self-contained HTML report with an inline SVG chart."""
    width, height = 960, 500
    left, right, top, bottom = 58, 22, 28, 54
    plot_width = width - left - right
    plot_height = height - top - bottom
    day_span = max(1, (window_end - window_start).days)

    def x_for(day: date) -> float:
        return left + ((day - window_start).days / day_span) * plot_width

    def y_for(value: float) -> float:
        return top + ((100 - value) / 100) * plot_height

    svg_parts = []
    for tick in range(0, 101, 20):
        y = y_for(tick)
        svg_parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" class="grid"/>'
            f'<text x="{left-10}" y="{y+4:.1f}" text-anchor="end" class="axis">{tick}</text>'
        )

    selected = [item for item in observations if window_start <= item.day <= window_end]
    if selected:
        points = " ".join(f"{x_for(item.day):.1f},{y_for(item.interest):.1f}" for item in selected)
        svg_parts.append(f'<polyline points="{points}" class="source-line"/>')

    candle_width = max(4.0, min(20.0, plot_width / max(1, len(candles)) * 0.45))
    for candle in candles:
        midpoint = candle.observed_start + (candle.observed_end - candle.observed_start) / 2
        x = x_for(midpoint)
        if candle.observations == 1:
            svg_parts.append(
                f'<circle cx="{x:.1f}" cy="{y_for(candle.close):.1f}" r="4" class="single"/>'
            )
            continue
        rising = candle.close >= candle.open
        css_class = "up" if rising else "down"
        if candle.edge_bucket or candle.source_partial:
            css_class += " incomplete"
        y_high, y_low = y_for(candle.high), y_for(candle.low)
        y_open, y_close = y_for(candle.open), y_for(candle.close)
        body_top = min(y_open, y_close)
        body_height = max(2.0, abs(y_close - y_open))
        svg_parts.append(
            f'<line x1="{x:.1f}" y1="{y_high:.1f}" x2="{x:.1f}" y2="{y_low:.1f}" class="wick {css_class}"/>'
            f'<rect x="{x-candle_width/2:.1f}" y="{body_top:.1f}" width="{candle_width:.1f}" height="{body_height:.1f}" class="body {css_class}"/>'
        )

    rows = []
    for candle in candles:
        flags = []
        if candle.edge_bucket:
            flags.append("edge")
        if candle.source_partial:
            flags.append("source partial")
        if candle.observations == 1:
            flags.append("single point")
        cells = [
            candle.bucket_start.isoformat(),
            f"{candle.open:g}", f"{candle.high:g}", f"{candle.low:g}", f"{candle.close:g}",
            str(candle.observations),
            f"{candle.observed_start.isoformat()} to {candle.observed_end.isoformat()}",
            ", ".join(flags) or "—",
        ]
        rows.append("<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in cells) + "</tr>")

    warning_items = "".join(f"<li>{html.escape(item)}</li>" for item in warnings)
    title = html.escape(term)
    profile = html.escape(profile_label)
    source = html.escape(f"{source_format}: {source_column}")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Keyword Search Insights</title>
<style>
:root {{ color-scheme: light dark; --bg:#faf9f6; --ink:#17202a; --muted:#667085; --grid:#d9dde5; --up:#087e5b; --down:#bd3b45; --line:#4169a1; }}
@media (prefers-color-scheme:dark) {{ :root {{ --bg:#12161d; --ink:#edf1f7; --muted:#aab4c3; --grid:#303846; --line:#7da7df; }} }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 system-ui,sans-serif; }}
main {{ max-width:1100px; margin:0 auto; padding:32px 24px 56px; }}
h1 {{ margin:0 0 4px; font-size:28px; }} .meta,.note {{ color:var(--muted); }}
.card {{ border:1px solid var(--grid); border-radius:12px; padding:16px; margin:22px 0; overflow:auto; }}
svg {{ min-width:720px; width:100%; height:auto; }} .grid {{ stroke:var(--grid); stroke-width:1; }}
.axis {{ fill:var(--muted); font-size:12px; }} .source-line {{ fill:none; stroke:var(--line); stroke-width:1.7; opacity:.68; }}
.wick {{ stroke-width:2; }} .body {{ stroke-width:1; }} .up {{ stroke:var(--up); fill:var(--up); }} .down {{ stroke:var(--down); fill:var(--down); }}
.incomplete {{ stroke-dasharray:4 3; opacity:.72; }} .single {{ fill:var(--line); stroke:var(--bg); stroke-width:1.5; }}
table {{ border-collapse:collapse; width:100%; font-variant-numeric:tabular-nums; }} th,td {{ padding:7px 9px; border-bottom:1px solid var(--grid); text-align:right; white-space:nowrap; }} th:first-child,td:first-child,th:nth-last-child(-n+2),td:nth-last-child(-n+2) {{ text-align:left; }}
code {{ overflow-wrap:anywhere; }}
</style>
</head>
<body><main>
<h1>{title}</h1>
<div class="meta">{profile} · {window_start.isoformat()} through {window_end.isoformat()} · {source}</div>
<div class="card">
<svg viewBox="0 0 {width} {height}" role="img" aria-labelledby="chart-title chart-desc">
<title id="chart-title">OHLC summary for {title}</title>
<desc id="chart-desc">Relative interest from zero to one hundred. Candles summarize available points and the thin line shows source observations.</desc>
{''.join(svg_parts)}
<text x="{left}" y="{height-14}" class="axis">{window_start.isoformat()}</text>
<text x="{width-right}" y="{height-14}" text-anchor="end" class="axis">{window_end.isoformat()}</text>
</svg>
</div>
<p class="note">The line shows available source observations. Candles summarize first, maximum, minimum, and last values within each bucket. A dot marks a single-observation bucket; it is not an inferred range. Dashed candles touch the selected window edge or include a source-partial point.</p>
<h2>Coverage and caveats</h2>
<ul><li>Values are relative indices from this input frame, not absolute search volume.</li><li>Separately normalized exports may not share a scale.</li>{warning_items}</ul>
<div class="card"><table><thead><tr><th>Bucket</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>n</th><th>Observed</th><th>Flags</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
</main></body></html>"""
