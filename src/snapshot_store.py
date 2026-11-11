"""Select, cache, and describe the public stock snapshot."""

from __future__ import annotations

import json
import os
import re
import threading
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .config import COLLECTION_STATUS, PUBLIC_SNAPSHOT, RAW_DIR, Config
from .transform.snapshot import normalize_stock


def read_json(path: Path) -> dict:
    """Read a JSON object, returning an empty mapping for missing or invalid data."""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def search_key(value: str) -> str:
    """Build an accent- and case-insensitive key used by search filters."""
    decomposed = unicodedata.normalize("NFKD", str(value).casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def raw_collection_time(raw_path: Path) -> str:
    """Read a capture timestamp from its filename or filesystem metadata."""
    match = re.fullmatch(r"vivver_estoque_(.+)\.txt", raw_path.name)
    if match:
        timestamp = match.group(1)
        for timestamp_format in ("%Y-%m-%dT%H%M%S%fZ", "%Y-%m-%dT%H%M%S%f%z"):
            try:
                parsed = datetime.strptime(timestamp, timestamp_format)
            except ValueError:
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat()

    return datetime.fromtimestamp(raw_path.stat().st_mtime, timezone.utc).isoformat()


def raw_sort_time(raw_path: Path) -> float:
    """Convert a capture timestamp to a sortable UTC epoch value."""
    if raw_path.stem.casefold().endswith("_fixture"):
        return 0.0
    try:
        return datetime.fromisoformat(raw_collection_time(raw_path)).timestamp()
    except (OSError, ValueError):
        return 0.0


def is_fixture_capture(path: Path, status: dict) -> bool:
    """Identify local demo data so it is never mistaken for a live capture."""
    if not isinstance(status, dict):
        status = {}
    if path.stem.casefold().endswith("_fixture"):
        return True

    source_url = status.get("source_url")
    if status.get("source_type") == "fixture" or (
        isinstance(source_url, str) and source_url.casefold().startswith("file://")
    ):
        raw_capture = status.get("raw_capture")
        if not raw_capture:
            return False
        try:
            return path.resolve() == Path(raw_capture).resolve()
        except (OSError, TypeError, ValueError):
            return True

    return False


def select_raw_snapshot(raw_dir: Path, status: dict) -> dict | None:
    """Return the most appropriate validated raw capture, if one exists.

    The selection keeps the newest structurally valid capture, except when it
    contains less than half of the medicines from a much larger capture. That
    guard avoids silently replacing a complete catalogue with a partial response.
    """
    if not raw_dir.exists():
        return None
    if not isinstance(status, dict):
        status = {}

    try:
        raw_paths = sorted(
            (
                path for path in raw_dir.glob("vivver_estoque_*.txt")
                if not is_fixture_capture(path, status)
            ),
            key=raw_sort_time,
            reverse=True,
        )
    except OSError:
        return None
    valid_snapshots: list[tuple[Path, dict]] = []
    for raw_path in raw_paths:
        try:
            content = raw_path.read_text(encoding="utf-8-sig")
            collected_at = raw_collection_time(raw_path)
            raw_snapshot = normalize_stock(content, Config().stock_page, collected_at)
        except (OSError, UnicodeDecodeError, TypeError, ValueError):
            continue

        valid_snapshots.append((raw_path, raw_snapshot))

    if not valid_snapshots:
        return None

    newest_path, newest_snapshot = valid_snapshots[0]
    largest_path, largest_snapshot = max(
        valid_snapshots,
        key=lambda item: (
            item[1]["metadata"]["product_count"],
            raw_sort_time(item[0]),
        ),
    )
    newest_count = newest_snapshot["metadata"]["product_count"]
    largest_count = largest_snapshot["metadata"]["product_count"]

    selected_path, selected_snapshot = newest_path, newest_snapshot
    if largest_count >= 50 and newest_count < largest_count * 0.5:
        selected_path, selected_snapshot = largest_path, largest_snapshot
        selected_snapshot["metadata"]["freshness_note"] += (
            f" A captura mais recente retornou {newest_count} medicamentos, "
            f"menos da metade dos {largest_count} da captura anterior mais completa; "
            "por segurança, esta consulta manteve a captura maior, que pode estar desatualizada."
        )

    for raw_path, raw_snapshot in valid_snapshots:
        if raw_path != selected_path:
            continue
        if status.get("raw_capture"):
            try:
                is_last_capture = raw_path.resolve() == Path(status["raw_capture"]).resolve()
            except (OSError, TypeError, ValueError):
                is_last_capture = False
        else:
            is_last_capture = False

        if is_last_capture:
            raw_snapshot["metadata"]["collected_at"] = (
                status.get("last_success_at") or raw_snapshot["metadata"]["collected_at"]
            )
            if status.get("source_type") == "fixture":
                raw_snapshot["metadata"]["source"] = "Fixture local de demonstração"
                raw_snapshot["metadata"]["source_url"] = status.get("source_url", "")
                raw_snapshot["metadata"]["freshness_note"] = (
                    "Estes são dados fictícios de demonstração; não representam o estoque atual."
                )

        return raw_snapshot

    return None


def load_public_snapshot(raw_dir: Path, status_path: Path, snapshot_path: Path) -> dict:
    """Load the selected raw capture or use the last published snapshot."""
    status = read_json(status_path)
    snapshot = select_raw_snapshot(raw_dir, status)
    return snapshot if snapshot is not None else read_json(snapshot_path)


def freshness(snapshot: dict, status: dict, now: datetime) -> dict:
    """Summarize snapshot age for the public page in local Brazilian time."""
    metadata = snapshot.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    if not isinstance(status, dict):
        status = {}
    collected_at = metadata.get("collected_at")
    age = None
    if collected_at:
        try:
            collected = datetime.fromisoformat(str(collected_at).replace("Z", "+00:00"))
            if collected.tzinfo is None:
                collected = collected.replace(tzinfo=timezone.utc)
            age = now - collected
        except (TypeError, ValueError):
            age = None

    try:
        threshold = max(1, int(os.environ.get("APP_STALE_AFTER_HOURS", "24")))
    except ValueError:
        threshold = 24
    is_stale = age is None or age > timedelta(hours=threshold)
    attempt_failed = status.get("last_attempt_status") == "failed"
    is_demo = "Fixture" in str(metadata.get("source", ""))

    if is_demo:
        label = "Dados fictícios de demonstração."
        tone = "warning"
    elif attempt_failed:
        label = "A última tentativa de atualização falhou."
        tone = "warning"
    elif is_stale:
        label = "Esta consulta pode estar desatualizada."
        tone = "warning"
    else:
        label = "Consulta recente à fonte."
        tone = "success"

    display_time = None
    if collected_at:
        try:
            collected_time = datetime.fromisoformat(str(collected_at).replace("Z", "+00:00"))
            if collected_time.tzinfo is None:
                collected_time = collected_time.replace(tzinfo=timezone.utc)
            display_time = collected_time.astimezone(
                ZoneInfo("America/Sao_Paulo")
            ).strftime("%d/%m/%Y às %H:%M")
        except (TypeError, ValueError):
            display_time = None

    return {
        "collected_at": collected_at,
        "display_time": display_time,
        "timezone_label": "horário de Brasília",
        "label": label,
        "tone": tone,
        "is_stale": is_stale,
        "attempt_failed": attempt_failed,
        "threshold_hours": threshold,
        "note": metadata.get("freshness_note") or "",
        "relative_label": humanize_age(age),
        "is_demo": is_demo,
    }


def humanize_age(age: timedelta | None) -> str:
    """Express snapshot age as a short Portuguese relative time label."""
    if age is None:
        return "horário da consulta indisponível"
    seconds = max(0, int(age.total_seconds()))
    if seconds < 60:
        return "há menos de um minuto"
    minutes = seconds // 60
    if minutes < 60:
        return f"há {minutes} min"
    hours = minutes // 60
    if hours < 24:
        return f"há {hours} h"
    days = hours // 24
    if days == 1:
        return "há 1 dia"
    if days < 30:
        return f"há {days} dias"
    months = days // 30
    if months == 1:
        return "há 1 mês"
    if months < 12:
        return f"há {months} meses"
    years = days // 365
    return "há 1 ano" if years <= 1 else f"há {years} anos"


@dataclass(frozen=True)
class SnapshotBundle:
    """Pair the displayed stock snapshot with the last collection status."""

    snapshot: dict
    status: dict


class SnapshotRepository:
    """Load the public snapshot once per file state.

    The web page reads a ~1.5 MB JSON and validates raw captures on every
    request in the original implementation. This repository keeps a small,
    explicit cache keyed by the modification state of the source files, so the
    data contract stays the same while repeated requests become cheap.
    """

    def __init__(
        self,
        snapshot_path: Path = PUBLIC_SNAPSHOT,
        status_path: Path = COLLECTION_STATUS,
        raw_dir: Path = RAW_DIR,
    ) -> None:
        """Set data paths and initialize the thread-safe snapshot cache."""
        self.snapshot_path = snapshot_path
        self.status_path = status_path
        self.raw_dir = raw_dir
        self._lock = threading.Lock()
        self._signature: tuple[Any, ...] | None = None
        self._bundle: SnapshotBundle | None = None

    def _file_signature(self, path: Path) -> tuple[int, int] | None:
        """Return the modification time and size used to refresh the cache."""
        try:
            stat = path.stat()
        except OSError:
            return None
        return stat.st_mtime_ns, stat.st_size

    def _current_signature(self) -> tuple[Any, ...]:
        """Build a signature from the raw captures and published metadata."""
        raw_entries: list[tuple[str, int, int]] = []
        try:
            raw_paths = sorted(self.raw_dir.glob("vivver_estoque_*.txt"))
        except OSError:
            raw_paths = []
        for path in raw_paths:
            try:
                stat = path.stat()
            except OSError:
                continue
            raw_entries.append((path.name, stat.st_mtime_ns, stat.st_size))
        return (
            tuple(raw_entries),
            self._file_signature(self.status_path),
            self._file_signature(self.snapshot_path),
        )

    def load(self) -> SnapshotBundle:
        """Return the cached snapshot or reload it after a source file changes."""
        signature = self._current_signature()
        with self._lock:
            if self._bundle is not None and signature == self._signature:
                return self._bundle

        status = read_json(self.status_path)
        snapshot = select_raw_snapshot(self.raw_dir, status)
        if snapshot is None:
            snapshot = read_json(self.snapshot_path)
        bundle = SnapshotBundle(snapshot=snapshot, status=status)

        with self._lock:
            self._signature = signature
            self._bundle = bundle
        return bundle
