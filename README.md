# Keyword Search Insights

Keyword Search Insights is a small, offline-first command-line utility that
summarizes one normalized search-interest series as open, high, low, and close
(OHLC) buckets. It accepts the term or topic label at runtime and never embeds a
search query.

I built this utility to turn an exported search-interest timeline into a compact,
inspectable view without implying that relative interest is market price or
absolute search volume. It is also a small Python project that is easy to review,
test, and extend in public.

The utility currently reads a neutral CSV or a downloaded Google Trends timeline
CSV. It does not call Google, Bing, or an unofficial endpoint. That boundary
makes the transformation reproducible and keeps provider access, credentials,
and terms of use outside the core.

## What the candles mean

Each candle describes the first, maximum, minimum, and last **relative index**
observed inside a time bucket. It is not a traded asset, and the values are not
absolute search counts. The output includes the number of source observations,
their covered date span, source partial flags, and edge-bucket flags.

Google explains that Trends website data is sampled, normalized by time and
location, and scaled from 0 to 100 within a request:
https://support.google.com/trends/answer/4365533. Separate website exports can
therefore have separate scales. Do not compare their candle heights as though
they share an absolute baseline.

Google announced an official Trends API with consistently scaled relative data,
but access is currently a limited alpha and its values still do not represent
absolute search volume: https://developers.google.com/search/apis/trends.

## Run it

Python 3.9 or newer is sufficient. No runtime packages are required.

```bash
python -m keyword_search_insights
```

The interactive flow asks for a CSV path, a term or topic label, and one of:

- 5 years / yearly candles
- 1 year / monthly candles
- 6 months / 2-week candles
- 3 months / weekly candles
- 30 days / daily candles

The same flow is scriptable:

```bash
python -m keyword_search_insights \
  --input fixtures/sample_interest.csv \
  --term "your term" \
  --profile 30d-daily \
  --format chart
```

Formats are `chart`, `table`, `csv`, `json`, and `html`. Any format can be written
to a new file with `--output`; existing files are never overwritten. Without
`--output`, text formats print to standard output. HTML is a self-contained
report with an inline SVG candlestick chart, a source-line overlay, coverage, and
the interpretation caveats embedded in the file, so HTML requires `--output`:

```bash
python -m keyword_search_insights \
  --input fixtures/sample_interest.csv \
  --term "your term" \
  --profile 30d-daily \
  --format html \
  --output report.html
```

Neutral CSV input must contain:

```csv
date,interest,is_partial
2026-10-20,79,false
2026-10-21,84,true
```

`date` uses ISO `YYYY-MM-DD`; `interest` must be between 0 and 100;
`is_partial` is optional. Downloaded Google Trends timeline CSVs with preamble
rows and `Day`, `Week`, or `Month` headers are also accepted. If an export has
multiple term columns, `--term` must match the desired column. Missing and `<1`
values are skipped and counted because their exact numeric value is unavailable.
Coarser input is never upsampled or interpolated. The included fixture is
synthetic transformation data, not a claim about any real query.

Human-readable reports distinguish the selected display window from the source
file's actual coverage. Filtering retains the scale already present in the input;
it does not renormalize the values.

## Verify it

```bash
python -m unittest discover -s tests -v
```

## Current scope

Built: deterministic offline CSV loading, Google export recognition, five
timeframe profiles, OHLC aggregation, visible bucket coverage, terminal and
self-contained HTML/SVG charts, and machine-readable output. Planned work is
kept in [BACKLOG.md](BACKLOG.md). No live provider, cross-export normalization,
absolute-volume estimation, GUI, or hosted service is implemented.

The bounded CrewKite test scope and manual checks are recorded in
[`docs/UAT.md`](docs/UAT.md). This seed has not been released or qualified by
CrewKite, and it does not imply any provider capability.

The code is available under the MIT License. The supplied legacy file remains
outside this repository and unchanged; `provenance/ORIGIN.md` records its
basename and checksum without publishing a private filesystem path.
