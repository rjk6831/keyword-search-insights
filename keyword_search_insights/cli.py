"""Interactive and scriptable command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from .core import PROFILES, build_candles, infer_cadence_days, load_csv
from .render import render_chart, render_csv, render_html_report, render_json, render_table


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="keyword-search-insights",
        description="Summarize one normalized search-interest series as OHLC candles.",
    )
    parser.add_argument("--input", type=Path, help="CSV with date,interest[,is_partial]")
    parser.add_argument("--term", help="Search term or topic label shown in output")
    parser.add_argument("--profile", choices=tuple(PROFILES), help="Lookback and bucket size")
    parser.add_argument(
        "--format", choices=("chart", "table", "csv", "json", "html"), default="chart"
    )
    parser.add_argument("--output", type=Path, help="Write to a new file instead of stdout")
    return parser


def _choose_profile() -> str:
    keys = list(PROFILES)
    print("Choose a timeframe:")
    for index, key in enumerate(keys, start=1):
        print(f"  {index}. {PROFILES[key].label}")
    raw = input("> ").strip()
    try:
        selection = int(raw)
    except ValueError:
        raise ValueError("timeframe selection must be a number from 1 to 5")
    if not 1 <= selection <= len(keys):
        raise ValueError("timeframe selection must be a number from 1 to 5")
    return keys[selection - 1]


def _collect_interactive(args: argparse.Namespace) -> argparse.Namespace:
    if args.input is None:
        raw = input("CSV path (date, interest, optional is_partial):\n> ").strip()
        if not raw:
            raise ValueError("CSV path cannot be empty")
        args.input = Path(raw)
    if not args.term:
        args.term = input("Search term or topic label:\n> ").strip()
    if not args.term:
        raise ValueError("term label cannot be empty")
    if args.profile is None:
        args.profile = _choose_profile()
    return args


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        args = _collect_interactive(args)
        loaded = load_csv(args.input, args.term)
        profile = PROFILES[args.profile]
        candles, window_start, window_end = build_candles(loaded.observations, profile)
        if args.format == "html" and args.output is None:
            raise ValueError("--output is required for HTML reports")
    except (EOFError, KeyboardInterrupt):
        print("cancelled: no changes were written", file=sys.stderr)
        return 130
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    warnings = []
    if loaded.skipped_below_one:
        warnings.append(
            f"Skipped {loaded.skipped_below_one} '<1' value(s); exact values were unavailable."
        )
    if loaded.skipped_missing:
        warnings.append(f"Skipped {loaded.skipped_missing} missing value(s).")
    single_count = sum(candle.observations == 1 for candle in candles)
    if single_count:
        warnings.append(
            f"{single_count} bucket(s) contain one observation and are shown as points, not ranges."
        )
    cadence = infer_cadence_days(loaded.observations)
    bucket_days = {"day": 1, "week": 7, "biweek": 14, "month": 31, "year": 366}[profile.bucket]
    if cadence is not None and cadence > bucket_days:
        warnings.append(
            f"Input cadence is about {cadence:g} days, coarser than the selected bucket; gaps are not interpolated."
        )

    source_start = loaded.source_start
    source_end = loaded.source_end
    preamble = [
        f"{args.term} — {profile.label}",
        f"Display window: {window_start.isoformat()} through {window_end.isoformat()}",
        f"Source coverage: {source_start.isoformat()} through {source_end.isoformat()}",
        "Values retain the input series' relative-interest scale; filtering does not renormalize them.",
    ]
    if loaded.source_format == "google-trends-export":
        preamble.append("Source: Google Trends export — https://trends.google.com/trends/")
    preamble.extend(f"Warning: {warning}" for warning in warnings)

    if args.format == "chart":
        content = "\n".join(preamble + [render_chart(candles), "", render_table(candles)])
    elif args.format == "table":
        content = "\n".join(preamble + [render_table(candles)])
    elif args.format == "csv":
        content = render_csv(candles)
    elif args.format == "json":
        content = render_json(candles)
    else:
        content = render_html_report(
            term=args.term,
            profile_label=profile.label,
            candles=candles,
            observations=loaded.observations,
            window_start=window_start,
            window_end=window_end,
            source_start=source_start,
            source_end=source_end,
            source_format=loaded.source_format,
            source_column=loaded.source_column,
            warnings=warnings,
        )

    if args.output is None:
        print(content)
        return 0
    try:
        with args.output.open("x", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.write("\n")
    except FileExistsError:
        print(f"error: output already exists: {args.output}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: could not write output {args.output}: {exc}", file=sys.stderr)
        return 2
    else:
        print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
