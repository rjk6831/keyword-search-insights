from datetime import date
import unittest

from keyword_search_insights.core import Observation, PROFILES, build_candles


class BuildCandlesTests(unittest.TestCase):
    def test_daily_profile_uses_last_thirty_days_and_preserves_ohlc(self):
        observations = [
            Observation(date(2026, 1, 1), 99),
            Observation(date(2026, 1, 31), 12),
            Observation(date(2026, 2, 1), 14, True),
        ]
        candles, start, end = build_candles(observations, PROFILES["30d-daily"])

        self.assertEqual(date(2026, 1, 3), start)
        self.assertEqual(date(2026, 2, 1), end)
        self.assertEqual([12, 14], [item.close for item in candles])
        self.assertTrue(candles[-1].source_partial)

    def test_weekly_profile_reports_bucket_coverage(self):
        observations = [
            Observation(date(2026, 1, 5), 20),
            Observation(date(2026, 1, 6), 50),
            Observation(date(2026, 1, 7), 10),
            Observation(date(2026, 1, 8), 40),
        ]
        candles, _, _ = build_candles(observations, PROFILES["3mo-weekly"])

        self.assertEqual(1, len(candles))
        candle = candles[0]
        self.assertEqual((20, 50, 10, 40), (candle.open, candle.high, candle.low, candle.close))
        self.assertEqual(4, candle.observations)
        self.assertEqual(date(2026, 1, 5), candle.observed_start)
        self.assertEqual(date(2026, 1, 8), candle.observed_end)
        self.assertTrue(candle.edge_bucket)

    def test_biweekly_buckets_anchor_to_selected_window(self):
        observations = [
            Observation(date(2026, 1, 1), 10),
            Observation(date(2026, 1, 14), 20),
            Observation(date(2026, 1, 15), 30),
            Observation(date(2026, 7, 1), 40),
        ]
        candles, start, _ = build_candles(observations, PROFILES["6mo-biweekly"])

        self.assertEqual(date(2026, 1, 1), start)
        self.assertEqual(date(2026, 1, 1), candles[0].bucket_start)
        self.assertEqual(2, candles[0].observations)
        self.assertEqual(date(2026, 1, 15), candles[1].bucket_start)


if __name__ == "__main__":
    unittest.main()
