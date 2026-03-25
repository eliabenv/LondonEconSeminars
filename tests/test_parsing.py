from __future__ import annotations

import unittest

from seminar_tracker.parsing import (
    academic_year_for_month,
    parse_lse_datetime_range,
    parse_time_range,
    parse_ucl_datetime,
)


class ParsingTests(unittest.TestCase):
    def test_parse_time_range_supports_compact_and_ampm_formats(self) -> None:
        start, end = parse_time_range("1600-1730hrs")
        self.assertEqual(start.hour, 16)
        self.assertEqual(end.minute, 30)

        start_ampm, end_ampm = parse_time_range("1:30 PM - 2:45 PM")
        self.assertEqual(start_ampm.hour, 13)
        self.assertEqual(end_ampm.hour, 14)

        start_short, end_short = parse_time_range("2-3pm")
        self.assertEqual(start_short.hour, 14)
        self.assertEqual(end_short.hour, 15)

    def test_parse_lse_multi_day_range(self) -> None:
        start, end = parse_lse_datetime_range(
            "Wednesday 25 March 2026 09:30 - Friday 27 March 2026 17:30"
        )
        self.assertEqual(start.year, 2026)
        self.assertEqual(start.day, 25)
        self.assertEqual(end.day, 27)
        self.assertEqual(end.hour, 17)

    def test_parse_ucl_datetime(self) -> None:
        start, end = parse_ucl_datetime("Monday 24 March, 1600-1730hrs.", 2025)
        self.assertEqual(start.year, 2025)
        self.assertEqual(start.hour, 16)
        self.assertEqual(end.minute, 30)

        start2, end2 = parse_ucl_datetime("Thursday 10th October, 2-3pm", 2025)
        self.assertEqual(start2.day, 10)
        self.assertEqual(start2.hour, 14)
        self.assertEqual(end2.hour, 15)

    def test_academic_year_rollover(self) -> None:
        self.assertEqual(academic_year_for_month(10, 2025), 2025)
        self.assertEqual(academic_year_for_month(3, 2025), 2026)


if __name__ == "__main__":
    unittest.main()
