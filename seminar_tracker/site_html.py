from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from seminar_tracker.config import DEFAULT_TIMEZONE


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(ZoneInfo(DEFAULT_TIMEZONE)).strftime("%d %B %Y %H:%M %Z")


def render_site_homepage(
    *,
    last_updated: datetime,
    calendar_days: int,
    digest_days: int,
    calendar_count: int,
    digest_count: int,
    error_count: int,
    repo_url: str | None = None,
    manual_update_url: str | None = None,
    title: str = "London Economics Seminar Tracker",
) -> str:
    last_updated_label = escape(_format_timestamp(last_updated))
    status_note = (
        f"{error_count} scrape issue{'s' if error_count != 1 else ''} "
        f"{'was' if error_count == 1 else 'were'} reported in the latest refresh."
        if error_count
        else "All tracked sources refreshed without reported scrape issues."
    )

    repo_links = ""
    if repo_url or manual_update_url:
        link_items: list[str] = []
        if repo_url:
            link_items.append(
                f"<a class='secondary' href='{escape(repo_url)}' target='_blank' rel='noreferrer noopener'>Repository</a>"
            )
        if manual_update_url:
            link_items.append(
                f"<a class='secondary' href='{escape(manual_update_url)}' target='_blank' rel='noreferrer noopener'>How to update</a>"
            )
        repo_links = f"<div class='link-row'>{''.join(link_items)}</div>"

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape(title)}</title>
    <style>
      :root {{
        --bg: #f3ede3;
        --panel: rgba(255, 252, 247, 0.95);
        --ink: #1d2329;
        --muted: #5f6871;
        --line: #d9ccba;
        --accent: #b84f1e;
        --accent-dark: #8f3d16;
        --shadow: rgba(51, 34, 16, 0.09);
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        color: var(--ink);
        font-family: Georgia, "Times New Roman", serif;
        background:
          radial-gradient(circle at top left, rgba(255, 225, 181, 0.74), transparent 30%),
          linear-gradient(180deg, #fcf7ef 0%, var(--bg) 100%);
      }}
      main {{
        max-width: 920px;
        margin: 0 auto;
        padding: 34px 18px 52px;
      }}
      .panel {{
        background: linear-gradient(135deg, rgba(255,255,255,0.84), rgba(255,246,229,0.92));
        border: 1px solid var(--line);
        border-radius: 28px;
        padding: 28px;
        box-shadow: 0 20px 44px var(--shadow);
      }}
      h1 {{
        margin: 0;
        font-size: clamp(2rem, 4vw, 3.1rem);
      }}
      .lede {{
        margin: 14px 0 0;
        color: var(--muted);
        font-size: 1.08rem;
        line-height: 1.55;
      }}
      .meta {{
        margin-top: 18px;
        padding: 14px 16px;
        border-radius: 18px;
        background: rgba(255,255,255,0.76);
        border: 1px solid var(--line);
      }}
      .meta p {{
        margin: 0;
      }}
      .cta-row, .link-row {{
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
        margin-top: 18px;
      }}
      a {{
        text-decoration: none;
      }}
      .primary, .secondary {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 999px;
        padding: 12px 18px;
        font-size: 1rem;
      }}
      .primary {{
        background: var(--accent);
        color: white;
        box-shadow: 0 12px 24px rgba(184, 79, 30, 0.22);
      }}
      .primary:hover {{
        background: var(--accent-dark);
      }}
      .secondary {{
        border: 1px solid var(--line);
        color: var(--ink);
        background: rgba(255,255,255,0.78);
      }}
      .grid {{
        display: grid;
        gap: 14px;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        margin-top: 22px;
      }}
      .card {{
        padding: 18px;
        border-radius: 20px;
        border: 1px solid var(--line);
        background: var(--panel);
        box-shadow: 0 12px 28px var(--shadow);
      }}
      .label {{
        display: block;
        color: var(--muted);
        margin-bottom: 6px;
      }}
      strong {{
        font-size: 1.55rem;
      }}
      .note {{
        margin-top: 24px;
        color: var(--muted);
        line-height: 1.55;
      }}
      @media (max-width: 640px) {{
        main {{ padding: 22px 12px 40px; }}
        .panel {{ border-radius: 22px; padding: 22px; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <section class="panel">
        <h1>{escape(title)}</h1>
        <p class="lede">A shared page for upcoming economics seminars in London. Use the main button below to open the latest calendar view.</p>
        <div class="meta">
          <p><strong>Last updated:</strong> {last_updated_label}</p>
          <p>{escape(status_note)}</p>
        </div>
        <div class="cta-row">
          <a class="primary" href="calendar.html">Open Calendar</a>
          <a class="secondary" href="weekly_digest.html">Weekly Digest</a>
          <a class="secondary" href="seminars.json">Raw Data</a>
        </div>
        {repo_links}
      </section>
      <section class="grid">
        <article class="card">
          <span class="label">Calendar window</span>
          <strong>{calendar_count}</strong>
          <div>seminars in the next {calendar_days} days</div>
        </article>
        <article class="card">
          <span class="label">Weekly digest</span>
          <strong>{digest_count}</strong>
          <div>seminars in the next {digest_days} days</div>
        </article>
        <article class="card">
          <span class="label">Update rhythm</span>
          <strong>Weekly</strong>
          <div>plus manual reruns from the repository</div>
        </article>
      </section>
      <p class="note">GitHub Pages is a static website, so it cannot refresh seminar data instantly every time a visitor clicks without adding delay and extra infrastructure. This page therefore shows the most recent completed refresh and points readers to the repository for manual update instructions.</p>
    </main>
  </body>
</html>
"""
