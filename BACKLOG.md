# Backlog

The baseline stays intentionally small. The next increments are independently
reviewable and keep provider-specific behavior outside the aggregation core.

1. Extract the current Google export recognition into
   `keyword_search_insights/importers/google_csv.py` as more official fixtures
   establish stable header variants.
2. Add `keyword_search_insights/metadata.py` and a sidecar manifest recording
   provider, geography, category, search property, requested window, retrieval
   time, source granularity, and checksum.
3. Add `keyword_search_insights/compare.py` to reject cross-frame comparisons by
   default and permit them only when a manifest proves a shared scale.
4. Extract `keyword_search_insights/render_svg.py` from the current self-contained
   HTML renderer and add a standalone accessible SVG output option.
5. Add `keyword_search_insights/importers/google_alpha.py` only after documented
   official API access is available and its authentication and terms are reviewed.
6. Add `tests/test_sparse_coverage.py` with daily, weekly, and monthly fixtures to
   make inferred gaps and incomplete edge buckets explicit.
7. Add `docs/provider-evaluation.md` before any Bing adapter. It should identify
   a current documented data source, access terms, units, and reproducibility
   limits rather than assuming a comparable Bing history API exists.
