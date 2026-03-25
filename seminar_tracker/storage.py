from __future__ import annotations

import json
import os
from pathlib import Path

from seminar_tracker.config import LAST_SENT_PATH, SNAPSHOT_PATH
from seminar_tracker.models import Snapshot


def load_dotenv(path: Path | None = None) -> None:
    env_path = path or Path(".env")
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def save_snapshot(snapshot: Snapshot, path: Path = SNAPSHOT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(snapshot.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def load_snapshot(path: Path = SNAPSHOT_PATH) -> Snapshot | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return Snapshot.from_dict(payload)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def load_last_sent_week(path: Path = LAST_SENT_PATH) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip() or None


def save_last_sent_week(week_id: str, path: Path = LAST_SENT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(week_id, encoding="utf-8")

