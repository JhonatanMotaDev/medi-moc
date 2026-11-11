"""Orchestrate authorized stock extraction, validation, and publication."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import COLLECTION_STATUS, PROCESSED_DIR, PUBLIC_SNAPSHOT, RAW_DIR, Config
from .source import ExtractedResponse, public_source_url, save_raw
from .sources import DEFAULT_STOCK_SOURCE, StockSource
from ..transform.snapshot import normalize_stock, utc_now, write_json_atomic


@dataclass(frozen=True)
class StockCollectionPipeline:
    """Coordinate extraction, validation, and publication of one stock capture.

    Attributes:
        snapshot_path: Destination for the validated public snapshot.
        status_path: Destination for the latest collection status.
        raw_dir: Directory that preserves source responses before transformation.
        source: Adapter responsible for retrieving stock data.
    """

    snapshot_path: Path = PUBLIC_SNAPSHOT
    status_path: Path = COLLECTION_STATUS
    raw_dir: Path = RAW_DIR
    source: StockSource = DEFAULT_STOCK_SOURCE

    def extract(self, fixture: Path | None = None) -> ExtractedResponse:
        """Extract a raw response from the configured source or a local fixture."""
        collected_at = utc_now()
        if fixture is not None:
            return ExtractedResponse(
                content=fixture.read_text(encoding="utf-8"),
                content_type="application/json",
                url=fixture.resolve().as_uri(),
                collected_at=collected_at,
                status_code=200,
            )
        return self.source.fetch(Config())

    def transform(self, response: ExtractedResponse, fixture: bool = False) -> dict[str, Any]:
        """Validate the response and build a public snapshot without URL secrets."""
        snapshot = normalize_stock(
            response.content,
            public_source_url(response.url),
            response.collected_at,
            source_name=self.source.display_name,
        )
        if fixture:
            snapshot["metadata"]["source"] = "Fixture local de demonstração"
            snapshot["metadata"]["freshness_note"] = (
                "Estes são dados fictícios de demonstração; não representam o estoque atual."
            )
        return snapshot

    def load(
        self,
        response: ExtractedResponse,
        snapshot: dict[str, Any],
        raw_path: Path,
        fixture: bool = False,
    ) -> None:
        """Publish the validated snapshot and record the successful collection."""
        write_json_atomic(self.snapshot_path, snapshot)
        write_json_atomic(self.status_path, {
            "last_attempt_at": response.collected_at,
            "last_attempt_status": "success",
            "last_success_at": response.collected_at,
            "last_success_snapshot": str(self.snapshot_path),
            "last_error": None,
            "raw_capture": str(raw_path),
            "source_type": "fixture" if fixture else self.source.source_id,
            "source_url": response.url,
        })

    def run(self, fixture: Path | None = None) -> dict[str, Any]:
        """Run extract → preserve raw → transform → publish, recording failures."""
        response: ExtractedResponse | None = None
        started_at = utc_now()
        try:
            response = self.extract(fixture)
            raw_path = save_raw(response, self.raw_dir)
            snapshot = self.transform(response, fixture=fixture is not None)
            self.load(response, snapshot, raw_path, fixture=fixture is not None)
            return snapshot
        except (OSError, ValueError, RuntimeError) as error:
            previous_status = _read_json(self.status_path)
            write_json_atomic(self.status_path, {
                "last_attempt_at": response.collected_at if response else started_at,
                "last_attempt_status": "failed",
                "last_success_at": previous_status.get("last_success_at"),
                "last_success_snapshot": str(self.snapshot_path),
                "last_error": str(error),
                "raw_capture": previous_status.get("raw_capture"),
                "source_type": previous_status.get("source_type"),
                "source_url": previous_status.get("source_url"),
            })
            raise


def collect(
    fixture: Path | None = None,
    snapshot_path: Path = PUBLIC_SNAPSHOT,
    status_path: Path = COLLECTION_STATUS,
    raw_dir: Path = RAW_DIR,
    source: StockSource = DEFAULT_STOCK_SOURCE,
) -> dict[str, Any]:
    """Backward-compatible function entry point for the collection pipeline."""
    pipeline = StockCollectionPipeline(snapshot_path, status_path, raw_dir, source)
    return pipeline.run(fixture)


def _read_json(path: Path) -> dict:
    """Read a status object, returning an empty mapping when none is available."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(value, dict):
        return {}
    return value


def main() -> int:
    """Run a collection from the command line and report its outcome."""
    parser = argparse.ArgumentParser(description="Coleta e valida o estoque do Vivver.")
    parser.add_argument("--fixture", type=Path, help="Usa uma captura JSON local em vez da fonte online.")
    args = parser.parse_args()

    try:
        snapshot = collect(fixture=args.fixture)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"[coleta] falha: {error}")
        return 1

    metadata = snapshot["metadata"]
    print(
        f"[coleta] sucesso: {metadata['product_count']} medicamentos, "
        f"{metadata['unit_stock_rows']} registros por unidade."
    )
    print(f"[coleta] snapshot: {PUBLIC_SNAPSHOT}")
    print(f"[coleta] status: {COLLECTION_STATUS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
