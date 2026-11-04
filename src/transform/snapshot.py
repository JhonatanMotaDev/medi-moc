from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


class SnapshotValidationError(ValueError):
    """Raised when the source payload cannot safely be published."""


def _quantity(value: Any, location: str) -> int | float:
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise SnapshotValidationError(f"Quantidade inválida em {location}.") from None

    if not quantity.is_finite() or quantity < 0:
        raise SnapshotValidationError(f"Quantidade negativa ou não finita em {location}.")
    return int(quantity) if quantity == quantity.to_integral_value() else float(quantity)


def normalize_stock(
    payload: str,
    source_url: str,
    collected_at: str,
    source_name: str = "Portal Cidadão – Estoque (Vivver)",
) -> dict[str, Any]:
    try:
        products = json.loads(payload)
    except json.JSONDecodeError as error:
        raise SnapshotValidationError("A fonte não retornou JSON válido.") from error

    if not isinstance(products, list) or not products:
        raise SnapshotValidationError("A resposta precisa ser uma lista não vazia de medicamentos.")

    normalized_products: list[dict[str, Any]] = []
    seen_product_ids: set[str] = set()
    unit_rows = 0

    for product_index, product in enumerate(products):
        if not isinstance(product, dict):
            raise SnapshotValidationError(f"Medicamento inválido na posição {product_index}.")

        product_id = str(product.get("id_produto", "")).strip()
        name = str(product.get("nomproduto", "")).strip()
        units = product.get("estoque_unidade")
        if not product_id or not name or not isinstance(units, list):
            raise SnapshotValidationError(
                f"Medicamento na posição {product_index} sem identificador, nome ou lista de unidades."
            )
        if product_id in seen_product_ids:
            raise SnapshotValidationError(f"Medicamento duplicado: {product_id}.")
        seen_product_ids.add(product_id)

        normalized_units: list[dict[str, Any]] = []
        seen_units: set[str] = set()
        for unit_index, unit in enumerate(units):
            location = f"medicamento {product_id}, unidade {unit_index}"
            if not isinstance(unit, dict):
                raise SnapshotValidationError(f"Registro de unidade inválido em {location}.")
            unit_id = str(unit.get("codunidade", "")).strip()
            unit_name = str(unit.get("nomfantasia", "")).strip()
            if not unit_id or not unit_name:
                raise SnapshotValidationError(f"Faltam código ou nome da unidade em {location}.")
            if unit_id in seen_units:
                raise SnapshotValidationError(
                    f"Unidade duplicada ({unit_id}) para o medicamento {product_id}."
                )
            seen_units.add(unit_id)
            normalized_units.append({
                "unit_id": unit_id,
                "name": unit_name,
                "quantity": _quantity(unit.get("qdeestoque"), location),
                "phone": str(unit.get("numtelefone") or "").strip(),
                "address": str(unit.get("endereco_unidade") or "").strip(),
            })
            unit_rows += 1

        normalized_products.append({
            "product_id": product_id,
            "name": name,
            "supply_unit": str(product.get("unidade_fornecimento") or "").strip(),
            "units": normalized_units,
        })

    if unit_rows == 0:
        raise SnapshotValidationError("A resposta não contém registros de estoque por unidade.")

    return {
        "metadata": {
            "source": source_name,
            "source_url": source_url,
            "collected_at": collected_at,
            "source_updated_at": None,
            "product_count": len(normalized_products),
            "unit_stock_rows": unit_rows,
            "freshness_note": (
                "Este horário informa quando a plataforma consultou a fonte; "
                "a fonte não informa quando cada unidade atualizou o estoque."
            ),
        },
        "products": normalized_products,
    }


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(data, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
