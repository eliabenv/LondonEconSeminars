from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
SNAPSHOT_PATH = DATA_DIR / "seminars.json"
DIGEST_HTML_PATH = DATA_DIR / "weekly_digest_latest.html"
CALENDAR_HTML_PATH = DATA_DIR / "seminar_calendar_latest.html"
LAST_SENT_PATH = DATA_DIR / "last_sent_week.txt"

DEFAULT_TIMEZONE = "Europe/London"
DEFAULT_HORIZON_DAYS = 180
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36"
)
INSTITUTIONS: tuple[str, ...] = (
    "LSE",
    "UCL",
    "QMUL",
    "LBS",
    "KCL",
    "Imperial",
    "IFS",
    "OCE-EBRD",
)


@dataclass(frozen=True, slots=True)
class SourceSpec:
    key: str
    institution: str
    label: str
    url: str
    parser_name: str


SOURCE_SPECS: tuple[SourceSpec, ...] = (
    SourceSpec(
        key="lse",
        institution="LSE",
        label="Biweekly Research Seminars and Workshops",
        url="https://www.lse.ac.uk/economics/events-and-seminars/biweekly-research-seminars-and-workshops",
        parser_name="lse_biweekly",
    ),
    SourceSpec(
        key="ucl",
        institution="UCL",
        label="Department of Economics Seminars",
        url="https://www.ucl.ac.uk/social-historical-sciences/economics/events/seminars",
        parser_name="ucl_department",
    ),
    SourceSpec(
        key="qmul",
        institution="QMUL",
        label="School of Economics and Finance External Seminars",
        url="https://www.qmul.ac.uk/sef/events/seminars/",
        parser_name="qmul_external",
    ),
    SourceSpec(
        key="lbs",
        institution="LBS",
        label="Economics Seminar Series",
        url="https://www.london.edu/faculty-and-research/economics/economics-seminars",
        parser_name="lbs_economics",
    ),
    SourceSpec(
        key="kcl_kbs",
        institution="KCL",
        label="King's Business School Seminars in Economics",
        url="https://www.kcl.ac.uk/events/series/kings-business-school-seminar-in-economics",
        parser_name="kcl_kbs",
    ),
    SourceSpec(
        key="kcl_brownbag",
        institution="KCL",
        label="Economics Brownbag Seminar Series",
        url="https://www.kcl.ac.uk/events/series/economics-brownbag-seminar-series",
        parser_name="kcl_brownbag",
    ),
    SourceSpec(
        key="imperial_epp",
        institution="Imperial",
        label="Economics & Public Policy Seminars",
        url="https://www.imperial.ac.uk/business-school/faculty-research/academic-areas/economics-public-policy/news-and-events/seminars/",
        parser_name="imperial_epp",
    ),
    SourceSpec(
        key="ifs_events",
        institution="IFS",
        label="Institute for Fiscal Studies Events",
        url="https://ifs.org.uk/events",
        parser_name="ifs_events",
    ),
    SourceSpec(
        key="oce_ebrd",
        institution="OCE-EBRD",
        label="OCE Research Seminars",
        url="https://loiaconofrancesco.com/oce-research-seminars/",
        parser_name="oce_series",
    ),
)
