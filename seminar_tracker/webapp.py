from __future__ import annotations

from collections import Counter
from datetime import datetime
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

from seminar_tracker.calendar_html import build_calendar_html
from seminar_tracker.config import INSTITUTIONS
from seminar_tracker.digest import display_title, filter_upcoming
from seminar_tracker.models import Snapshot
from seminar_tracker.storage import load_snapshot, save_snapshot


def serve_dashboard(
    host: str,
    port: int,
    refresh_callback,
    snapshot_path,
) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/refresh":
                snapshot = refresh_callback()
                save_snapshot(snapshot, snapshot_path)
                self.send_response(HTTPStatus.SEE_OTHER)
                self.send_header("Location", "/")
                self.end_headers()
                return

            query = parse_qs(parsed.query)
            days = int(query.get("days", ["14"])[0])
            institution = query.get("institution", [""])[0] or None
            snapshot = load_snapshot(snapshot_path)
            if snapshot is None:
                snapshot = refresh_callback()
                save_snapshot(snapshot, snapshot_path)

            if parsed.path == "/calendar":
                html, _ = build_calendar_html(
                    snapshot,
                    now=datetime.now(snapshot.refreshed_at.tzinfo),
                    days=days,
                    institution=institution,
                )
            else:
                html = _render_dashboard(snapshot, days=days, institution=institution)
            body = html.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Serving dashboard on http://{host}:{port}")
    server.serve_forever()


def _render_dashboard(snapshot: Snapshot, days: int, institution: str | None) -> str:
    now = datetime.now(snapshot.refreshed_at.tzinfo)
    seminars = filter_upcoming(snapshot.seminars, now=now, days=days, institution=institution)
    counts = Counter(item.institution for item in seminars)
    calendar_query = urlencode(
        {key: value for key, value in {"days": days, "institution": institution or ""}.items() if value}
    )
    calendar_href = f"/calendar?{calendar_query}" if calendar_query else "/calendar"
    cards = "".join(
        (
            f"<div class='stat'><span class='label'>{escape(name)}</span>"
            f"<strong>{count}</strong></div>"
        )
        for name, count in sorted(counts.items())
    ) or "<div class='stat'><span class='label'>No upcoming events</span><strong>0</strong></div>"

    rows = "".join(
        (
            "<tr>"
            f"<td>{escape(item.start.strftime('%d %b %Y'))}</td>"
            f"<td>{escape(item.start.strftime('%H:%M'))}</td>"
            f"<td>{escape(item.institution)}</td>"
            f"<td>{escape(item.series)}</td>"
            f"<td>{escape(display_title(item))}</td>"
            f"<td>{escape(item.speaker)}</td>"
            f"<td>{escape(item.location)}</td>"
            f"<td><a href='{escape(item.url)}' target='_blank' rel='noreferrer noopener'>source</a></td>"
            "</tr>"
        )
        for item in seminars
    )
    if not rows:
        rows = "<tr><td colspan='8'>No seminars found for this filter.</td></tr>"

    error_block = ""
    if snapshot.errors:
        issues = "".join(
            f"<li><strong>{escape(error.source_name)}:</strong> {escape(error.message)}</li>"
            for error in snapshot.errors
        )
        error_block = f"<section class='issues'><h2>Scrape Issues</h2><ul>{issues}</ul></section>"

    selected = institution or ""
    options = "".join(
        (
            f"<option value=\"{escape(name)}\" {'selected' if selected == name else ''}>"
            f"{escape(name)}</option>"
        )
        for name in INSTITUTIONS
    )
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>London Economics Seminars</title>
    <style>
      :root {{
        --bg: #f6f1e8;
        --panel: rgba(255, 252, 246, 0.92);
        --ink: #1d242b;
        --muted: #5a6470;
        --accent: #b4451b;
        --line: #dccfbf;
      }}
      body {{
        margin: 0;
        font-family: Georgia, "Times New Roman", serif;
        color: var(--ink);
        background:
          radial-gradient(circle at top left, rgba(255, 230, 190, 0.7), transparent 36%),
          linear-gradient(180deg, #fdf7ee 0%, var(--bg) 100%);
      }}
      main {{
        max-width: 1120px;
        margin: 0 auto;
        padding: 32px 18px 56px;
      }}
      .hero {{
        background: linear-gradient(135deg, rgba(255,255,255,0.72), rgba(255,244,224,0.9));
        border: 1px solid var(--line);
        border-radius: 24px;
        padding: 24px;
        box-shadow: 0 18px 40px rgba(64, 44, 20, 0.08);
      }}
      .sub {{
        color: var(--muted);
      }}
      .actions {{
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
        margin-top: 16px;
      }}
      .actions a, button {{
        background: var(--accent);
        color: white;
        text-decoration: none;
        border: 0;
        border-radius: 999px;
        padding: 10px 14px;
        font: inherit;
        cursor: pointer;
      }}
      form {{
        display: grid;
        gap: 12px;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        margin-top: 20px;
      }}
      input, select {{
        font: inherit;
        padding: 10px 12px;
        border-radius: 12px;
        border: 1px solid var(--line);
        background: rgba(255,255,255,0.88);
      }}
      .stats {{
        display: grid;
        gap: 12px;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        margin: 22px 0;
      }}
      .stat {{
        padding: 16px;
        border-radius: 18px;
        border: 1px solid var(--line);
        background: var(--panel);
      }}
      .stat .label {{
        display: block;
        color: var(--muted);
        margin-bottom: 8px;
      }}
      table {{
        width: 100%;
        border-collapse: collapse;
        background: var(--panel);
        border-radius: 18px;
        overflow: hidden;
        border: 1px solid var(--line);
      }}
      th, td {{
        padding: 12px 10px;
        border-bottom: 1px solid rgba(220, 207, 191, 0.7);
        text-align: left;
        vertical-align: top;
      }}
      th {{
        font-size: 0.95rem;
        color: var(--muted);
      }}
      .issues {{
        margin-top: 24px;
        padding: 18px;
        border-radius: 18px;
        border: 1px solid #d9b9aa;
        background: rgba(255, 242, 237, 0.9);
      }}
      @media (max-width: 720px) {{
        table, thead, tbody, th, td, tr {{
          display: block;
        }}
        thead {{
          display: none;
        }}
        td {{
          padding: 10px 14px;
        }}
      }}
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <h1>London Economics Seminars</h1>
        <p class="sub">Upcoming seminars and related research events across tracked London institutions. Last refreshed {escape(snapshot.refreshed_at.strftime('%d %b %Y %H:%M %Z'))}.</p>
        <div class="actions">
          <a href="/refresh">Refresh Data</a>
          <a href="{calendar_href}">Open Calendar</a>
        </div>
        <form method="get" action="/">
          <label>
            Institution
            <select name="institution">
              <option value="" {"selected" if not selected else ""}>All</option>
              {options}
            </select>
          </label>
          <label>
            Days Ahead
            <input type="number" min="1" max="365" name="days" value="{days}">
          </label>
          <button type="submit">Apply Filter</button>
        </form>
      </section>
      <section class="stats">{cards}</section>
      <section>
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Time</th>
              <th>Institution</th>
              <th>Series</th>
              <th>Title</th>
              <th>Speaker</th>
              <th>Location</th>
              <th>Link</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
      </section>
      {error_block}
    </main>
  </body>
</html>
"""
