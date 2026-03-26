from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, datetime, timedelta
from html import escape
from typing import Iterable
from zoneinfo import ZoneInfo

from seminar_tracker.config import DEFAULT_TIMEZONE
from seminar_tracker.digest import display_title, filter_upcoming
from seminar_tracker.models import RefreshError, Seminar, Snapshot


_INSTITUTION_CLASS = {
    "LSE": "lse",
    "UCL": "ucl",
    "QMUL": "qmul",
    "LBS": "lbs",
    "KCL": "kcl",
    "Imperial": "imperial",
    "IFS": "ifs",
    "OCE-EBRD": "oce",
}

_SERIES_SHORT_NAMES = {
    "CEP/STICERD Applications Seminars": "CEP/STICERD Apps",
    "Labour Economics Workshops": "Labour Econ",
    "Labour and Education Seminars": "Labour & Education",
    "Political Economy Research Seminar": "Political Economy",
    "Hayek Programme Online Webinar Series": "Hayek Webinar",
    "STICERD Public Events and Lectures": "STICERD Public",
    "International Economics Workshops": "International Econ",
    "Trade and Urban Seminars": "Trade & Urban",
    "Capabilities, Competition and Innovation Seminars": "CCI",
    "IFS/STICERD/UCL Development Work in Progress Seminar": "Development WIP",
    "STICERD Econometrics Seminar Series": "Econometrics",
    "STICERD Economic Theory Seminars": "Theory",
    "Wellbeing Seminars": "Wellbeing",
    "European Seminars on the Economics of Crime (ESEC)": "ESEC",
    "Cohesive Capitalism Event": "Cohesive Capitalism",
    "External seminars": "External",
    "King's Business School Seminars in Economics": "KBS Econ",
    "Economics Brownbag Seminar Series": "Brownbag",
    "Department of Economics Seminars": "UCL Econ",
    "Economics Seminar Series": "LBS Econ",
    "Economics & Public Policy Seminars": "EPP",
    "Institute for Fiscal Studies Events": "IFS Events",
    "IFS Event": "IFS Event",
    "IFS Workshop": "IFS Workshop",
    "IFS Conference": "IFS Conf",
    "IFS Course": "IFS Course",
    "OCE-EBRD Research Symposium": "OCE-EBRD",
    "OCE Research Seminars": "OCE Seminar",
}


def _month_starts_between(start_day: date, end_day: date) -> list[date]:
    months: list[date] = []
    current = date(start_day.year, start_day.month, 1)
    last = date(end_day.year, end_day.month, 1)
    while current <= last:
        months.append(current)
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return months


def _group_by_day(seminars: Iterable[Seminar]) -> dict[date, list[Seminar]]:
    grouped: dict[date, list[Seminar]] = defaultdict(list)
    for seminar in seminars:
        grouped[seminar.start.date()].append(seminar)
    for day in grouped:
        grouped[day].sort(key=lambda item: item.start)
    return grouped


def _short_series_label(series: str) -> str:
    if series in _SERIES_SHORT_NAMES:
        return _SERIES_SHORT_NAMES[series]
    compact = series
    replacements = {
        "Seminars": "",
        "Seminar": "",
        "Series": "",
        "Workshops": "Workshop",
        "Economics": "Econ",
        "Research": "Res",
    }
    for old, new in replacements.items():
        compact = compact.replace(old, new)
    compact = " ".join(compact.split()).strip(" -")
    return compact or series


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(ZoneInfo(DEFAULT_TIMEZONE)).strftime("%d %B %Y %H:%M %Z")


def _render_calendar_event(seminar: Seminar) -> str:
    event_class = _INSTITUTION_CLASS.get(seminar.institution, "other")
    return (
        f"<a class='event {event_class}' href='{escape(seminar.url)}' target='_blank' rel='noreferrer noopener'>"
        f"<span class='event-time'>{escape(seminar.start.strftime('%H:%M'))}</span>"
        f"<span class='event-inst'>{escape(seminar.institution)}</span>"
        f"<span class='event-series'>{escape(_short_series_label(seminar.series))}</span>"
        f"<span class='event-title'>{escape(display_title(seminar))}</span>"
        "</a>"
    )


def _render_month(month_start: date, by_day: dict[date, list[Seminar]], focus_days: set[date]) -> str:
    cal = calendar.Calendar(firstweekday=0)
    week_rows: list[str] = []
    for week in cal.monthdatescalendar(month_start.year, month_start.month):
        day_cells: list[str] = []
        for day in week:
            seminars = by_day.get(day, [])
            is_current = day.month == month_start.month
            is_focus = day in focus_days
            classes = ["day"]
            if not is_current:
                classes.append("day-muted")
            if seminars:
                classes.append("day-has-events")
            if is_focus:
                classes.append("day-in-window")
            visible_items = seminars
            overflow = ""
            if len(seminars) > 4:
                toggle_id = f"day-{day.isoformat()}"
                visible_items = seminars[:4]
                hidden_html = "".join(_render_calendar_event(item) for item in seminars[4:])
                overflow = (
                    f"<div class='day-events-hidden' id='{toggle_id}' hidden>{hidden_html}</div>"
                    f"<button type='button' class='overflow-toggle' data-target='{toggle_id}' "
                    f"data-count='{len(seminars) - 4}' aria-expanded='false'>+{len(seminars) - 4} more</button>"
                )
            seminar_html = "".join(_render_calendar_event(item) for item in visible_items) + overflow
            day_cells.append(
                (
                    f"<div class='{' '.join(classes)}'>"
                    f"<div class='day-header'><span class='day-number'>{day.day}</span></div>"
                    f"<div class='day-events'>{seminar_html}</div>"
                    "</div>"
                )
            )
        week_rows.append(f"<div class='week'>{''.join(day_cells)}</div>")

    return (
        "<section class='month'>"
        f"<div class='month-title'>{escape(month_start.strftime('%B %Y'))}</div>"
        "<div class='weekdays'>"
        "<div>Mon</div><div>Tue</div><div>Wed</div><div>Thu</div><div>Fri</div><div>Sat</div><div>Sun</div>"
        "</div>"
        f"{''.join(week_rows)}"
        "</section>"
    )


def _render_agenda(seminars: list[Seminar]) -> str:
    if not seminars:
        return "<p class='empty'>No seminars found in this window.</p>"

    groups: dict[str, list[Seminar]] = defaultdict(list)
    for seminar in seminars:
        groups[seminar.start.strftime("%A %d %B %Y")].append(seminar)

    sections: list[str] = []
    for day, items in groups.items():
        cards = []
        for seminar in items:
            speaker = escape(seminar.speaker)
            if seminar.speaker_affiliation:
                speaker = f"{speaker} ({escape(seminar.speaker_affiliation)})"
            notes = f"<p class='agenda-notes'>{escape(seminar.notes)}</p>" if seminar.notes else ""
            cards.append(
                (
                    "<article class='agenda-card'>"
                    f"<p class='agenda-meta'>{escape(seminar.start.strftime('%H:%M'))} - "
                    f"{escape(seminar.end.strftime('%H:%M'))} | {escape(seminar.institution)} | "
                    f"{escape(seminar.series)}</p>"
                    f"<h3>{escape(display_title(seminar))}</h3>"
                    f"<p><strong>Speaker:</strong> {speaker}</p>"
                    f"<p><strong>Location:</strong> {escape(seminar.location)}</p>"
                    f"<p><a href='{escape(seminar.url)}' target='_blank' rel='noreferrer noopener'>Source page</a></p>"
                    f"{notes}"
                    "</article>"
                )
            )
        sections.append(f"<section class='agenda-group'><h2>{escape(day)}</h2>{''.join(cards)}</section>")
    return "".join(sections)


def render_calendar_html(
    seminars: list[Seminar],
    now: datetime,
    days: int,
    errors: list[RefreshError] | None = None,
    institution: str | None = None,
    title: str = "London Economics Seminar Calendar",
    snapshot_refreshed_at: datetime | None = None,
    home_url: str | None = None,
    repo_url: str | None = None,
    manual_update_url: str | None = None,
) -> str:
    end = now + timedelta(days=days)
    by_day = _group_by_day(seminars)
    focus_days = {
        now.date() + timedelta(days=offset)
        for offset in range((end.date() - now.date()).days + 1)
    }
    month_starts = _month_starts_between(now.date().replace(day=1), end.date().replace(day=1))
    month_sections = "".join(_render_month(month_start, by_day, focus_days) for month_start in month_starts)
    agenda_html = _render_agenda(seminars)

    issues = ""
    if errors:
        items = "".join(
            f"<li><strong>{escape(error.source_name)}:</strong> {escape(error.message)}</li>"
            for error in errors
        )
        issues = f"<section class='issues'><h2>Scrape Issues</h2><ul>{items}</ul></section>"

    subtitle = (
        f"{escape(institution)} seminars from {escape(now.strftime('%d %b %Y'))} "
        f"to {escape(end.strftime('%d %b %Y'))}"
        if institution
        else f"Seminars from {escape(now.strftime('%d %b %Y'))} to {escape(end.strftime('%d %b %Y'))}"
    )
    last_updated = snapshot_refreshed_at or now
    nav_links: list[str] = []
    if home_url:
        nav_links.append(f"<a href='{escape(home_url)}'>Home</a>")
    if repo_url:
        nav_links.append(
            f"<a href='{escape(repo_url)}' target='_blank' rel='noreferrer noopener'>Repository</a>"
        )
    if manual_update_url:
        nav_links.append(
            f"<a href='{escape(manual_update_url)}' target='_blank' rel='noreferrer noopener'>How to update</a>"
        )
    actions_html = (
        f"<div class='hero-links'>{''.join(nav_links)}</div>"
        if nav_links
        else ""
    )

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape(title)}</title>
    <style>
      :root {{
        --bg: #efe7d9;
        --panel: rgba(255, 252, 246, 0.94);
        --ink: #1d2329;
        --muted: #606a74;
        --line: #d8ccb9;
        --shadow: rgba(42, 27, 11, 0.08);
        --accent: #bb4d1f;
        --lse: #8f1d2c;
        --ucl: #005f92;
        --qmul: #9b1c45;
        --lbs: #244f3d;
        --kcl: #4b2d73;
        --imperial: #0f5f74;
        --ifs: #7a5a11;
        --oce: #6a2146;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        color: var(--ink);
        font-family: Georgia, "Times New Roman", serif;
        background:
          radial-gradient(circle at top left, rgba(255, 233, 194, 0.78), transparent 32%),
          radial-gradient(circle at top right, rgba(188, 84, 34, 0.08), transparent 24%),
          linear-gradient(180deg, #faf4ea 0%, var(--bg) 100%);
      }}
      main {{
        max-width: 1240px;
        margin: 0 auto;
        padding: 30px 18px 56px;
      }}
      .hero {{
        background: linear-gradient(135deg, rgba(255,255,255,0.76), rgba(255,245,227,0.9));
        border: 1px solid var(--line);
        border-radius: 28px;
        padding: 24px;
        box-shadow: 0 18px 40px var(--shadow);
      }}
      .lede {{
        color: var(--muted);
        max-width: 760px;
        margin: 8px 0 0;
      }}
      .legend {{
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        margin-top: 18px;
      }}
      .hero-links {{
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        margin-top: 16px;
      }}
      .hero-links a {{
        text-decoration: none;
        color: var(--ink);
        border: 1px solid var(--line);
        border-radius: 999px;
        padding: 8px 12px;
        background: rgba(255,255,255,0.8);
      }}
      .legend span {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        border: 1px solid var(--line);
        border-radius: 999px;
        background: rgba(255,255,255,0.8);
        font-size: 0.95rem;
      }}
      .legend i {{
        width: 10px;
        height: 10px;
        display: inline-block;
        border-radius: 999px;
      }}
      .calendar-wrap {{
        margin-top: 24px;
        display: grid;
        gap: 24px;
      }}
      .month {{
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 24px;
        padding: 18px;
        box-shadow: 0 10px 26px var(--shadow);
      }}
      .month-title {{
        font-size: 1.5rem;
        margin-bottom: 14px;
      }}
      .weekdays, .week {{
        display: grid;
        grid-template-columns: repeat(7, minmax(0, 1fr));
      }}
      .weekdays {{
        color: var(--muted);
        margin-bottom: 8px;
        font-size: 0.92rem;
      }}
      .weekdays div {{
        padding: 10px 8px;
      }}
      .day {{
        min-height: 156px;
        padding: 10px;
        border: 1px solid rgba(216, 204, 185, 0.9);
        background: rgba(255,255,255,0.74);
      }}
      .day-muted {{
        opacity: 0.42;
        background: rgba(244, 239, 231, 0.85);
      }}
      .day-in-window {{
        background: rgba(255, 249, 240, 0.96);
      }}
      .day-has-events {{
        box-shadow: inset 0 0 0 1px rgba(187, 77, 31, 0.12);
      }}
      .day-header {{
        display: flex;
        justify-content: flex-end;
        margin-bottom: 8px;
      }}
      .day-number {{
        font-size: 0.96rem;
        color: var(--muted);
      }}
      .day-events {{
        display: grid;
        gap: 6px;
      }}
      .event {{
        display: grid;
        gap: 2px;
        text-decoration: none;
        color: white;
        border-radius: 12px;
        padding: 8px 9px;
        font-size: 0.82rem;
        line-height: 1.15;
        box-shadow: 0 8px 18px rgba(36, 29, 24, 0.16);
      }}
      .event:hover {{
        transform: translateY(-1px);
      }}
      .event-time {{
        font-weight: 700;
        opacity: 0.92;
      }}
      .event-inst {{
        font-size: 0.72rem;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        opacity: 0.85;
      }}
      .event-title {{
        display: -webkit-box;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }}
      .event-series {{
        font-size: 0.7rem;
        letter-spacing: 0.03em;
        opacity: 0.88;
      }}
      .event.lse {{ background: linear-gradient(135deg, var(--lse), #b12d41); }}
      .event.ucl {{ background: linear-gradient(135deg, var(--ucl), #2586ba); }}
      .event.qmul {{ background: linear-gradient(135deg, var(--qmul), #c03969); }}
      .event.lbs {{ background: linear-gradient(135deg, var(--lbs), #42705c); }}
      .event.kcl {{ background: linear-gradient(135deg, var(--kcl), #6c479a); }}
      .event.imperial {{ background: linear-gradient(135deg, var(--imperial), #2a8ea6); }}
      .event.ifs {{ background: linear-gradient(135deg, var(--ifs), #a67d1d); }}
      .event.oce {{ background: linear-gradient(135deg, var(--oce), #8d3564); }}
      .event.other {{ background: linear-gradient(135deg, #4d5967, #798594); }}
      .day-events-hidden {{
        display: grid;
        gap: 6px;
        margin-top: 6px;
      }}
      .overflow-toggle {{
        border: 0;
        background: transparent;
        color: var(--accent);
        font: inherit;
        text-align: left;
        padding: 2px 2px 0;
        cursor: pointer;
      }}
      .overflow-toggle:hover {{
        text-decoration: underline;
      }}
      .overflow {{
        color: var(--muted);
        font-size: 0.8rem;
        padding: 2px 2px 0;
      }}
      .agenda {{
        margin-top: 26px;
      }}
      .agenda-group {{
        margin-bottom: 24px;
      }}
      .agenda-card {{
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 16px 18px;
        margin-bottom: 12px;
        box-shadow: 0 10px 24px var(--shadow);
      }}
      .agenda-meta {{
        color: var(--accent);
        font-size: 0.94rem;
      }}
      .agenda-notes {{
        color: var(--muted);
      }}
      .issues {{
        margin-top: 24px;
        padding: 18px;
        border-radius: 18px;
        border: 1px solid #d9b9aa;
        background: rgba(255, 242, 237, 0.9);
      }}
      .empty {{
        color: var(--muted);
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 18px;
      }}
      @media (max-width: 980px) {{
        .weekdays, .week {{
          grid-template-columns: repeat(7, minmax(120px, 1fr));
          min-width: 860px;
        }}
        .month {{
          overflow-x: auto;
        }}
      }}
      @media (max-width: 640px) {{
        main {{ padding: 20px 12px 44px; }}
        .hero {{ border-radius: 22px; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <h1>{escape(title)}</h1>
        <p class="lede">{subtitle}. Last updated {escape(_format_timestamp(last_updated))}.</p>
        {actions_html}
        <div class="legend">
          <span><i style="background: var(--lse)"></i>LSE</span>
          <span><i style="background: var(--ucl)"></i>UCL</span>
          <span><i style="background: var(--qmul)"></i>QMUL</span>
          <span><i style="background: var(--lbs)"></i>LBS</span>
          <span><i style="background: var(--kcl)"></i>KCL</span>
          <span><i style="background: var(--imperial)"></i>Imperial</span>
          <span><i style="background: var(--ifs)"></i>IFS</span>
          <span><i style="background: var(--oce)"></i>OCE-EBRD</span>
        </div>
      </section>
      <section class="calendar-wrap">
        {month_sections}
      </section>
      <section class="agenda">
        <h2>Agenda</h2>
        {agenda_html}
      </section>
      {issues}
    </main>
    <script>
      document.addEventListener("click", function (event) {{
        const button = event.target.closest(".overflow-toggle");
        if (!button) {{
          return;
        }}
        const target = document.getElementById(button.dataset.target);
        if (!target) {{
          return;
        }}
        const expanded = button.getAttribute("aria-expanded") === "true";
        target.hidden = expanded;
        button.setAttribute("aria-expanded", String(!expanded));
        button.textContent = expanded ? `+${{button.dataset.count}} more` : "show less";
      }});
    </script>
  </body>
</html>
"""


def build_calendar_html(
    snapshot: Snapshot,
    now: datetime,
    days: int,
    institution: str | None = None,
    home_url: str | None = None,
    repo_url: str | None = None,
    manual_update_url: str | None = None,
) -> tuple[str, list[Seminar]]:
    seminars = filter_upcoming(snapshot.seminars, now=now, days=days, institution=institution)
    html = render_calendar_html(
        seminars,
        now=now,
        days=days,
        errors=snapshot.errors,
        institution=institution,
        snapshot_refreshed_at=snapshot.refreshed_at,
        home_url=home_url,
        repo_url=repo_url,
        manual_update_url=manual_update_url,
    )
    return html, seminars
