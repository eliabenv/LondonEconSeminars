from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from seminar_tracker.site_html import render_site_homepage


class SiteHtmlTests(unittest.TestCase):
    def test_render_site_homepage_contains_calendar_button_and_update_links(self) -> None:
        tz = ZoneInfo("Europe/London")
        html = render_site_homepage(
            last_updated=datetime(2026, 3, 26, 8, 15, tzinfo=tz),
            calendar_days=60,
            digest_days=7,
            calendar_count=47,
            digest_count=10,
            error_count=1,
            repo_url="https://github.com/example/london-econ",
            manual_update_url="https://github.com/example/london-econ#manual-update-for-colleagues",
        )
        self.assertIn('href="calendar.html"', html)
        self.assertIn("Last updated:", html)
        self.assertIn("26 March 2026 08:15 GMT", html)
        self.assertIn("How to update", html)
        self.assertIn("GitHub Pages is a static website", html)


if __name__ == "__main__":
    unittest.main()
