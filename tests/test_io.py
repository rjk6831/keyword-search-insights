from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from keyword_search_insights.cli import main
from keyword_search_insights.core import load_csv


class CsvAndCliTests(unittest.TestCase):
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

    def test_noninteractive_json_output(self):
        with TemporaryDirectory() as directory:
            path = Path(directory, "series.csv")
            path.write_text(
                "date,interest,is_partial\n"
                "2026-01-01,25,false\n"
                "2026-01-02,50,true\n",
                encoding="utf-8",
            )
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

    def test_html_report_escapes_term_and_refuses_overwrite(self):
        with TemporaryDirectory() as directory:
            source = Path(directory, "series.csv")
            destination = Path(directory, "report.html")
            source.write_text(
                "date,interest\n2026-01-01,25\n2026-01-02,50\n",
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


if __name__ == "__main__":
    unittest.main()
