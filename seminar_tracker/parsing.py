from __future__ import annotations

import re
from datetime import date, datetime, time
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from seminar_tracker.config import DEFAULT_TIMEZONE


LONDON_TZ = ZoneInfo(DEFAULT_TIMEZONE)
_DASH_TRANSLATION = str.maketrans(
    {
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "\u2212": "-",
    }
)
_QUOTE_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\xa0": " ",
    }
)


def normalize_text(value: str) -> str:
    cleaned = value.translate(_DASH_TRANSLATION).translate(_QUOTE_TRANSLATION)
    return re.sub(r"\s+", " ", cleaned).strip()


def _strip_ordinal_suffixes(value: str) -> str:
    return re.sub(r"\b(\d{1,2})(st|nd|rd|th)\b", r"\1", value, flags=re.IGNORECASE)


class _TextExtractor(HTMLParser):
    _block_tags = {
        "p",
        "div",
        "section",
        "article",
        "header",
        "footer",
        "li",
        "ul",
        "ol",
        "table",
        "tr",
        "td",
        "th",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "br",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._block_tags:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._block_tags:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def text(self) -> str:
        return "".join(self._parts)


class _LinkExtractor(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self._href: str | None = None
        self._parts: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attr_map = dict(attrs)
        href = attr_map.get("href")
        if href:
            self._href = urljoin(self.base_url, href)
            self._parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self._href:
            return
        text = normalize_text("".join(self._parts))
        if text:
            self.links.append((text, self._href))
        self._href = None
        self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._parts.append(data)


def extract_lines(html: str) -> list[str]:
    parser = _TextExtractor()
    parser.feed(html)
    return [normalize_text(line) for line in parser.text().splitlines() if normalize_text(line)]


def extract_links(html: str, base_url: str) -> list[tuple[str, str]]:
    parser = _LinkExtractor(base_url)
    parser.feed(html)
    return parser.links


def strip_tags(fragment: str) -> str:
    parser = _TextExtractor()
    parser.feed(fragment)
    return normalize_text(parser.text())


def extract_table_rows(html: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", html, flags=re.IGNORECASE | re.DOTALL):
        cells = re.findall(
            r"<t[dh]\b[^>]*>(.*?)</t[dh]>",
            row_html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not cells:
            continue
        cleaned = [strip_tags(cell) for cell in cells]
        if any(cleaned):
            rows.append(cleaned)
    return rows


def parse_time_token(token: str) -> time:
    value = normalize_text(token).upper().replace("HRS", "").replace(" ", "")
    value = value.rstrip(".").replace(".", ":")
    if value.endswith(("AM", "PM")):
        for fmt in ("%I:%M%p", "%I%M%p", "%I%p"):
            try:
                return datetime.strptime(value, fmt).time()
            except ValueError:
                continue
    if ":" not in value and value.isdigit():
        if len(value) in {3, 4}:
            value = f"{value[:-2]}:{value[-2:]}"
    return time.fromisoformat(value)


def parse_time_range(value: str) -> tuple[time, time]:
    cleaned = normalize_text(value).replace("hrs", "").replace("HRS", "")
    pieces = re.split(r"\s*-\s*", cleaned)
    if len(pieces) != 2:
        raise ValueError(f"Could not parse time range: {value}")
    if not re.search(r"(AM|PM)$", pieces[0], flags=re.IGNORECASE) and re.search(
        r"(AM|PM)$", pieces[1], flags=re.IGNORECASE
    ):
        meridiem = re.search(r"(AM|PM)$", pieces[1], flags=re.IGNORECASE).group(1)
        pieces[0] = f"{pieces[0]}{meridiem}"
    return parse_time_token(pieces[0]), parse_time_token(pieces[1])


def combine_date_and_times(day: date, start_time: time, end_time: time) -> tuple[datetime, datetime]:
    start = datetime.combine(day, start_time, tzinfo=LONDON_TZ)
    end = datetime.combine(day, end_time, tzinfo=LONDON_TZ)
    return start, end


def parse_date_token(value: str, default_year: int | None = None) -> date:
    cleaned = _strip_ordinal_suffixes(normalize_text(value).rstrip("."))
    formats = [
        "%d %B %Y",
        "%d %b %Y",
        "%d-%b %Y",
        "%d/%m/%y",
        "%d/%m/%Y",
        "%d %B",
        "%d %b",
        "%d-%b",
    ]
    for fmt in formats:
        candidate = cleaned
        if "%Y" not in fmt and default_year is not None:
            candidate = f"{cleaned} {default_year}"
            fmt = f"{fmt} %Y"
        try:
            return datetime.strptime(candidate, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Could not parse date: {value}")


def academic_year_for_month(month: int, academic_start_year: int) -> int:
    return academic_start_year if month >= 8 else academic_start_year + 1


def parse_lse_datetime_range(value: str) -> tuple[datetime, datetime]:
    cleaned = normalize_text(value)
    multi_day = re.match(
        (
            r"^[A-Za-z]+ (?P<d1>\d{1,2}) (?P<m1>[A-Za-z]+) (?P<y1>\d{4}) "
            r"(?P<t1>\d{1,2}:\d{2}) - [A-Za-z]+ (?P<d2>\d{1,2}) "
            r"(?P<m2>[A-Za-z]+) (?P<y2>\d{4}) (?P<t2>\d{1,2}:\d{2})$"
        ),
        cleaned,
    )
    if multi_day:
        first_day = parse_date_token(
            f"{multi_day.group('d1')} {multi_day.group('m1')} {multi_day.group('y1')}"
        )
        second_day = parse_date_token(
            f"{multi_day.group('d2')} {multi_day.group('m2')} {multi_day.group('y2')}"
        )
        start_time = parse_time_token(multi_day.group("t1"))
        end_time = parse_time_token(multi_day.group("t2"))
        return (
            datetime.combine(first_day, start_time, tzinfo=LONDON_TZ),
            datetime.combine(second_day, end_time, tzinfo=LONDON_TZ),
        )

    same_day = re.match(
        (
            r"^[A-Za-z]+ (?P<day>\d{1,2}) (?P<month>[A-Za-z]+) (?P<year>\d{4}) "
            r"(?P<start>\d{1,2}:\d{2}) - (?P<end>\d{1,2}:\d{2})$"
        ),
        cleaned,
    )
    if not same_day:
        raise ValueError(f"Could not parse LSE datetime range: {value}")
    day_value = parse_date_token(
        f"{same_day.group('day')} {same_day.group('month')} {same_day.group('year')}"
    )
    start_time = parse_time_token(same_day.group("start"))
    end_time = parse_time_token(same_day.group("end"))
    return combine_date_and_times(day_value, start_time, end_time)


def parse_ucl_datetime(value: str, default_year: int) -> tuple[datetime, datetime]:
    cleaned = _strip_ordinal_suffixes(normalize_text(value).rstrip("."))
    match = re.match(
        r"^[A-Za-z]+ (?P<day>\d{1,2}) (?P<month>[A-Za-z]+), (?P<times>.+)$",
        cleaned,
    )
    if not match:
        raise ValueError(f"Could not parse UCL datetime line: {value}")
    day_value = parse_date_token(
        f"{match.group('day')} {match.group('month')} {default_year}"
    )
    start_time, end_time = parse_time_range(match.group("times"))
    return combine_date_and_times(day_value, start_time, end_time)


def parse_speaker_and_affiliation(value: str) -> tuple[str, str]:
    cleaned = normalize_text(value).rstrip(".")
    match = re.match(r"^(?P<speaker>.+?) \((?P<affiliation>[^)]+)\)$", cleaned)
    if match:
        return match.group("speaker"), match.group("affiliation")
    return cleaned, ""


def split_series_and_title(value: str) -> tuple[str, str]:
    cleaned = normalize_text(value)
    if ":" not in cleaned:
        return cleaned, ""
    series, title = cleaned.split(":", 1)
    return normalize_text(series), normalize_text(title)


def unique_preserving_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        items.append(value)
    return items
