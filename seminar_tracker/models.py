from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


def _normalize_key_part(value: str) -> str:
    return " ".join(value.lower().split())


@dataclass(slots=True)
class Seminar:
    institution: str
    series: str
    title: str
    speaker: str
    speaker_affiliation: str
    start: datetime
    end: datetime
    location: str
    url: str
    notes: str = ""

    def key(self) -> str:
        return "|".join(
            [
                _normalize_key_part(self.institution),
                _normalize_key_part(self.series),
                _normalize_key_part(self.title),
                _normalize_key_part(self.speaker),
                self.start.isoformat(),
            ]
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "institution": self.institution,
            "series": self.series,
            "title": self.title,
            "speaker": self.speaker,
            "speaker_affiliation": self.speaker_affiliation,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "location": self.location,
            "url": self.url,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, str]) -> "Seminar":
        return cls(
            institution=payload["institution"],
            series=payload["series"],
            title=payload["title"],
            speaker=payload["speaker"],
            speaker_affiliation=payload.get("speaker_affiliation", ""),
            start=datetime.fromisoformat(payload["start"]),
            end=datetime.fromisoformat(payload["end"]),
            location=payload["location"],
            url=payload["url"],
            notes=payload.get("notes", ""),
        )


@dataclass(slots=True)
class RefreshError:
    source_name: str
    url: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "source_name": self.source_name,
            "url": self.url,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, str]) -> "RefreshError":
        return cls(
            source_name=payload["source_name"],
            url=payload["url"],
            message=payload["message"],
        )


@dataclass(slots=True)
class Snapshot:
    refreshed_at: datetime
    seminars: list[Seminar]
    errors: list[RefreshError]

    def to_dict(self) -> dict[str, object]:
        return {
            "refreshed_at": self.refreshed_at.isoformat(),
            "seminars": [seminar.to_dict() for seminar in self.seminars],
            "errors": [error.to_dict() for error in self.errors],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "Snapshot":
        seminars = [Seminar.from_dict(item) for item in payload.get("seminars", [])]
        errors = [RefreshError.from_dict(item) for item in payload.get("errors", [])]
        return cls(
            refreshed_at=datetime.fromisoformat(str(payload["refreshed_at"])),
            seminars=seminars,
            errors=errors,
        )

