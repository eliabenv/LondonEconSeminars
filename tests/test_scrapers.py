from __future__ import annotations

import unittest
from datetime import datetime
from urllib.error import URLError
from zoneinfo import ZoneInfo

from seminar_tracker.config import SourceSpec
from seminar_tracker.sources import (
    FetchClient,
    _parse_ifs_events,
    _parse_kcl_kbs,
    _parse_kcl_brownbag,
    _parse_lse_biweekly,
    _parse_oce_series,
    _parse_imperial_epp,
    _parse_ucl_detail_page,
    _parse_qmul_external,
)


class ScraperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = FetchClient()
        self.now = datetime(2026, 3, 25, 9, 0, tzinfo=ZoneInfo("Europe/London"))

    def test_lse_parser_extracts_series_title_and_notes(self) -> None:
        html = """
        <html><body>
          <h1>Biweekly research seminars and workshops</h1>
          <a href="/event">Labour and Education Seminars: Parents Working from Home and their Children's Education</a>
          <p>Date: Tuesday 24 March 2026 13:30 - 14:45</p>
          <p>Speaker: Eric Maurin (Paris School of Economics)</p>
          <p>Location: SAL 2.04</p>
          <p>This event is both online and in person</p>
        </body></html>
        """
        spec = SourceSpec("lse", "LSE", "LSE Seminars", "https://example.com/lse", "lse_biweekly")
        seminars = _parse_lse_biweekly(spec, html, self.client, self.now)
        self.assertEqual(len(seminars), 1)
        self.assertEqual(seminars[0].series, "Labour and Education Seminars")
        self.assertIn("Parents Working from Home", seminars[0].title)
        self.assertIn("online", seminars[0].notes.lower())

    def test_qmul_parser_reads_table_rows(self) -> None:
        html = """
        <table>
          <tr><th>Date</th><th>Time</th><th>Event</th><th>Venue</th></tr>
          <tr>
            <td>25 Mar 2026</td>
            <td>1:30 PM - 2:45 PM</td>
            <td>Anna Russo (Harvard) The long-run effects of migration</td>
            <td>GC201</td>
          </tr>
        </table>
        """
        spec = SourceSpec("qmul", "QMUL", "External seminars", "https://example.com/qmul", "qmul_external")
        seminars = _parse_qmul_external(spec, html, self.client, self.now)
        self.assertEqual(len(seminars), 1)
        self.assertEqual(seminars[0].speaker, "Anna Russo")
        self.assertEqual(seminars[0].location, "GC201")

    def test_kcl_brownbag_uses_academic_year_rollover(self) -> None:
        html = """
        <html><body>
          <p>Economics Brownbag Seminar Series for academic year 2025-2026</p>
          <p>26 March, Bush House, (NE) 9.03, 13.00 - 14.00</p>
          <p>Yonatan Berman (Tel Aviv University) - Unexpected Deaths</p>
        </body></html>
        """
        spec = SourceSpec("kcl_b", "KCL", "Economics Brownbag Seminar Series", "https://example.com/kcl", "kcl_brownbag")
        seminars = _parse_kcl_brownbag(spec, html, self.client, self.now)
        self.assertEqual(len(seminars), 1)
        self.assertEqual(seminars[0].start.year, 2026)
        self.assertEqual(seminars[0].speaker_affiliation, "Tel Aviv University")

    def test_fetch_client_detects_ssl_errors(self) -> None:
        exc = URLError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")
        self.assertTrue(FetchClient._looks_like_ssl_issue(exc))

    def test_ucl_detail_parser_skips_non_seminar_event_dates(self) -> None:
        html = """
        <html><body>
          <h2>Seminars</h2>
          <p>CReAM Seminar</p>
          <p>Speaker: Cristobal Otero (Columbia University).</p>
          <p>Title: Physicians' Occupational Licensing and the Quantity-Quality Trade-off.</p>
          <p>Date: Monday 10 March, 1600-1730hrs.</p>
          <p>Venue: Bedford Way (26) 305 - visit the location on a map.</p>
          <h2>Events</h2>
          <p>Date: Tuesday 1 April and Wednesday 9 April</p>
        </body></html>
        """
        spec = SourceSpec("ucl", "UCL", "Department of Economics Seminars", "https://example.com/ucl", "ucl_department")
        seminars = _parse_ucl_detail_page(
            spec,
            html,
            "https://www.ucl.ac.uk/social-historical-sciences/news/2025/mar/example",
        )
        self.assertEqual(len(seminars), 1)
        self.assertEqual(seminars[0].institution, "UCL")

    def test_kcl_kbs_parser_handles_colon_style_entries(self) -> None:
        html = """
        <html><body>
          <p>King's Business School Seminars in Economics academic year 2025/2026</p>
          <p>1 October: Mark Armstrong (University College London) - Multibrand Price Dispersion</p>
        </body></html>
        """
        spec = SourceSpec("kcl_kbs", "KCL", "King's Business School Seminars in Economics", "https://example.com/kcl", "kcl_kbs")
        seminars = _parse_kcl_kbs(spec, html, self.client, self.now)
        self.assertEqual(len(seminars), 1)
        self.assertEqual(seminars[0].speaker, "Mark Armstrong")
        self.assertEqual(seminars[0].speaker_affiliation, "University College London")
        self.assertIn("Multibrand Price Dispersion", seminars[0].title)

    def test_imperial_parser_extracts_speaker_title_and_defaults(self) -> None:
        html = """
        <html><body>
          <p>Spring term 2026 external seminar series</p>
          <p>Tuesday 03 February 2026, Lorenzo Casaburi (UZH), Copayments and the Value of Health Insurance</p>
        </body></html>
        """
        spec = SourceSpec("imperial", "Imperial", "Economics & Public Policy Seminars", "https://example.com/imperial", "imperial_epp")
        seminars = _parse_imperial_epp(spec, html, self.client, self.now)
        self.assertEqual(len(seminars), 1)
        self.assertEqual(seminars[0].speaker, "Lorenzo Casaburi")
        self.assertEqual(seminars[0].speaker_affiliation, "UZH")
        self.assertEqual(seminars[0].start.hour, 13)
        self.assertIn("Health Insurance", seminars[0].title)

    def test_ifs_events_parser_extracts_upcoming_cards(self) -> None:
        html = """
        <html><body>
          <h2>All upcoming events</h2>
          <h3><a href="/events/housing">How can governments make housing more affordable?</a></h3>
          <p>Event 15 April 2026 at 09:00</p>
          <p>Researchers present evidence on housing affordability.</p>
          <h3><a href="/events/labour">1st Annual CEP-IFS Labour Economics Conference</a></h3>
          <p>Conference 15 June 2026 at 09:00 London</p>
          <p>Labour conference in London.</p>
          <h2>All past events</h2>
        </body></html>
        """
        spec = SourceSpec("ifs", "IFS", "Institute for Fiscal Studies Events", "https://ifs.example/events", "ifs_events")
        seminars = _parse_ifs_events(spec, html, self.client, self.now)
        self.assertEqual(len(seminars), 2)
        self.assertEqual(seminars[0].series, "IFS Event")
        self.assertEqual(seminars[1].series, "IFS Conference")
        self.assertEqual(seminars[1].location, "London")

    def test_oce_series_parser_extracts_weekly_seminar_entries(self) -> None:
        html = """
        <html><body>
          <h1>OCE Research Seminars 2025-2026</h1>
          <p>Michal Rubaszek, Warsaw School of Economics Are Exchange Rates Predictable?11/09/25, 1pm GMT</p>
          <p>Tom Schwantje, Bocconi University Banking on Conflict: Managers and Organizational Design Tuesday 18/11/25, 1pm GMT</p>
        </body></html>
        """
        spec = SourceSpec("oce", "OCE-EBRD", "OCE Research Seminars", "https://example.com/oce", "oce_series")
        seminars = _parse_oce_series(spec, html, self.client, self.now)
        self.assertEqual(len(seminars), 2)
        self.assertEqual(seminars[0].speaker, "Michal Rubaszek")
        self.assertEqual(seminars[0].speaker_affiliation, "Warsaw School of Economics")
        self.assertIn("Are Exchange Rates Predictable?", seminars[0].title)
        self.assertEqual(seminars[1].speaker_affiliation, "Bocconi University")


if __name__ == "__main__":
    unittest.main()
