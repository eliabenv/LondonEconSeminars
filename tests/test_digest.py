from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from seminar_tracker.digest import filter_upcoming, render_text_digest
from seminar_tracker.models import RefreshError, Seminar


class DigestTests(unittest.TestCase):
    def test_filter_upcoming_and_render(self) -> None:
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
                institution="KCL",
                series="Economics Brownbag Seminar Series",
                title="Unexpected Deaths",
                speaker="Yonatan Berman",
                speaker_affiliation="Tel Aviv University",
                start=datetime(2026, 4, 8, 13, 0, tzinfo=tz),
                end=datetime(2026, 4, 8, 14, 0, tzinfo=tz),
                location="Bush House",
                url="https://example.com/kcl",
            ),
        ]
        selected = filter_upcoming(seminars, now=now, days=7)
        self.assertEqual(len(selected), 1)
        digest = render_text_digest(
            selected,
            now=now,
            days=7,
            errors=[RefreshError("UCL", "https://example.com/ucl", "No detail pages published yet")],
        )
        self.assertIn("Intergenerational Effects of Domestic Violence", digest)
        self.assertIn("Scrape issues", digest)


if __name__ == "__main__":
    unittest.main()

