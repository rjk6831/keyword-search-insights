# Assessment of the input utility

The supplied script remains unchanged at its original location. Its path and
checksum are recorded in `provenance/ORIGIN.md`. This assessment explains why
the new baseline keeps only its central idea.

## Data meaning

Google states that Trends website results use a sample of searches. Each point
is normalized against total searches for its time and geography, then the series
is scaled from 0 to 100. Google recommends relative comparisons and distinguishes
Trends from advertiser search-volume reporting.

Source: https://support.google.com/trends/answer/4365533

For that reason, the original `baseline / 100` multiplier does not estimate
absolute volume. It maps the maximum normalized point to a number described as an
average, mixes units, and has no model tying the result to total searches. The
stated `+/-15% to 35%` error range has no cited basis. Both features were removed.

The Google Trends website rescales each request. Google says its limited-alpha
official API uses a separate, consistently scaled method that supports joins
across requests, but those values still represent search interest rather than
absolute counts.

Source: https://developers.google.com/search/apis/trends

## Source access

The input uses `pytrends`, whose own README calls it an unofficial Google Trends
API. The repository was archived in April 2025 and is read-only. A former
maintainer explicitly advised users to stop relying on it for analysis.

Sources:

- https://github.com/GeneralMills/pytrends
- https://github.com/GeneralMills/pytrends/issues/636

The baseline makes no network request and does not claim an official Google or
Bing integration.

## Aggregation and coverage

OHLC aggregation can be a compact description of variation inside a bucket, but
it does not turn search interest into market data. `open` and `close` mean the
first and last available observation; `high` and `low` are the observed extrema.
There is no trading volume.

The input utility silently resamples calendar buckets, discards missing buckets,
and gives incomplete first and last buckets the same visual weight as full ones.
It also creates a zero-valued `Volume` series. The new baseline reports source
observation count, observed start and end dates, source partial flags, and whether
a bucket crosses the selected window edge.

The input's 6-month view is fetched as a 12-month Trends request and sliced after
normalization. Its scale can therefore be determined by observations that are not
shown. More generally, separately requested 0-to-100 windows are not directly
comparable. The new baseline processes one exported frame at a time and labels
that limitation in human-readable output.

## Operational accuracy

The input labels itself production and analyst grade without tests or source
metadata. It hard-codes a timezone offset, treats every request exception as a
rate limit, prints a disclaimer that is not actually embedded in saved images,
and derives filesystem names directly from user text. The new seed uses no live
endpoint, has focused offline tests, and does not put the term into a path.
