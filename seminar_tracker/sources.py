from __future__ import annotations

import re
import shutil
import ssl
import subprocess
from datetime import datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from seminar_tracker.config import DEFAULT_HORIZON_DAYS, DEFAULT_USER_AGENT, SOURCE_SPECS, SourceSpec
from seminar_tracker.models import RefreshError, Seminar, Snapshot
from seminar_tracker.parsing import (
    academic_year_for_month,
    combine_date_and_times,
    extract_lines,
    extract_links,
    extract_table_rows,
    normalize_text,
    parse_date_token,
    parse_lse_datetime_range,
    parse_speaker_and_affiliation,
    parse_time_token,
    parse_time_range,
    parse_ucl_datetime,
    split_series_and_title,
    unique_preserving_order,
)


class FetchClient:
    def __init__(self, user_agent: str = DEFAULT_USER_AGENT, timeout_seconds: int = 20) -> None:
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds

    def fetch_html(self, url: str) -> str:
        try:
            return self._fetch_with_urllib(url)
        except URLError as exc:
            if self._looks_like_ssl_issue(exc) and shutil.which("curl"):
                try:
                    return self._fetch_with_curl(url)
                except URLError:
                    return self._fetch_with_insecure_urllib(url)
            if self._looks_like_ssl_issue(exc):
                return self._fetch_with_insecure_urllib(url)
            raise

    def _fetch_with_urllib(self, url: str) -> str:
        return self._fetch_with_urllib_context(url, ssl.create_default_context())

    def _fetch_with_insecure_urllib(self, url: str) -> str:
        insecure_context = ssl._create_unverified_context()
        return self._fetch_with_urllib_context(url, insecure_context)

    def _fetch_with_urllib_context(self, url: str, context: ssl.SSLContext) -> str:
        request = Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "en-GB,en;q=0.9",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Upgrade-Insecure-Requests": "1",
            },
        )
        with urlopen(request, timeout=self.timeout_seconds, context=context) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")

    def _fetch_with_curl(self, url: str) -> str:
        result = subprocess.run(
            [
                "curl",
                "-fsSL",
                "--connect-timeout",
                str(self.timeout_seconds),
                "--max-time",
                str(self.timeout_seconds),
                "--compressed",
                "-A",
                self.user_agent,
                "-H",
                (
                    "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,*/*;q=0.8"
                ),
                "-H",
                "Accept-Language: en-GB,en;q=0.9",
                "-H",
                "Cache-Control: no-cache",
                "-H",
                "Pragma: no-cache",
                "-H",
                "Upgrade-Insecure-Requests: 1",
                url,
            ],
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            raise URLError(f"curl fallback failed for {url}: {stderr}")
        return result.stdout.decode("utf-8", errors="replace")

    @staticmethod
    def _looks_like_ssl_issue(exc: URLError) -> bool:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, ssl.SSLCertVerificationError):
            return True
        return "certificate verify failed" in str(exc).lower()


def _dedupe_and_sort(seminars: list[Seminar]) -> list[Seminar]:
    seen: set[str] = set()
    unique: list[Seminar] = []
    for seminar in sorted(seminars, key=lambda item: item.start):
        key = seminar.key()
        if key in seen:
            continue
        seen.add(key)
        unique.append(seminar)
    return unique


def refresh_snapshot(now: datetime, horizon_days: int = DEFAULT_HORIZON_DAYS) -> Snapshot:
    client = FetchClient()
    seminars: list[Seminar] = []
    errors: list[RefreshError] = []
    earliest = now - timedelta(days=30)
    latest = now + timedelta(days=horizon_days)

    for spec in SOURCE_SPECS:
        parser = _PARSERS[spec.parser_name]
        try:
            html = client.fetch_html(spec.url)
            seminars.extend(parser(spec, html, client, now))
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            errors.append(
                RefreshError(
                    source_name=spec.label,
                    url=spec.url,
                    message=str(exc),
                )
            )

    filtered = [seminar for seminar in seminars if earliest <= seminar.start <= latest]
    return Snapshot(refreshed_at=now, seminars=_dedupe_and_sort(filtered), errors=errors)


def _finalize_seminar(
    institution: str,
    series: str,
    title: str,
    speaker: str,
    speaker_affiliation: str,
    start: datetime,
    end: datetime,
    location: str,
    url: str,
    notes: str = "",
) -> Seminar:
    return Seminar(
        institution=institution,
        series=series,
        title=title,
        speaker=speaker,
        speaker_affiliation=speaker_affiliation,
        start=start,
        end=end,
        location=location,
        url=url,
        notes=notes,
    )


def _parse_lse_biweekly(spec: SourceSpec, html: str, _: FetchClient, __: datetime) -> list[Seminar]:
    lines = extract_lines(html)
    results: list[Seminar] = []
    current: dict[str, object] | None = None
    previous_free_line = ""
    ignore_prefixes = (
        "Below you will find",
        "For the ",
        "View the seminar",
        "Subscribe to",
        "Share",
        "Email a link",
    )
    for line in lines:
        if line.startswith("Date:"):
            if current:
                results.append(
                    _finalize_seminar(
                        institution=spec.institution,
                        series=str(current["series"]),
                        title=str(current["title"]),
                        speaker=str(current.get("speaker", "")),
                        speaker_affiliation=str(current.get("speaker_affiliation", "")),
                        start=current["start"],
                        end=current["end"],
                        location=str(current.get("location", "")),
                        url=spec.url,
                        notes=str(current.get("notes", "")),
                    )
                )
            raw_title = previous_free_line
            series, title = split_series_and_title(raw_title)
            title = title or series
            notes = ""
            if "cancelled" in raw_title.lower():
                notes = "Cancelled"
                title = title.replace("CANCELLED:", "").replace("Cancelled:", "").strip()
            start, end = parse_lse_datetime_range(line.removeprefix("Date:").strip())
            current = {
                "series": series,
                "title": title,
                "start": start,
                "end": end,
                "notes": notes,
            }
            continue

        if current and line.startswith("Speaker:"):
            speaker, speaker_affiliation = parse_speaker_and_affiliation(
                line.removeprefix("Speaker:").strip()
            )
            current["speaker"] = speaker
            current["speaker_affiliation"] = speaker_affiliation
            continue

        if current and line.startswith("Location:"):
            current["location"] = line.removeprefix("Location:").strip()
            continue

        if current and line.startswith("This event"):
            existing = str(current.get("notes", ""))
            current["notes"] = normalize_text(" ".join(part for part in [existing, line] if part))
            continue

        if line.startswith(ignore_prefixes):
            continue
        previous_free_line = line

    if current:
        results.append(
            _finalize_seminar(
                institution=spec.institution,
                series=str(current["series"]),
                title=str(current["title"]),
                speaker=str(current.get("speaker", "")),
                speaker_affiliation=str(current.get("speaker_affiliation", "")),
                start=current["start"],
                end=current["end"],
                location=str(current.get("location", "")),
                url=spec.url,
                notes=str(current.get("notes", "")),
            )
        )
    return results


def _parse_ucl_detail_page(spec: SourceSpec, html: str, page_url: str) -> list[Seminar]:
    lines = extract_lines(html)
    match = re.search(r"/(20\d{2})/", page_url)
    default_year = int(match.group(1)) if match else datetime.now().year
    results: list[Seminar] = []
    current_heading = ""
    current: dict[str, object] | None = None
    in_seminars_section = True

    def commit() -> None:
        nonlocal current
        if not current or "start" not in current or "end" not in current:
            current = None
            return
        results.append(
            _finalize_seminar(
                institution=spec.institution,
                series=str(current.get("series", current_heading)),
                title=str(current.get("title", "")),
                speaker=str(current.get("speaker", "")),
                speaker_affiliation=str(current.get("speaker_affiliation", "")),
                start=current["start"],
                end=current["end"],
                location=str(current.get("location", "")),
                url=page_url,
                notes=str(current.get("notes", "")),
            )
        )
        current = None

    for line in lines:
        if line == "Seminars":
            in_seminars_section = True
            continue
        if line == "Events":
            commit()
            in_seminars_section = False
            continue
        if not in_seminars_section:
            continue

        if line.startswith("Speaker:"):
            if current is None:
                current = {"series": current_heading}
            speaker, speaker_affiliation = parse_speaker_and_affiliation(
                line.removeprefix("Speaker:").strip()
            )
            current["speaker"] = speaker
            current["speaker_affiliation"] = speaker_affiliation
            continue

        if line.startswith("Title:"):
            if current is None:
                current = {"series": current_heading}
            current["title"] = line.removeprefix("Title:").strip().rstrip(".")
            continue

        if line.startswith("Date:"):
            if current is None:
                current = {"series": current_heading}
            try:
                start, end = parse_ucl_datetime(line.removeprefix("Date:").strip(), default_year)
            except ValueError:
                continue
            current["start"] = start
            current["end"] = end
            continue

        if line.startswith("Venue:"):
            if current is None:
                current = {"series": current_heading}
            venue = line.removeprefix("Venue:").strip()
            venue = venue.replace(" - visit the location on a map.", "").strip()
            current["location"] = venue
            continue

        if line.startswith("Further info:"):
            continue

        if line.startswith("Seminar organiser"):
            continue

        if current and "start" in current and "location" in current:
            commit()

        if "Seminar" in line or "Workshop" in line or "Lecture" in line:
            current_heading = line

    commit()
    return results


def _parse_ucl_department(spec: SourceSpec, html: str, client: FetchClient, _: datetime) -> list[Seminar]:
    links = extract_links(html, spec.url)
    detail_urls = unique_preserving_order(
        href
        for _, href in links
        if "economics-announces-research-seminars" in href
    )
    results: list[Seminar] = []
    for href in detail_urls:
        detail_html = client.fetch_html(href)
        results.extend(_parse_ucl_detail_page(spec, detail_html, href))
    return results


def _parse_qmul_event_text(value: str) -> tuple[str, str, str]:
    cleaned = normalize_text(re.sub(r"\[[^\]]+\]", "", value))
    match = re.match(r"^(?P<speaker>.+?) \((?P<affiliation>[^)]+)\) (?P<title>.+)$", cleaned)
    if not match:
        return cleaned, "", ""
    title = match.group("title").replace("Title:", "").strip()
    return match.group("speaker"), match.group("affiliation"), title


def _parse_qmul_external(spec: SourceSpec, html: str, _: FetchClient, __: datetime) -> list[Seminar]:
    results: list[Seminar] = []
    for row in extract_table_rows(html):
        if len(row) < 4:
            continue
        if row[0].lower() == "date" or row[0].lower().startswith("past seminars"):
            continue
        try:
            seminar_day = parse_date_token(row[0])
            start_time, end_time = parse_time_range(row[1])
        except ValueError:
            continue
        start, end = combine_date_and_times(seminar_day, start_time, end_time)
        speaker, speaker_affiliation, title = _parse_qmul_event_text(row[2])
        results.append(
            _finalize_seminar(
                institution=spec.institution,
                series="External seminars",
                title=title,
                speaker=speaker,
                speaker_affiliation=speaker_affiliation,
                start=start,
                end=end,
                location=row[3],
                url=spec.url,
            )
        )
    return results


def _parse_lbs_economics(spec: SourceSpec, html: str, _: FetchClient, __: datetime) -> list[Seminar]:
    lines = extract_lines(html)
    results: list[Seminar] = []
    current_year: int | None = None
    index = 0
    while index < len(lines):
        line = lines[index]
        year_match = re.match(r"^(AUTUMN|SPRING|SUMMER|WINTER) (\d{4})$", line.upper())
        if year_match:
            current_year = int(year_match.group(2))
            index += 1
            continue

        if current_year and re.match(r"^\d{1,2}-[A-Za-z]{3}$", line):
            if index + 5 >= len(lines):
                break
            event_day = parse_date_token(line, default_year=current_year)
            start_time, end_time = parse_time_range(lines[index + 2])
            start, end = combine_date_and_times(event_day, start_time, end_time)
            results.append(
                _finalize_seminar(
                    institution=spec.institution,
                    series=spec.label,
                    title="",
                    speaker=lines[index + 3],
                    speaker_affiliation=lines[index + 4],
                    start=start,
                    end=end,
                    location=lines[index + 5],
                    url=spec.url,
                )
            )
            index += 6
            continue
        index += 1
    return results


def _extract_academic_start_year(html: str, fallback: int) -> int:
    for pattern in (r"(20\d{2})-(20\d{2})", r"(20\d{2})/(20\d{2})"):
        match = re.search(pattern, html)
        if match:
            return int(match.group(1))
    return fallback


def _event_link_map(html: str, base_url: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for text, href in extract_links(html, base_url):
        mapping.setdefault(text, href)
    return mapping


def _default_end_time_for_kind(kind: str, start: datetime) -> datetime:
    if kind.lower() in {"workshop", "conference", "course"}:
        return start + timedelta(hours=8)
    return start + timedelta(hours=1, minutes=30)


def _split_oce_affiliation_and_title(rest: str) -> tuple[str, str]:
    match = re.match(
        (
            r"^(?P<affiliation>.+?(?:School of Economics|Business School|Central Bank|World Bank|"
            r"University College London|Graduate Institute|University|Institute|School|Bank|London|Amsterdam))"
            r"\s+(?P<title>.+)$"
        ),
        rest,
    )
    if match:
        return match.group("affiliation"), match.group("title")
    return "", rest


def _parse_imperial_epp(spec: SourceSpec, html: str, _: FetchClient, now: datetime) -> list[Seminar]:
    lines = extract_lines(html)
    results: list[Seminar] = []
    default_start_time, default_end_time = parse_time_range("13.30 - 14.45")
    note = "Source page does not specify time or venue for 2026 entries; using 13:30-14:45 and unspecified venue."
    for line in lines:
        match = re.match(
            (
                r"^(?:Monday|Tuesday|Wednesday|Thursday|Friday)\s+"
                r"(?P<day>\d{1,2})(?:st|nd|rd|th)?\s+(?P<month>[A-Za-z]+)\s+"
                r"(?P<year>20\d{2,3}),\s*(?P<rest>.+)$"
            ),
            line,
        )
        if not match:
            continue
        year_text = match.group("year")
        year = int(year_text)
        if year_text == "20206":
            year = 2026
        if year < now.year - 1:
            continue
        event_day = parse_date_token(f"{match.group('day')} {match.group('month')} {year}")
        rest = normalize_text(match.group("rest"))
        speaker_match = re.match(
            r"^(?P<speaker>.+?)\s*\((?P<affiliation>[^)]+)\)\s*,?\s*(?P<title>.+)$",
            rest,
        )
        if not speaker_match:
            continue
        start, end = combine_date_and_times(event_day, default_start_time, default_end_time)
        results.append(
            _finalize_seminar(
                institution=spec.institution,
                series=spec.label,
                title=speaker_match.group("title"),
                speaker=speaker_match.group("speaker"),
                speaker_affiliation=speaker_match.group("affiliation"),
                start=start,
                end=end,
                location="Imperial Business School (venue not specified)",
                url=spec.url,
                notes=note,
            )
        )
    return results


def _parse_ifs_events(spec: SourceSpec, html: str, _: FetchClient, __: datetime) -> list[Seminar]:
    lines = extract_lines(html)
    links = _event_link_map(html, spec.url)
    results: list[Seminar] = []
    in_upcoming = False
    index = 0
    while index < len(lines):
        line = lines[index]
        if line == "All upcoming events":
            in_upcoming = True
            index += 1
            continue
        if line == "All past events":
            break
        if not in_upcoming:
            index += 1
            continue

        if index + 1 >= len(lines):
            break
        next_line = lines[index + 1]
        match = re.match(
            (
                r"^(?P<kind>Event|Workshop|Conference|Course)\s+"
                r"(?P<day>\d{1,2})\s+(?P<month>[A-Za-z]+)\s+(?P<year>\d{4})\s+"
                r"at\s+(?P<time>\d{1,2}:\d{2})(?:\s+(?P<location>.+))?$"
            ),
            next_line,
        )
        if not match:
            index += 1
            continue
        title = line
        event_day = parse_date_token(
            f"{match.group('day')} {match.group('month')} {match.group('year')}"
        )
        start_time = parse_time_token(match.group("time"))
        start, _ = combine_date_and_times(event_day, start_time, start_time)
        end = _default_end_time_for_kind(match.group("kind"), start)
        location = match.group("location") or "IFS / venue not specified"
        description = lines[index + 2] if index + 2 < len(lines) else ""
        note = f"{match.group('kind')} listing from IFS events page."
        if description:
            note = f"{note} {description}"
        results.append(
            _finalize_seminar(
                institution=spec.institution,
                series=f"IFS {match.group('kind')}",
                title=title,
                speaker="",
                speaker_affiliation="",
                start=start,
                end=end,
                location=location,
                url=links.get(title, spec.url),
                notes=note,
            )
        )
        index += 3
    return results


def _parse_oce_ebrd_event(spec: SourceSpec, html: str, _: FetchClient, __: datetime) -> list[Seminar]:
    lines = extract_lines(html)
    title = ""
    date_line = ""
    location = ""
    keynote = ""
    for idx, line in enumerate(lines):
        if line.startswith("8th EBRD and CEPR Research Symposium"):
            title = line
        elif line == "Date" and idx + 1 < len(lines):
            date_line = lines[idx + 1]
        elif line == "Location" and idx + 1 < len(lines):
            location = lines[idx + 1]
        elif "keynote speech by" in line.lower():
            keynote = line

    if not title or not date_line:
        return []

    match = re.match(
        r"^(?P<day1>\d{1,2})\s*-\s*(?P<day2>\d{1,2})\s+(?P<month>[A-Za-z]+)\s+(?P<year>\d{4})$",
        date_line,
    )
    if not match:
        raise ValueError(f"Could not parse OCE-EBRD event date: {date_line}")
    start_day = parse_date_token(f"{match.group('day1')} {match.group('month')} {match.group('year')}")
    end_day = parse_date_token(f"{match.group('day2')} {match.group('month')} {match.group('year')}")
    start, _ = combine_date_and_times(start_day, parse_time_token("09:00"), parse_time_token("17:00"))
    _, end = combine_date_and_times(end_day, parse_time_token("09:00"), parse_time_token("17:00"))
    affiliation = ""
    if keynote:
        keynote_match = re.search(r"keynote speech by (.+)$", keynote, flags=re.IGNORECASE)
        if keynote_match:
            affiliation = keynote_match.group(1).rstrip(".")
    return [
        _finalize_seminar(
            institution=spec.institution,
            series=spec.label,
            title=title,
            speaker="Multiple speakers",
            speaker_affiliation=affiliation,
            start=start,
            end=end,
            location=location or "EBRD HQ",
            url=spec.url,
            notes="Multi-day symposium. Source page does not specify session start/end times; using 09:00-17:00 placeholders.",
        )
    ]


def _parse_oce_series(spec: SourceSpec, html: str, _: FetchClient, __: datetime) -> list[Seminar]:
    lines = extract_lines(html)
    results: list[Seminar] = []
    for line in lines:
        if "GMT" not in line or "," not in line:
            continue
        match = re.match(
            (
                r"^(?P<speaker>.+?),\s+(?P<rest>.+?)\s*"
                r"(?:(?:Monday|Tuesday|Wednesday|Thursday|Friday)\s+)?"
                r"(?P<date>\d{2}/\d{2}/\d{2,4}),\s*(?P<time>\d{1,2}(?::\d{2})?\s*[ap]m)\s+GMT$"
            ),
            line,
            flags=re.IGNORECASE,
        )
        if not match:
            continue
        event_day = parse_date_token(match.group("date"))
        start_time = parse_time_token(match.group("time"))
        start, _ = combine_date_and_times(event_day, start_time, start_time)
        end = start + timedelta(hours=1)
        affiliation, title = _split_oce_affiliation_and_title(normalize_text(match.group("rest")))
        results.append(
            _finalize_seminar(
                institution=spec.institution,
                series=spec.label,
                title=title,
                speaker=match.group("speaker"),
                speaker_affiliation=affiliation,
                start=start,
                end=end,
                location="OCE / venue not specified",
                url=spec.url,
                notes="Time sourced from the seminar-series page. Venue is not specified on the page.",
            )
        )
    return results


def _parse_kcl_kbs(spec: SourceSpec, html: str, _: FetchClient, now: datetime) -> list[Seminar]:
    lines = extract_lines(html)
    academic_start_year = _extract_academic_start_year(html, now.year if now.month >= 8 else now.year - 1)
    default_start_time, default_end_time = parse_time_range("14.00-15.15")
    default_location = "(SE)2.09"
    results: list[Seminar] = []
    for line in lines:
        match = re.match(r"^(?P<date>\d{1,2} [A-Za-z]+)\s*[:\-]\s*(?P<rest>.+)$", line)
        if not match:
            continue
        date_part = match.group("date")
        rest = match.group("rest")
        day_guess = parse_date_token(date_part, default_year=academic_start_year)
        year = academic_year_for_month(day_guess.month, academic_start_year)
        event_day = parse_date_token(date_part, default_year=year)
        title = ""
        notes = ""
        speaker_chunk = normalize_text(rest).rstrip(".")
        if " - " in speaker_chunk:
            speaker_chunk, title = speaker_chunk.split(" - ", 1)
        if ", held jointly with" in speaker_chunk:
            speaker_chunk, joint_note = speaker_chunk.split(", held jointly with", 1)
            notes = f"Held jointly with {joint_note.strip()}"
        speaker, speaker_affiliation = parse_speaker_and_affiliation(speaker_chunk)
        start, end = combine_date_and_times(event_day, default_start_time, default_end_time)
        results.append(
            _finalize_seminar(
                institution=spec.institution,
                series=spec.label,
                title=title,
                speaker=speaker,
                speaker_affiliation=speaker_affiliation,
                start=start,
                end=end,
                location=default_location,
                url=spec.url,
                notes=notes,
            )
        )
    return results


def _parse_kcl_brownbag(spec: SourceSpec, html: str, _: FetchClient, now: datetime) -> list[Seminar]:
    lines = extract_lines(html)
    academic_start_year = _extract_academic_start_year(html, now.year if now.month >= 8 else now.year - 1)
    results: list[Seminar] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if "Reading week" in line or line.startswith("Semester"):
            index += 1
            continue
        match = re.match(
            r"^(?P<date>\d{1,2} [A-Za-z]+), (?P<location>.+), (?P<times>\d{1,2}\.\d{2} - \d{1,2}\.\d{2})$",
            line,
        )
        if not match:
            index += 1
            continue
        day_guess = parse_date_token(match.group("date"), default_year=academic_start_year)
        year = academic_year_for_month(day_guess.month, academic_start_year)
        event_day = parse_date_token(match.group("date"), default_year=year)
        start_time, end_time = parse_time_range(match.group("times"))
        start, end = combine_date_and_times(event_day, start_time, end_time)
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        speaker_info, title = re.split(r"\s*-\s+", next_line, maxsplit=1) if re.search(r"\s*-\s+", next_line) else (next_line, "")
        speaker, speaker_affiliation = parse_speaker_and_affiliation(speaker_info)
        results.append(
            _finalize_seminar(
                institution=spec.institution,
                series=spec.label,
                title=title,
                speaker=speaker,
                speaker_affiliation=speaker_affiliation,
                start=start,
                end=end,
                location=match.group("location"),
                url=spec.url,
            )
        )
        index += 2
    return results


_PARSERS = {
    "lse_biweekly": _parse_lse_biweekly,
    "ucl_department": _parse_ucl_department,
    "qmul_external": _parse_qmul_external,
    "lbs_economics": _parse_lbs_economics,
    "kcl_kbs": _parse_kcl_kbs,
    "kcl_brownbag": _parse_kcl_brownbag,
    "imperial_epp": _parse_imperial_epp,
    "ifs_events": _parse_ifs_events,
    "oce_ebrd_event": _parse_oce_ebrd_event,
    "oce_series": _parse_oce_series,
}
