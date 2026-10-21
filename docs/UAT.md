# CrewKite UAT scope

This repository is a candidate small-project fixture for the current
`D2b-uat-02` CrewKite profile. The useful scope is planning a bounded change,
editing several related files, reviewing the diff, retaining project context, and
handing the result back for human verification.

It does not qualify CrewKite's Python toolchain or provider behavior. Explicit
project-command controls planned for B6 are not shipped in the current profile,
so Python verification remains a manual repository check:

```bash
python3 -m unittest discover -s tests -v
python3 -m keyword_search_insights \
  --input fixtures/sample_interest.csv \
  --term "manual UAT term" \
  --profile 3mo-weekly \
  --format html \
  --output /tmp/keyword-search-insights-uat.html
git diff --check
git status --short
```

The expected result is a passing offline test suite, a newly created HTML report,
no overwrite of an existing output, and a clean or intentionally explained Git
state. Choose a new output path for each successful report run; reusing the path
should fail without replacing the file. These checks are manual evidence for this
repository only. They are not a CrewKite release qualifier.
