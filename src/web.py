from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from .config import COLLECTION_STATUS, PUBLIC_SNAPSHOT, RAW_DIR, Config
from .transform.snapshot import normalize_stock


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _search_key(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def _raw_collection_time(raw_path: Path) -> str:
    match = re.fullmatch(r"vivver_estoque_(.+)\.txt", raw_path.name)
    if match:
        timestamp = match.group(1)
        for timestamp_format in ("%Y-%m-%dT%H%M%S%fZ", "%Y-%m-%dT%H%M%S%f%z"):
            try:
                return datetime.strptime(timestamp, timestamp_format).astimezone(timezone.utc).isoformat()
            except ValueError:
                continue

    return datetime.fromtimestamp(raw_path.stat().st_mtime, timezone.utc).isoformat()


def _raw_sort_time(raw_path: Path) -> float:
    if raw_path.stem.casefold().endswith("_fixture"):
        return 0.0
    try:
        return datetime.fromisoformat(_raw_collection_time(raw_path)).timestamp()
    except (OSError, ValueError):
        return 0.0


def _is_fixture_capture(path: Path, status: dict) -> bool:
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


def _raw_snapshot(
    raw_dir: Path,
    status: dict,
) -> dict | None:
    if not raw_dir.exists():
        return None

    raw_paths = sorted(
        (
            path for path in raw_dir.glob("vivver_estoque_*.txt")
            if not _is_fixture_capture(path, status)
        ),
        key=_raw_sort_time,
        reverse=True,
    )
    valid_snapshots: list[tuple[Path, dict]] = []
    for raw_path in raw_paths:
        try:
            content = raw_path.read_text(encoding="utf-8-sig")
            collected_at = _raw_collection_time(raw_path)
            raw_snapshot = normalize_stock(content, Config().stock_page, collected_at)
        except (OSError, ValueError):
            continue

        valid_snapshots.append((raw_path, raw_snapshot))

    if not valid_snapshots:
        return None

    newest_path, newest_snapshot = valid_snapshots[0]
    largest_path, largest_snapshot = max(
        valid_snapshots,
        key=lambda item: (
            item[1]["metadata"]["product_count"],
            _raw_sort_time(item[0]),
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
                status.get("last_success_at") or collected_at
            )
            if status.get("source_type") == "fixture":
                raw_snapshot["metadata"]["source"] = "Fixture local de demonstração"
                raw_snapshot["metadata"]["source_url"] = status.get("source_url", "")
                raw_snapshot["metadata"]["freshness_note"] = (
                    "Estes são dados fictícios de demonstração; não representam o estoque atual."
                )

        return raw_snapshot


def _load_public_snapshot(raw_dir: Path, status_path: Path, snapshot_path: Path) -> dict:
    status = _read_json(status_path)
    snapshot = _raw_snapshot(raw_dir, status)
    return snapshot if snapshot is not None else _read_json(snapshot_path)


def _freshness(snapshot: dict, status: dict, now: datetime) -> dict:
    metadata = snapshot.get("metadata", {})
    collected_at = metadata.get("collected_at")
    age = None
    if collected_at:
        try:
            collected = datetime.fromisoformat(collected_at.replace("Z", "+00:00"))
            age = now - collected
        except (TypeError, ValueError):
            age = None

    threshold = max(1, int(os.environ.get("APP_STALE_AFTER_HOURS", "24")))
    is_stale = age is None or age > timedelta(hours=threshold)
    attempt_failed = status.get("last_attempt_status") == "failed"

    if attempt_failed:
        label = "A última tentativa de atualização falhou."
        tone = "warning"
    elif is_stale:
        label = "Esta consulta pode estar desatualizada."
        tone = "warning"
    else:
        label = "Consulta recente à fonte."
        tone = "success"

    return {
        "collected_at": collected_at,
        "label": label,
        "tone": tone,
        "is_stale": is_stale,
        "attempt_failed": attempt_failed,
        "threshold_hours": threshold,
        "note": metadata.get("freshness_note", ""),
    }


def create_app(
    snapshot_path: Path = PUBLIC_SNAPSHOT,
    status_path: Path = COLLECTION_STATUS,
    raw_dir: Path = RAW_DIR,
) -> Flask:
    application = Flask(__name__, template_folder="template")
    application.config["TEMPLATES_AUTO_RELOAD"] = True

    @application.template_filter("phone_href")
    def phone_href(phone: str) -> str:
        digits = "".join(character for character in phone if character.isdigit() or character == "+")
        return f"tel:{digits}"

    @application.get("/api/medicines")
    def medicine_suggestions():
        query = _search_key(request.args.get("q", "").strip())
        if len(query) < 2:
            return jsonify([])

        products = _load_public_snapshot(raw_dir, status_path, snapshot_path).get("products", [])
        if not isinstance(products, list):
            return jsonify([])

        names = sorted({
            str(product.get("name", "")).strip()
            for product in products
            if isinstance(product, dict)
            and query in _search_key(str(product.get("name", "")))
            and product.get("name")
        }, key=_search_key)
        return jsonify(names[:10])

    @application.get("/")
    def index():
        status = _read_json(status_path)
        snapshot = _load_public_snapshot(raw_dir, status_path, snapshot_path)
        products = snapshot.get("products", [])
        if not isinstance(products, list):
            products = []

        query = request.args.get("q", "").strip()
        unit_query = request.args.get("unidade", "").strip()
        show_catalog = request.args.get("catalogo") == "1" and not query and not unit_query
        try:
            page_number = max(1, int(request.args.get("pagina", "1")))
        except ValueError:
            page_number = 1
        normalized_query = _search_key(query)
        normalized_unit_query = _search_key(unit_query)

        if normalized_query:
            matched = [
                product for product in products
                if normalized_query in _search_key(
                    f"{product.get('name', '')} {product.get('product_id', '')}"
                )
            ]
        else:
            matched = list(products) if unit_query or show_catalog else []

        if normalized_unit_query:
            matched = [
                product for product in matched
                if any(str(unit.get("unit_id", "")) == unit_query for unit in product.get("units", []))
            ]

        selected_unit_ids = {
            str(unit.get("unit_id", ""))
            for product in products
            if isinstance(product, dict)
            and (
                not normalized_query
                or normalized_query in _search_key(
                    f"{product.get('name', '')} {product.get('product_id', '')}"
                )
            )
            for unit in product.get("units", [])
            if isinstance(unit, dict)
        }
        units_by_id = {
            str(unit.get("unit_id", "")): str(unit.get("name", ""))
            for product in products
            if isinstance(product, dict)
            for unit in product.get("units", [])
            if isinstance(unit, dict)
            and str(unit.get("unit_id", "")) in selected_unit_ids
        }
        unit_options = [
            {"unit_id": unit_id, "name": name}
            for unit_id, name in sorted(units_by_id.items(), key=lambda item: _search_key(item[1]))
        ]
        for product in matched:
            units = product.get("units", [])
            if normalized_unit_query:
                product["units"] = [
                    unit for unit in units
                    if str(unit.get("unit_id", "")) == unit_query
                ]

        matched.sort(key=lambda product: _search_key(product.get("name", "")))
        result_count = len(matched)
        page_size = 20
        page_count = max(1, (result_count + page_size - 1) // page_size)
        page_number = min(page_number, page_count)
        page_start = (page_number - 1) * page_size
        paginated_products = matched[page_start:page_start + page_size]
        total_products = len(products)
        total_units = len({
            unit.get("unit_id")
            for product in products
            for unit in product.get("units", [])
            if unit.get("unit_id")
        })
        total_available = sum(
            1
            for product in products
            for unit in product.get("units", [])
            if unit.get("quantity", 0) > 0
        )
        map_units_by_id: dict[str, dict] = {}
        for product in products:
            for unit in product.get("units", []):
                unit_id = str(unit.get("unit_id", ""))
                if not unit_id:
                    continue
                map_unit = map_units_by_id.setdefault(unit_id, {
                    "unit_id": unit_id,
                    "name": str(unit.get("name", "")),
                    "address": str(unit.get("address", "")),
                    "phone": str(unit.get("phone", "")),
                    "product_count": 0,
                    "available_product_count": 0,
                })
                if not map_unit["address"] and unit.get("address"):
                    map_unit["address"] = str(unit["address"])
                if not map_unit["phone"] and unit.get("phone"):
                    map_unit["phone"] = str(unit["phone"])
                map_unit["product_count"] += 1
                if unit.get("quantity", 0) > 0:
                    map_unit["available_product_count"] += 1
        map_units = sorted(
            map_units_by_id.values(),
            key=lambda unit: _search_key(unit["name"]),
        )
        featured_products = sorted(
            products,
            key=lambda product: (
                -sum(1 for unit in product.get("units", []) if unit.get("quantity", 0) > 0),
                _search_key(product.get("name", "")),
            ),
        )[:4]

        freshness = _freshness(snapshot, status, datetime.now(timezone.utc))
        return render_template(
            "stock.html",
            has_snapshot=bool(products),
            products=paginated_products,
            result_count=result_count,
            show_catalog=show_catalog,
            page_number=page_number,
            page_count=page_count,
            page_size=page_size,
            page_start=page_start,
            query=query,
            unit_query=unit_query,
            unit_options=unit_options,
            map_units=map_units,
            featured_products=featured_products,
            product_count=total_products,
            unit_count=total_units,
            available_count=total_available,
            available_medicine_count=sum(
                1 for product in products
                if any(unit.get("quantity", 0) > 0 for unit in product.get("units", []))
            ),
            freshness=freshness,
            source_url=snapshot.get("metadata", {}).get(
                "source_url", "https://www.montesclaros-mg.vivver.com/estoque"
            ),
        )

    return application


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"Servidor local iniciado em http://{host}:{port} (Ctrl+C para encerrar)")
    app.run(host=host, port=port, debug=False, threaded=True)
