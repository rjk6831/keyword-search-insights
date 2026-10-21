from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from keyword_search_insights.cli import _choose_profile, main
from keyword_search_insights.core import load_csv


class CsvAndCliTests(unittest.TestCase):
    @staticmethod
    def _series(path: Path) -> None:
        path.write_text(
            "date,interest,is_partial\n"
            "2026-01-01,25,false\n"
            "2026-01-02,50,true\n",
            encoding="utf-8",
        )

    def test_load_csv_rejects_out_of_range_index(self):
        with TemporaryDirectory() as directory:
            path = Path(directory, "bad.csv")
            path.write_text("date,interest\n2026-01-01,101\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "between 0 and 100"):
                load_csv(path)

    def test_google_export_preamble_and_suppressed_values_are_handled(self):
        with TemporaryDirectory() as directory:
            path = Path(directory, "multiTimeline.csv")
            path.write_text(
                "Category: All categories\n\n"
                "Week,chosen term: (Worldwide)\n"
                "2026-09-06,42\n"
                "2026-09-13,<1\n"
                "2026-09-20,\n",
                encoding="utf-8",
            )
            loaded = load_csv(path, "chosen term")

        self.assertEqual("google-trends-export", loaded.source_format)
        self.assertEqual(1, len(loaded.observations))
        self.assertEqual(1, loaded.skipped_below_one)
        self.assertEqual(1, loaded.skipped_missing)
        self.assertEqual("2026-09-06", loaded.source_start.isoformat())
        self.assertEqual("2026-09-20", loaded.source_end.isoformat())

    def test_noninteractive_json_output(self):
        with TemporaryDirectory() as directory:
            path = Path(directory, "series.csv")
            self._series(path)
            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "--input", str(path),
                        "--term", "user-selected label",
                        "--profile", "30d-daily",
                        "--format", "json",
                    ]
                )

        self.assertEqual(0, result)
        self.assertIn('"close": 50.0', output.getvalue())
        self.assertIn('"source_partial": true', output.getvalue())

    def test_text_formats_use_exclusive_output_files(self):
        with TemporaryDirectory() as directory:
            source = Path(directory, "series.csv")
            self._series(source)
            for output_format in ("chart", "table", "csv", "json"):
                with self.subTest(output_format=output_format):
                    destination = Path(directory, f"report.{output_format}")
                    argv = [
                        "--input", str(source), "--term", "chosen",
                        "--profile", "30d-daily", "--format", output_format,
                        "--output", str(destination),
                    ]
                    with redirect_stdout(StringIO()):
                        self.assertEqual(0, main(argv))
                    self.assertTrue(destination.read_text(encoding="utf-8").strip())
                    with redirect_stderr(StringIO()):
                        self.assertEqual(2, main(argv))

    def test_output_write_error_is_actionable(self):
        with TemporaryDirectory() as directory:
            source = Path(directory, "series.csv")
            self._series(source)
            error = StringIO()
            with redirect_stderr(error):
                result = main([
                    "--input", str(source), "--term", "chosen",
                    "--profile", "30d-daily", "--format", "json",
                    "--output", str(Path(directory, "missing", "report.json")),
                ])
        self.assertEqual(2, result)
        self.assertIn("could not write output", error.getvalue())

    def test_cli_reports_missing_file_without_traceback(self):
        error = StringIO()
        with redirect_stderr(error):
            result = main(
                [
                    "--input", "/does/not/exist.csv",
                    "--term", "chosen at runtime",
                    "--profile", "1y-monthly",
                ]
            )
        self.assertEqual(2, result)
        self.assertIn("error:", error.getvalue())

    def test_interactive_profile_bounds_and_eof_are_clean(self):
        for value in ("0", "-1", "6"):
            with self.subTest(value=value), patch("builtins.input", return_value=value), redirect_stdout(StringIO()):
                with self.assertRaisesRegex(ValueError, "number from 1 to 5"):
                    _choose_profile()
        error = StringIO()
        with patch("builtins.input", side_effect=EOFError), redirect_stderr(error):
            result = main([])
        self.assertEqual(130, result)
        self.assertIn("cancelled", error.getvalue())

    def test_csv_structure_and_dates_fail_closed(self):
        cases = {
            "trailing date text": ("date,interest\n2026-01-01garbage,20\n", "YYYY-MM-DD"),
            "hourly data": ("Hour,chosen\n2026-01-01T01:00:00,20\n", "hourly CSV"),
            "duplicate header": ("date,interest,Interest\n2026-01-01,20,21\n", "duplicate"),
            "field mismatch": ("date,interest\n2026-01-01,20,extra\n", "expected 2 fields"),
        }
        with TemporaryDirectory() as directory:
            for index, (label, (content, message)) in enumerate(cases.items()):
                with self.subTest(label=label):
                    path = Path(directory, f"bad-{index}.csv")
                    path.write_text(content, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, message):
                        load_csv(path, "chosen")

            month_path = Path(directory, "month.csv")
            month_path.write_text("Month,chosen\n2026-01,20\n", encoding="utf-8")
            self.assertEqual("2026-01-01", load_csv(month_path, "chosen").observations[0].day.isoformat())

    def test_html_report_escapes_term_and_refuses_overwrite(self):
        with TemporaryDirectory() as directory:
            source = Path(directory, "series.csv")
            destination = Path(directory, "report.html")
            source.write_text(
                "Category: All categories\n\n"
                "Day,chosen: (Worldwide)\n2026-01-01,25\n2026-01-02,50\n",
                encoding="utf-8",
            )
            with redirect_stdout(StringIO()):
                first = main(
                    ["--input", str(source), "--term", "</title><script>",
                     "--profile", "30d-daily", "--format", "html",
                     "--output", str(destination)]
                )
            report = destination.read_text(encoding="utf-8")
            with redirect_stderr(StringIO()):
                second = main(
                    ["--input", str(source), "--term", "anything",
                     "--profile", "30d-daily", "--format", "html",
                     "--output", str(destination)]
                )

        self.assertEqual(0, first)
        self.assertEqual(2, second)
        self.assertNotIn("</title><script>", report)
        self.assertIn("&lt;/title&gt;&lt;script&gt;", report)
        self.assertIn("source-line", report)
        self.assertIn("Display window:", report)
        self.assertIn("Source coverage:", report)
        self.assertIn("https://trends.google.com/trends/", report)


if __name__ == "__main__":
    unittest.main()
