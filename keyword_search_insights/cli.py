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
    parser.add_argument("--output", type=Path, help="New output file; required for HTML")
    return parser


def _choose_profile() -> str:
    keys = list(PROFILES)
    print("Choose a timeframe:")
    for index, key in enumerate(keys, start=1):
        print(f"  {index}. {PROFILES[key].label}")
    raw = input("> ").strip()
    try:
        return keys[int(raw) - 1]
    except (ValueError, IndexError):
        raise ValueError("timeframe selection must be a number from 1 to 5")


def _collect_interactive(args: argparse.Namespace) -> argparse.Namespace:
    if args.input is None:
        raw = input("CSV path (date, interest, optional is_partial):\n> ").strip()
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
        if args.output is not None and args.output.exists():
            raise ValueError(f"output already exists: {args.output}")
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

    if args.format in {"chart", "table"}:
        print(f"{args.term} — {profile.label}")
        print(f"Input frame: {window_start.isoformat()} through {window_end.isoformat()}")
        print("Values are relative indices from this input frame, not absolute search volume.")
        for warning in warnings:
            print(f"Warning: {warning}")
    if args.format == "chart":
        print(render_chart(candles))
        print()
        print(render_table(candles))
    elif args.format == "table":
        print(render_table(candles))
    elif args.format == "csv":
        print(render_csv(candles))
    elif args.format == "json":
        print(render_json(candles))
    else:
        report = render_html_report(
            term=args.term,
            profile_label=profile.label,
            candles=candles,
            observations=loaded.observations,
            window_start=window_start,
            window_end=window_end,
            source_format=loaded.source_format,
            source_column=loaded.source_column,
            warnings=warnings,
        )
        args.output.write_text(report, encoding="utf-8")
        print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
