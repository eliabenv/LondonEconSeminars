from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from seminar_tracker.calendar_html import build_calendar_html
from seminar_tracker.config import CALENDAR_HTML_PATH, DIGEST_HTML_PATH, INSTITUTIONS, SNAPSHOT_PATH
from seminar_tracker.digest import build_digest, render_text_digest
from seminar_tracker.mailer import send_email, smtp_is_configured
from seminar_tracker.models import Snapshot
from seminar_tracker.site_html import render_site_homepage
from seminar_tracker.sources import refresh_snapshot
from seminar_tracker.storage import (
    load_dotenv,
    load_last_sent_week,
    load_snapshot,
    save_last_sent_week,
    save_snapshot,
    write_text,
)
from seminar_tracker.webapp import serve_dashboard


def _now() -> datetime:
    snapshot = load_snapshot(SNAPSHOT_PATH)
    if snapshot:
        return datetime.now(snapshot.refreshed_at.tzinfo)
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("Europe/London"))


def _refresh_and_save(horizon_days: int) -> Snapshot:
    now = _now()
    snapshot = refresh_snapshot(now=now, horizon_days=horizon_days)
    save_snapshot(snapshot, SNAPSHOT_PATH)
    return snapshot


def _load_or_refresh_snapshot(refresh: bool, horizon_days: int) -> Snapshot:
    snapshot = _refresh_and_save(horizon_days) if refresh else load_snapshot(SNAPSHOT_PATH)
    if snapshot is None:
        snapshot = _refresh_and_save(horizon_days)
    return snapshot


def _resolve_repo_url(explicit_url: str | None) -> str | None:
    if explicit_url:
        return explicit_url.rstrip("/")
    env_url = os.environ.get("SEMINAR_TRACKER_REPO_URL")
    if env_url:
        return env_url.rstrip("/")
    server_url = os.environ.get("GITHUB_SERVER_URL")
    repository = os.environ.get("GITHUB_REPOSITORY")
    if server_url and repository:
        return f"{server_url.rstrip('/')}/{repository}"
    return None


def cmd_refresh(args: argparse.Namespace) -> None:
    snapshot = _refresh_and_save(args.horizon_days)
    print(
        f"Saved {len(snapshot.seminars)} seminars to {SNAPSHOT_PATH} with {len(snapshot.errors)} scrape issues."
    )


def cmd_digest(args: argparse.Namespace) -> None:
    snapshot = _load_or_refresh_snapshot(args.refresh, args.horizon_days)
    now = _now()
    text_body, html_body, seminars = build_digest(snapshot, now=now, days=args.days)
    if args.html_output:
        output_path = DIGEST_HTML_PATH if args.html_output == "default" else Path(args.html_output)
        write_text(output_path, html_body)
    print(text_body)
    print(f"Total upcoming seminars in digest window: {len(seminars)}")


def cmd_send_weekly(args: argparse.Namespace) -> None:
    snapshot = _refresh_and_save(args.horizon_days)
    now = _now()
    week_id = f"{now.isocalendar().year}-W{now.isocalendar().week:02d}"
    if not args.force and load_last_sent_week() == week_id:
        print(f"Weekly digest already sent for {week_id}. Use --force to send again.")
        return

    text_body, html_body, seminars = build_digest(snapshot, now=now, days=args.days)
    write_text(DIGEST_HTML_PATH, html_body)
    if smtp_is_configured():
        subject = f"London economics seminars: next {args.days} days"
        send_email(subject=subject, text_body=text_body, html_body=html_body)
        save_last_sent_week(week_id)
        print(f"Sent weekly digest with {len(seminars)} seminars.")
    else:
        print("SMTP not configured. Wrote the HTML digest locally instead:")
        print(DIGEST_HTML_PATH)
        print()
        print(render_text_digest(seminars, now=now, days=args.days, errors=snapshot.errors))


def cmd_calendar(args: argparse.Namespace) -> None:
    snapshot = _load_or_refresh_snapshot(args.refresh, args.horizon_days)
    now = _now()
    html, seminars = build_calendar_html(
        snapshot,
        now=now,
        days=args.days,
        institution=args.institution,
    )
    output_path = Path(args.output) if args.output else CALENDAR_HTML_PATH
    write_text(output_path, html)
    scope = args.institution or "all institutions"
    print(f"Wrote HTML calendar for {scope} with {len(seminars)} seminars:")
    print(output_path)


def cmd_site(args: argparse.Namespace) -> None:
    snapshot = _load_or_refresh_snapshot(args.refresh, args.horizon_days)
    now = _now()
    output_dir = Path(args.output_dir)
    repo_url = _resolve_repo_url(args.repo_url)
    manual_update_url = f"{repo_url}#manual-update-for-colleagues" if repo_url else None

    calendar_html, calendar_seminars = build_calendar_html(
        snapshot,
        now=now,
        days=args.days,
        home_url="index.html",
        repo_url=repo_url,
        manual_update_url=manual_update_url,
    )
    _, digest_html, digest_seminars = build_digest(snapshot, now=now, days=args.digest_days)
    homepage_html = render_site_homepage(
        last_updated=snapshot.refreshed_at,
        calendar_days=args.days,
        digest_days=args.digest_days,
        calendar_count=len(calendar_seminars),
        digest_count=len(digest_seminars),
        error_count=len(snapshot.errors),
        repo_url=repo_url,
        manual_update_url=manual_update_url,
    )

    write_text(output_dir / "index.html", homepage_html)
    write_text(output_dir / "calendar.html", calendar_html)
    write_text(output_dir / "weekly_digest.html", digest_html)
    write_text(
        output_dir / "seminars.json",
        json.dumps(snapshot.to_dict(), indent=2, sort_keys=True),
    )
    print(
        f"Wrote publishable site with {len(calendar_seminars)} calendar seminars and "
        f"{len(digest_seminars)} digest seminars:"
    )
    print(output_dir)


def cmd_serve(args: argparse.Namespace) -> None:
    def refresh_callback():
        return _refresh_and_save(args.horizon_days)

    if args.refresh_on_start or load_snapshot(SNAPSHOT_PATH) is None:
        refresh_callback()
    serve_dashboard(
        host=args.host,
        port=args.port,
        refresh_callback=refresh_callback,
        snapshot_path=SNAPSHOT_PATH,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Track economics seminars in London.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    refresh_parser = subparsers.add_parser("refresh", help="Fetch seminar listings and save a snapshot.")
    refresh_parser.add_argument("--horizon-days", type=int, default=180)
    refresh_parser.set_defaults(func=cmd_refresh)

    digest_parser = subparsers.add_parser("digest", help="Print a digest for the next few days.")
    digest_parser.add_argument("--days", type=int, default=7)
    digest_parser.add_argument("--refresh", action="store_true")
    digest_parser.add_argument("--horizon-days", type=int, default=180)
    digest_parser.add_argument(
        "--html-output",
        nargs="?",
        const="default",
        default=None,
        help="Optionally write the HTML digest. Omit the path to use the default data file.",
    )
    digest_parser.set_defaults(func=cmd_digest)

    send_parser = subparsers.add_parser("send-weekly", help="Refresh listings and email a weekly digest.")
    send_parser.add_argument("--days", type=int, default=7)
    send_parser.add_argument("--force", action="store_true")
    send_parser.add_argument("--horizon-days", type=int, default=180)
    send_parser.set_defaults(func=cmd_send_weekly)

    calendar_parser = subparsers.add_parser("calendar", help="Write a standalone HTML seminar calendar.")
    calendar_parser.add_argument("--days", type=int, default=60)
    calendar_parser.add_argument("--refresh", action="store_true")
    calendar_parser.add_argument("--horizon-days", type=int, default=180)
    calendar_parser.add_argument("--institution", choices=INSTITUTIONS)
    calendar_parser.add_argument("--output", help="Optional output path for the generated HTML calendar.")
    calendar_parser.set_defaults(func=cmd_calendar)

    site_parser = subparsers.add_parser("site", help="Write a publishable static seminar website.")
    site_parser.add_argument("--days", type=int, default=60)
    site_parser.add_argument("--digest-days", type=int, default=7)
    site_parser.add_argument("--refresh", action="store_true")
    site_parser.add_argument("--horizon-days", type=int, default=180)
    site_parser.add_argument("--output-dir", default="site")
    site_parser.add_argument("--repo-url", help="Optional repository URL for the published site.")
    site_parser.set_defaults(func=cmd_site)

    serve_parser = subparsers.add_parser("serve", help="Serve a local seminar dashboard.")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--refresh-on-start", action="store_true")
    serve_parser.add_argument("--horizon-days", type=int, default=180)
    serve_parser.set_defaults(func=cmd_serve)

    return parser


def main() -> None:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
