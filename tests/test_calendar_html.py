from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from seminar_tracker.calendar_html import render_calendar_html
from seminar_tracker.models import RefreshError, Seminar


class CalendarHtmlTests(unittest.TestCase):
    def test_render_calendar_html_contains_month_grid_and_events(self) -> None:
        tz = ZoneInfo("Europe/London")
        now = datetime(2026, 3, 25, 9, 0, tzinfo=tz)
        seminars = [
            Seminar(
                institution="LSE",
                series="Labour Economics Workshops",
                title="Intergenerational Effects of Domestic Violence",
                speaker="Isadora Arabe",
                speaker_affiliation="LSE",
                start=datetime(2026, 3, 26, 12, 0, tzinfo=tz),
                end=datetime(2026, 3, 26, 13, 0, tzinfo=tz),
                location="SAL 2.04",
                url="https://example.com/lse",
            ),
            Seminar(
                institution="QMUL",
                series="External seminars",
                title="Investment in Demand and Dynamic Competition for Customers",
                speaker="Lukas Nord",
                speaker_affiliation="University of Pennsylvania",
                start=datetime(2026, 3, 30, 13, 30, tzinfo=tz),
                end=datetime(2026, 3, 30, 14, 45, tzinfo=tz),
                location="GC305",
                url="https://example.com/qmul",
            ),
        ]
        for index in range(4):
            seminars.append(
                Seminar(
                    institution="LSE",
                    series="STICERD Econometrics Seminar Series",
                    title=f"Extra seminar {index}",
                    speaker="Speaker",
                    speaker_affiliation="Affiliation",
                    start=datetime(2026, 3, 26, 14 + index, 0, tzinfo=tz),
                    end=datetime(2026, 3, 26, 14 + index, 45, tzinfo=tz),
                    location="SAL",
                    url=f"https://example.com/extra-{index}",
                )
            )
        html = render_calendar_html(
            seminars,
            now=now,
            days=14,
            errors=[RefreshError("UCL", "https://example.com/ucl", "No current detail page")],
        )
        self.assertIn("March 2026", html)
        self.assertIn("Intergenerational Effects of Domestic Violence", html)
        self.assertIn("Scrape Issues", html)
        self.assertIn("event lse", html)
        self.assertIn("event qmul", html)
        self.assertIn("target='_blank'", html)
        self.assertIn("Labour Econ", html)
        self.assertIn("+1 more", html)
        self.assertIn("overflow-toggle", html)


if __name__ == "__main__":
    unittest.main()
