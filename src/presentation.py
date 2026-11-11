from __future__ import annotations

import json
import math
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .config import Config
from .snapshot_store import freshness, search_key

PAGE_SIZE = 20

SORT_OPTIONS = (
    ("relevancia", "Relevância"),
    ("nome", "Nome"),
    ("disponibilidade", "Mais unidades com estoque"),
)
SORT_KEYS = {key for key, _ in SORT_OPTIONS}

LOCATIONS_PATH = Path(__file__).parent / "static" / "unit_locations.json"

_locations_lock = threading.Lock()
_locations_cache: tuple[tuple[int, int] | None, dict[str, dict]] = (None, {})


def load_unit_locations(path: Path = LOCATIONS_PATH) -> dict[str, dict]:
    """Read documented map points, cached by file modification state."""
    global _locations_cache
    try:
        stat = path.stat()
        signature: tuple[int, int] | None = (stat.st_mtime_ns, stat.st_size)
    except OSError:
        signature = None

    with _locations_lock:
        cached_signature, cached_locations = _locations_cache
        if signature is not None and signature == cached_signature:
            return cached_locations

        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            data = {}
        if not isinstance(data, dict):
            data = {}

        raw_locations = data.get("locations", [])
        if not isinstance(raw_locations, list):
            raw_locations = []
        locations = {
            str(location.get("unit_id", "")): location
            for location in raw_locations
            if isinstance(location, dict) and location.get("unit_id")
        }
        _locations_cache = (signature, locations)
        return locations


def _quantity(value: Any) -> float:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return value
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return 0


def _format_quantity(value: float) -> str:
    if float(value).is_integer():
        return f"{int(value):,}".replace(",", ".")
    return f"{value:,.2f}".rstrip("0").rstrip(".").replace(",", "X").replace(".", ",").replace("X", ".")


def _availability_label(available: int, total: int) -> str:
    if total == 0:
        return "Sem unidades nesta consulta"
    if available == 0:
        return "Sem quantidade registrada"
    if total == 1:
        return "Com quantidade na única unidade"
    if available == total:
        return f"Com quantidade nas {total} unidades"
    return f"Com quantidade em {available} de {total} unidades"


def _relevance(product: dict, normalized_query: str) -> int:
    if not normalized_query:
        return 0
    name_key = search_key(product["name"])
    if name_key == normalized_query:
        return 0
    if name_key.startswith(normalized_query):
        return 1
    if any(word.startswith(normalized_query) for word in name_key.split()):
        return 2
    return 3


def _page_window(current: int, total: int) -> list[int | None]:
    if total <= 7:
        return list(range(1, total + 1))

    pages = {1, total, current}
    for distance in (1, 2):
        if current - distance > 1:
            pages.add(current - distance)
        if current + distance < total:
            pages.add(current + distance)

    ordered = sorted(pages)
    window: list[int | None] = []
    previous = 0
    for page in ordered:
        if previous and page - previous > 1:
            window.append(None)
        window.append(page)
        previous = page
    return window


def _build_units(product: dict, locations: Mapping[str, dict]) -> list[dict]:
    units: list[dict] = []
    raw_units = product.get("units", [])
    if not isinstance(raw_units, list):
        raw_units = []
    for unit in raw_units:
        if not isinstance(unit, dict):
            continue
        unit_id = str(unit.get("unit_id", "")).strip()
        if not unit_id:
            continue
        quantity = _quantity(unit.get("quantity"))
        location = locations.get(unit_id)
        units.append({
            "unit_id": unit_id,
            "name": str(unit.get("name", "")).strip(),
            "address": str(unit.get("address", "")).strip(),
            "phone": str(unit.get("phone", "")).strip(),
            "quantity": quantity,
            "quantity_display": _format_quantity(quantity),
            "is_available": quantity > 0,
            "has_map_location": location is not None,
            "map_status": str(location.get("location_status", "")) if location else "",
        })
    return units


def _decorate_product(product: dict, units: list[dict]) -> dict:
    available = sum(1 for unit in units if unit["is_available"])
    ordered_units = sorted(
        units,
        key=lambda unit: (not unit["is_available"], search_key(unit["name"])),
    )
    return {
        "product_id": product["product_id"],
        "name": product["name"],
        "supply_unit": product["supply_unit"],
        "units": ordered_units,
        "unit_count": len(ordered_units),
        "available_unit_count": available,
        "has_available": available > 0,
        "availability_label": _availability_label(available, len(ordered_units)),
        "total_quantity": sum(unit["quantity"] for unit in ordered_units),
    }


def _build_unit_options(
    products: list[dict],
    locations: Mapping[str, dict],
    available_only: bool = False,
) -> list[dict]:
    units_by_id: dict[str, dict] = {}
    for product in products:
        for unit in product["units"]:
            if available_only and not unit["is_available"]:
                continue
            unit_id = unit["unit_id"]
            entry = units_by_id.setdefault(unit_id, {
                "unit_id": unit_id,
                "name": unit["name"],
                "address": unit["address"],
                "phone": unit["phone"],
                "product_count": 0,
                "available_product_count": 0,
                "has_map_location": unit["has_map_location"],
                "map_status": unit["map_status"],
            })
            if not entry["address"] and unit["address"]:
                entry["address"] = unit["address"]
            if not entry["phone"] and unit["phone"]:
                entry["phone"] = unit["phone"]
            entry["product_count"] += 1
            if unit["is_available"]:
                entry["available_product_count"] += 1

    return sorted(units_by_id.values(), key=lambda unit: search_key(unit["name"]))


def build_home_context(
    snapshot: dict,
    status: dict,
    args: Mapping[str, str],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Translate the validated snapshot into the template's view model.

    This function is intentionally pure with respect to the snapshot: it never
    mutates the validated data, so the same snapshot can serve the page, the
    autocomplete API and future consumers.
    """
    now = now or datetime.now(timezone.utc)
    metadata = snapshot.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    locations = load_unit_locations()

    raw_products = snapshot.get("products", [])
    if not isinstance(raw_products, list):
        raw_products = []

    products: list[dict] = []
    for raw_product in raw_products:
        if not isinstance(raw_product, dict):
            continue
        name = str(raw_product.get("name", "")).strip()
        product_id = str(raw_product.get("product_id", "")).strip()
        if not name:
            continue
        product = {
            "product_id": product_id,
            "name": name,
            "supply_unit": str(raw_product.get("supply_unit", "")).strip(),
            "units": _build_units(raw_product, locations),
        }
        products.append(_decorate_product(product, product["units"]))

    unit_options_all = _build_unit_options(products, locations)
    unit_names = {unit["unit_id"]: unit["name"] for unit in unit_options_all}

    query = str(args.get("q", "") or "").strip()
    unit_query = str(args.get("unidade", "") or "").strip()
    show_catalog = args.get("catalogo") == "1" and not query and not unit_query
    normalized_query = search_key(query)

    # Keep the documented behaviour: the unit filter lists units present in the
    # medicines matched by the current search. Without a search, it lists all.
    if normalized_query:
        query_products = [
            product for product in products
            if normalized_query in search_key(f"{product['name']} {product['product_id']}")
        ]
        unit_options = _build_unit_options(query_products, locations, available_only=True)
    else:
        unit_options = unit_options_all

    # Keep the selected unit visible in the dropdown even when it has no
    # positive quantity for the current search (the results still show it).
    if unit_query and unit_query not in {unit["unit_id"] for unit in unit_options}:
        selected_unit = next(
            (unit for unit in unit_options_all if unit["unit_id"] == unit_query),
            None,
        )
        if selected_unit is not None:
            unit_options = sorted(
                [*unit_options, selected_unit],
                key=lambda unit: search_key(unit["name"]),
            )

    sort_key = str(args.get("ordem", "") or "").strip()
    if sort_key not in SORT_KEYS:
        sort_key = "relevancia"

    try:
        page_number = max(1, int(str(args.get("pagina", "1"))))
    except (TypeError, ValueError):
        page_number = 1

    if normalized_query:
        matched = [
            product for product in products
            if normalized_query in search_key(f"{product['name']} {product['product_id']}")
        ]
    else:
        matched = list(products) if unit_query or show_catalog else []

    if unit_query:
        matched = [
            product for product in matched
            if any(unit["unit_id"] == unit_query for unit in product["units"])
        ]

    if unit_query:
        matched = [
            _decorate_product(
                product,
                [unit for unit in product["units"] if unit["unit_id"] == unit_query],
            )
            for product in matched
        ]

    if sort_key == "disponibilidade":
        matched.sort(key=lambda product: (
            -product["available_unit_count"],
            -product["unit_count"],
            search_key(product["name"]),
        ))
    elif sort_key == "nome":
        matched.sort(key=lambda product: search_key(product["name"]))
    else:
        matched.sort(key=lambda product: (
            _relevance(product, normalized_query),
            search_key(product["name"]),
        ))

    result_count = len(matched)
    page_count = max(1, math.ceil(result_count / PAGE_SIZE))
    page_number = min(page_number, page_count)
    page_start = (page_number - 1) * PAGE_SIZE
    paginated_products = matched[page_start:page_start + PAGE_SIZE]

    total_units = len(unit_options_all)
    available_count = sum(
        1
        for product in products
        for unit in product["units"]
        if unit["is_available"]
    )
    mapped_count = sum(1 for unit in unit_options_all if unit["has_map_location"])

    return {
        "has_snapshot": bool(products),
        "products": paginated_products,
        "result_count": result_count,
        "show_catalog": show_catalog,
        "page_number": page_number,
        "page_count": page_count,
        "page_size": PAGE_SIZE,
        "page_start": page_start,
        "page_numbers": _page_window(page_number, page_count),
        "query": query,
        "unit_query": unit_query,
        "unit_query_name": unit_names.get(
            unit_query, f"Unidade {unit_query}" if unit_query else ""
        ),
        "unit_options": unit_options,
        "map_units": unit_options_all,
        "sort_key": sort_key,
        "sort_options": SORT_OPTIONS,
        "product_count": len(products),
        "unit_count": total_units,
        "available_count": available_count,
        "available_medicine_count": sum(1 for product in products if product["has_available"]),
        "mapped_count": mapped_count,
        "freshness": freshness(snapshot, status, now),
        "source_url": metadata.get(
            "source_url"
        ) or "https://www.montesclaros-mg.vivver.com/estoque",
        "source_page_url": Config().stock_page,
        "source_name": metadata.get(
            "source"
        ) or "Portal Cidadão – Estoque (Vivver)",
    }
