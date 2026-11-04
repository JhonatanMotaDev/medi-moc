from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..config import COLLECTION_STATUS, PROCESSED_DIR, PUBLIC_SNAPSHOT, RAW_DIR, Config
from .source import ExtractedResponse, save_raw
from .sources import DEFAULT_STOCK_SOURCE, StockSource
from ..transform.snapshot import normalize_stock, utc_now, write_json_atomic


def collect(
    fixture: Path | None = None,
    snapshot_path: Path = PUBLIC_SNAPSHOT,
    status_path: Path = COLLECTION_STATUS,
    raw_dir: Path = RAW_DIR,
    source: StockSource = DEFAULT_STOCK_SOURCE,
) -> dict:
    result: ExtractedResponse | None = None
    collected_at = utc_now()

    try:
        if fixture is not None:
            content = fixture.read_text(encoding="utf-8")
            result = ExtractedResponse(
                content=content,
                content_type="application/json",
                url=fixture.resolve().as_uri(),
                collected_at=collected_at,
                status_code=200,
            )
        else:
            result = source.fetch(Config())

        raw_path = save_raw(result, raw_dir)
        snapshot = normalize_stock(
            result.content,
            result.url,
            result.collected_at,
            source_name=source.display_name,
        )
        if fixture is not None:
            snapshot["metadata"]["source"] = "Fixture local de demonstração"
            snapshot["metadata"]["freshness_note"] = (
                "Estes são dados fictícios de demonstração; não representam o estoque atual."
            )
        write_json_atomic(snapshot_path, snapshot)
        status = {
            "last_attempt_at": result.collected_at,
            "last_attempt_status": "success",
            "last_success_at": result.collected_at,
            "last_success_snapshot": str(snapshot_path),
            "last_error": None,
            "raw_capture": str(raw_path),
            "source_type": "fixture" if fixture is not None else source.source_id,
            "source_url": result.url,
        }
        write_json_atomic(status_path, status)
        return snapshot
    except (OSError, ValueError, RuntimeError) as error:
        previous_status = _read_json(status_path)
        status = {
            "last_attempt_at": result.collected_at if result else collected_at,
            "last_attempt_status": "failed",
            "last_success_at": previous_status.get("last_success_at"),
            "last_success_snapshot": str(snapshot_path),
            "last_error": str(error),
            "raw_capture": previous_status.get("raw_capture"),
            "source_type": previous_status.get("source_type"),
            "source_url": previous_status.get("source_url"),
        }
        write_json_atomic(status_path, status)
        raise


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(value, dict):
        return {}
    return value


def main() -> int:
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
