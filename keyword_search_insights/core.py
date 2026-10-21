"""CSV loading and deterministic OHLC aggregation."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, List, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Observation:
    day: date
    interest: float
    is_partial: bool = False


@dataclass(frozen=True)
class LoadedSeries:
    observations: List[Observation]
    source_format: str
    source_column: str
    source_start: date
    source_end: date
    skipped_missing: int = 0
    skipped_below_one: int = 0


@dataclass(frozen=True)
class Profile:
    key: str
    label: str
    lookback_months: int
    bucket: str


@dataclass(frozen=True)
class Candle:
    bucket_start: date
    bucket_end: date
    open: float
    high: float
    low: float
    close: float
    observations: int
    observed_start: date
    observed_end: date
    source_partial: bool
    edge_bucket: bool


PROFILES: Mapping[str, Profile] = {
    "5y-yearly": Profile("5y-yearly", "5 years / yearly", 60, "year"),
    "1y-monthly": Profile("1y-monthly", "1 year / monthly", 12, "month"),
    "6mo-biweekly": Profile("6mo-biweekly", "6 months / 2-week", 6, "biweek"),
    "3mo-weekly": Profile("3mo-weekly", "3 months / weekly", 3, "week"),
    "30d-daily": Profile("30d-daily", "30 days / daily", 0, "day"),
}


def _parse_bool(value: str, row_number: int) -> bool:
    normalized = value.strip().lower()
    if normalized in {"", "0", "false", "no"}:
        return False
    if normalized in {"1", "true", "yes"}:
        return True
    raise ValueError(f"row {row_number}: is_partial must be true or false")


def _parse_source_date(value: str, row_number: int, time_header: str) -> date:
    cleaned = value.strip()
    if time_header.casefold() == "month" and re.fullmatch(r"\d{4}-\d{2}", cleaned):
        cleaned += "-01"
    elif not re.fullmatch(r"\d{4}-\d{2}-\d{2}", cleaned):
        expected = "YYYY-MM" if time_header.casefold() == "month" else "YYYY-MM-DD"
        raise ValueError(f"row {row_number}: date must use {expected}")
    try:
        return date.fromisoformat(cleaned)
    except ValueError as exc:
        raise ValueError(f"row {row_number}: invalid date value") from exc


def _choose_interest_column(fieldnames: Sequence[str], term: Optional[str]) -> Tuple[str, str]:
    lowered_names = {name.casefold(): name for name in fieldnames}
    if "date" in lowered_names and "interest" in lowered_names:
        return lowered_names["interest"], "neutral"
    candidates = [
        name
        for name in fieldnames[1:]
        if name.casefold() not in {"ispartial", "is_partial"}
    ]
    if len(candidates) == 1:
        return candidates[0], "google-trends-export"
    if term:
        lowered_term = term.casefold()
        matches = [
            name
            for name in candidates
            if name.casefold() == lowered_term
            or name.split(":", 1)[0].strip().casefold() == lowered_term
        ]
        if len(matches) == 1:
            return matches[0], "google-trends-export"
    available = ", ".join(candidates) or "none"
    raise ValueError(f"CSV has multiple series; --term must match one of: {available}")


def load_csv(path: Path, term: Optional[str] = None) -> LoadedSeries:
    """Load a neutral CSV or an exported Google Trends timeline CSV.

    Google export preamble rows are skipped. Suppressed ``<1`` and missing values
    are counted and omitted because their exact numeric value is unavailable.
    """
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.reader(handle))

    header_index = None
    for index, row in enumerate(rows):
        if row and row[0].strip().casefold() == "hour":
            raise ValueError("hourly CSV input is not supported; aggregate it to daily data first")
        if row and row[0].strip().casefold() in {"date", "day", "week", "month"}:
            header_index = index
            break
    if header_index is None:
        raise ValueError("CSV must contain a date, day, week, or month timeline header")

    fieldnames = [name.strip() for name in rows[header_index]]
    if any(not name for name in fieldnames):
        raise ValueError("CSV header names cannot be empty")
    folded_headers = [name.casefold() for name in fieldnames]
    if len(folded_headers) != len(set(folded_headers)):
        raise ValueError("CSV contains duplicate or case-ambiguous header names")
    interest_column, source_format = _choose_interest_column(fieldnames, term)
    header_lookup = {name.casefold(): name for name in fieldnames}
    partial_column = header_lookup.get("is_partial") or header_lookup.get("ispartial")
    observations: List[Observation] = []
    source_days: List[date] = []
    skipped_missing = 0
    skipped_below_one = 0
    for row_number, values in enumerate(rows[header_index + 1 :], start=header_index + 2):
        if not values or not any(value.strip() for value in values):
            continue
        if len(values) != len(fieldnames):
            raise ValueError(
                f"row {row_number}: expected {len(fieldnames)} fields, found {len(values)}"
            )
        row = dict(zip(fieldnames, values))
        day = _parse_source_date(row.get(fieldnames[0], ""), row_number, fieldnames[0])
        source_days.append(day)
        raw_interest = (row.get(interest_column) or "").strip()
        if not raw_interest:
            skipped_missing += 1
            continue
        if raw_interest == "<1":
            skipped_below_one += 1
            continue
        try:
            interest = float(raw_interest)
        except ValueError as exc:
            raise ValueError(f"row {row_number}: invalid interest value") from exc
        if not 0 <= interest <= 100:
            raise ValueError(f"row {row_number}: interest must be between 0 and 100")
        partial = _parse_bool(row.get(partial_column, "") if partial_column else "", row_number)
        observations.append(Observation(day, interest, partial))

    observations.sort(key=lambda item: item.day)
    if not observations:
        raise ValueError("CSV contains no numeric observations")
    days = [item.day for item in observations]
    if len(days) != len(set(days)):
        raise ValueError("CSV contains duplicate dates; hourly input must be aggregated first")
    return LoadedSeries(
        observations=observations,
        source_format=source_format,
        source_column=interest_column,
        source_start=min(source_days),
        source_end=max(source_days),
        skipped_missing=skipped_missing,
        skipped_below_one=skipped_below_one,
    )


def infer_cadence_days(observations: Sequence[Observation]) -> Optional[float]:
    if len(observations) < 2:
        return None
    gaps = sorted(
        (current.day - previous.day).days
        for previous, current in zip(observations, observations[1:])
        if current.day > previous.day
    )
    if not gaps:
        return None
    middle = len(gaps) // 2
    if len(gaps) % 2:
        return float(gaps[middle])
    return (gaps[middle - 1] + gaps[middle]) / 2


def _shift_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    next_month = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    last_day = (next_month - timedelta(days=1)).day
    return date(year, month, min(value.day, last_day))


def _window_start(latest: date, profile: Profile) -> date:
    if profile.key == "30d-daily":
        return latest - timedelta(days=29)
    return _shift_months(latest, -profile.lookback_months)


def _month_end(start: date) -> date:
    return _shift_months(start, 1) - timedelta(days=1)


def _bucket_bounds(day: date, bucket: str, anchor: date) -> Tuple[date, date]:
    if bucket == "day":
        return day, day
    if bucket == "week":
        start = day - timedelta(days=day.weekday())
        return start, start + timedelta(days=6)
    if bucket == "biweek":
        start = anchor + timedelta(days=((day - anchor).days // 14) * 14)
        return start, start + timedelta(days=13)
    if bucket == "month":
        start = date(day.year, day.month, 1)
        return start, _month_end(start)
    if bucket == "year":
        return date(day.year, 1, 1), date(day.year, 12, 31)
    raise ValueError(f"unsupported bucket: {bucket}")


def build_candles(
    observations: Sequence[Observation], profile: Profile
) -> Tuple[List[Candle], date, date]:
    """Filter to a profile window and aggregate each deterministic time bucket."""
    if not observations:
        raise ValueError("at least one observation is required")
    ordered = sorted(observations, key=lambda item: item.day)
    latest = ordered[-1].day
    start = _window_start(latest, profile)
    selected = [item for item in ordered if start <= item.day <= latest]
    if not selected:
        raise ValueError("no observations fall inside the selected profile")

    grouped = {}
    for item in selected:
        bounds = _bucket_bounds(item.day, profile.bucket, start)
        grouped.setdefault(bounds, []).append(item)

    candles: List[Candle] = []
    for (bucket_start, bucket_end), items in sorted(grouped.items()):
        values = [item.interest for item in items]
        candles.append(
            Candle(
                bucket_start=bucket_start,
                bucket_end=bucket_end,
                open=values[0],
                high=max(values),
                low=min(values),
                close=values[-1],
                observations=len(items),
                observed_start=items[0].day,
                observed_end=items[-1].day,
                source_partial=any(item.is_partial for item in items),
                edge_bucket=bucket_start < start or bucket_end > latest,
            )
        )
    return candles, start, latest


def serialize_rows(candles: Iterable[Candle]) -> List[dict]:
    rows = []
    for candle in candles:
        rows.append(
            {
                "bucket_start": candle.bucket_start.isoformat(),
                "bucket_end": candle.bucket_end.isoformat(),
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "observations": candle.observations,
                "observed_start": candle.observed_start.isoformat(),
                "observed_end": candle.observed_end.isoformat(),
                "source_partial": candle.source_partial,
                "edge_bucket": candle.edge_bucket,
            }
        )
    return rows
