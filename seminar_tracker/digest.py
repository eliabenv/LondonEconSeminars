from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from html import escape

from seminar_tracker.models import RefreshError, Seminar, Snapshot


def filter_upcoming(
    seminars: list[Seminar],
    now: datetime,
    days: int,
    institution: str | None = None,
) -> list[Seminar]:
    cutoff = now + timedelta(days=days)
    selected = [
        seminar
        for seminar in seminars
        if now <= seminar.start < cutoff
        and (institution is None or seminar.institution.lower() == institution.lower())
    ]
    return sorted(selected, key=lambda item: item.start)


def _group_by_day(seminars: list[Seminar]) -> dict[str, list[Seminar]]:
    grouped: dict[str, list[Seminar]] = defaultdict(list)
    for seminar in seminars:
        grouped[seminar.start.strftime("%A %d %B %Y")].append(seminar)
    return grouped


def display_title(seminar: Seminar) -> str:
    return seminar.title or seminar.series


def render_text_digest(
    seminars: list[Seminar],
    now: datetime,
    days: int,
    errors: list[RefreshError] | None = None,
) -> str:
    lines = [
        "London Economics Seminars",
        f"Window: {now.strftime('%d %b %Y')} to {(now + timedelta(days=days)).strftime('%d %b %Y')}",
        "",
    ]
    if not seminars:
        lines.append("No seminars found in this window.")
    else:
        for day, day_seminars in _group_by_day(seminars).items():
            lines.append(day)
            for seminar in day_seminars:
                time_range = f"{seminar.start.strftime('%H:%M')}-{seminar.end.strftime('%H:%M')}"
                speaker = seminar.speaker
                if seminar.speaker_affiliation:
                    speaker = f"{speaker} ({seminar.speaker_affiliation})"
                lines.append(
                    f"- {time_range} | {seminar.institution} | {seminar.series} | {display_title(seminar)}"
                )
                lines.append(f"  Speaker: {speaker}")
                lines.append(f"  Location: {seminar.location}")
                lines.append(f"  Link: {seminar.url}")
                if seminar.notes:
                    lines.append(f"  Notes: {seminar.notes}")
            lines.append("")
    if errors:
        lines.append("Scrape issues")
        for error in errors:
            lines.append(f"- {error.source_name}: {error.message}")
    return "\n".join(lines).strip() + "\n"


def render_html_digest(
    seminars: list[Seminar],
    now: datetime,
    days: int,
    errors: list[RefreshError] | None = None,
) -> str:
    groups = _group_by_day(seminars)
    cards: list[str] = []
    if not seminars:
        cards.append("<p>No seminars found in this window.</p>")
    else:
        for day, day_seminars in groups.items():
            rows: list[str] = []
            for seminar in day_seminars:
                speaker = escape(seminar.speaker)
                if seminar.speaker_affiliation:
                    speaker = f"{speaker} ({escape(seminar.speaker_affiliation)})"
                note_row = (
                    f"<p class='notes'>{escape(seminar.notes)}</p>" if seminar.notes else ""
                )
                rows.append(
                    (
                        "<article class='seminar'>"
                        f"<p class='meta'>{seminar.start.strftime('%H:%M')} - {seminar.end.strftime('%H:%M')} | "
                        f"{escape(seminar.institution)} | {escape(seminar.series)}</p>"
                        f"<h3>{escape(display_title(seminar))}</h3>"
                        f"<p><strong>Speaker:</strong> {speaker}</p>"
                        f"<p><strong>Location:</strong> {escape(seminar.location)}</p>"
                        f"<p><a href='{escape(seminar.url)}'>Source page</a></p>"
                        f"{note_row}"
                        "</article>"
                    )
                )
            cards.append(f"<section><h2>{escape(day)}</h2>{''.join(rows)}</section>")

    error_block = ""
    if errors:
        issues = "".join(
            f"<li><strong>{escape(item.source_name)}:</strong> {escape(item.message)}</li>"
            for item in errors
        )
        error_block = f"<section><h2>Scrape issues</h2><ul>{issues}</ul></section>"

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>London Economics Seminars</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f4f0e8;
        --card: #fffdf8;
        --ink: #1f2328;
        --muted: #5c6773;
        --accent: #9d2a00;
        --border: #d7c9b8;
      }}
      body {{
        font-family: Georgia, "Times New Roman", serif;
        background: radial-gradient(circle at top, #fff7ea 0%, var(--bg) 65%);
        color: var(--ink);
        margin: 0;
      }}
      main {{
        max-width: 920px;
        margin: 0 auto;
        padding: 32px 18px 48px;
      }}
      h1, h2, h3 {{
        line-height: 1.15;
      }}
      .lede {{
        color: var(--muted);
        margin-bottom: 28px;
      }}
      section {{
        margin-bottom: 28px;
      }}
      .seminar {{
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 16px 18px;
        margin-bottom: 12px;
        box-shadow: 0 10px 24px rgba(45, 33, 19, 0.05);
      }}
      .meta {{
        color: var(--accent);
        font-size: 0.95rem;
        margin-bottom: 6px;
      }}
      .notes {{
        color: var(--muted);
      }}
      a {{
        color: var(--accent);
      }}
    </style>
  </head>
  <body>
    <main>
      <h1>London Economics Seminars</h1>
      <p class="lede">Upcoming seminars and related research events across tracked institutions for the next {days} days. Generated {escape(now.strftime('%d %B %Y %H:%M'))}.</p>
      {''.join(cards)}
      {error_block}
    </main>
  </body>
</html>
"""


def build_digest(snapshot: Snapshot, now: datetime, days: int) -> tuple[str, str, list[Seminar]]:
    seminars = filter_upcoming(snapshot.seminars, now=now, days=days)
    text_body = render_text_digest(seminars, now=now, days=days, errors=snapshot.errors)
    html_body = render_html_digest(seminars, now=now, days=days, errors=snapshot.errors)
    return text_body, html_body, seminars
