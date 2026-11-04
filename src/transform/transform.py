#!/usr/bin/env python3
"""
Transformação dos dados de estoque da API Vivver.

Entrada:
    JSON em formato de lista, com produtos contendo `estoque_unidade`.

Saída:
    dim_produto.csv
    dim_unidade.csv
    fato_estoque.csv
    transform_log.json

Uso:
    python transform.py <arquivo_entrada.txt> <diretorio_saida>
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any


PRODUCT_REQUIRED = {
    "id_produto",
    "nomproduto",
    "unidade_fornecimento",
    "qdeestoque",
    "estoque_unidade",
}

STOCK_REQUIRED = {
    "codmunicipio",
    "codunidade",
    "id_produto",
    "nomproduto",
    "nomfantasia",
    "numtelefone",
    "endereco_unidade",
    "qdeestoque",
}


def clean_text(value: Any) -> str:
    """Normaliza Unicode e espaços sem alterar o conteúdo semântico."""
    if value is None:
        return ""
    value = unicodedata.normalize("NFKC", str(value))
    return re.sub(r"\s+", " ", value).strip()


def to_int(value: Any, field_name: str) -> int:
    """Converte números inteiros representados como int, float ou string."""
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name}: valor inválido: {value!r}") from exc

    if not number.is_integer():
        raise ValueError(f"{field_name}: esperado inteiro, recebido {value!r}")

    return int(number)


def normalize_phone(value: Any) -> str:
    """
    Mantém apenas dígitos para facilitar comparação/consulta.
    Ex.: '38 2211-4504' -> '3822114504'
    """
    return re.sub(r"\D", "", clean_text(value))


def validate_schema(products: list[dict[str, Any]]) -> None:
    for idx, product in enumerate(products):
        missing = PRODUCT_REQUIRED - product.keys()
        if missing:
            raise ValueError(
                f"Produto na posição {idx} sem campos obrigatórios: {sorted(missing)}"
            )

        if not isinstance(product["estoque_unidade"], list):
            raise ValueError(
                f"id_produto={product.get('id_produto')}: "
                "`estoque_unidade` deve ser uma lista."
            )

        for unit_idx, stock in enumerate(product["estoque_unidade"]):
            missing = STOCK_REQUIRED - stock.keys()
            if missing:
                raise ValueError(
                    f"id_produto={product.get('id_produto')}, "
                    f"estoque_unidade[{unit_idx}] sem campos: {sorted(missing)}"
                )


def transform(products: list[dict[str, Any]]) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    dim_produto: list[dict[str, Any]] = []
    dim_unidade_by_id: dict[int, dict[str, Any]] = {}
    fato_estoque: list[dict[str, Any]] = []

    errors: list[str] = []
    seen_stock_keys: set[tuple[int, int]] = set()
    unit_metadata: dict[int, tuple[str, str, str]] = {}

    for product in products:
        product_id = to_int(product["id_produto"], "id_produto")
        product_name = clean_text(product["nomproduto"])
        supply_unit = clean_text(product["unidade_fornecimento"])
        source_total = to_int(product["qdeestoque"], "qdeestoque")

        unit_rows = product["estoque_unidade"]
        calculated_total = 0

        for stock in unit_rows:
            stock_product_id = to_int(stock["id_produto"], "estoque_unidade.id_produto")
            municipality_id = to_int(stock["codmunicipio"], "codmunicipio")
            unit_id = to_int(stock["codunidade"], "codunidade")
            quantity = to_int(stock["qdeestoque"], "estoque_unidade.qdeestoque")

            stock_product_name = clean_text(stock["nomproduto"])
            unit_name = clean_text(stock["nomfantasia"])
            phone = normalize_phone(stock["numtelefone"])
            address = clean_text(stock["endereco_unidade"])

            if stock_product_id != product_id:
                errors.append(
                    f"id_produto {product_id}: registro filho aponta para "
                    f"id_produto {stock_product_id}"
                )

            if stock_product_name != product_name:
                errors.append(
                    f"id_produto {product_id}: nome do produto diverge no registro filho"
                )

            stock_key = (product_id, unit_id)
            if stock_key in seen_stock_keys:
                errors.append(
                    f"duplicidade encontrada para (id_produto, codunidade)={stock_key}"
                )
            seen_stock_keys.add(stock_key)

            metadata = (unit_name, phone, address)
            previous = unit_metadata.get(unit_id)
            if previous is not None and previous != metadata:
                errors.append(
                    f"codunidade={unit_id}: metadados da unidade divergentes"
                )
            unit_metadata[unit_id] = metadata

            if unit_id not in dim_unidade_by_id:
                dim_unidade_by_id[unit_id] = {
                    "codmunicipio": municipality_id,
                    "codunidade": unit_id,
                    "nomfantasia": unit_name,
                    "numtelefone": phone,
                    "endereco_unidade": address,
                }

            fato_estoque.append(
                {
                    "id_produto": product_id,
                    "codmunicipio": municipality_id,
                    "codunidade": unit_id,
                    "qdeestoque": quantity,
                }
            )

            calculated_total += quantity

        if source_total != calculated_total:
            errors.append(
                f"id_produto={product_id}: estoque total divergente "
                f"(fonte={source_total}, calculado={calculated_total})"
            )

        dim_produto.append(
            {
                "id_produto": product_id,
                "nomproduto": product_name,
                "unidade_fornecimento": supply_unit,
                "qdeestoque": calculated_total,
            }
        )

    if errors:
        raise ValueError(
            "Falha na validação dos dados:\n- " + "\n- ".join(errors[:20])
            + ("\n..." if len(errors) > 20 else "")
        )

    dim_produto.sort(key=lambda row: row["id_produto"])
    dim_unidade = sorted(
        dim_unidade_by_id.values(),
        key=lambda row: row["codunidade"],
    )
    fato_estoque.sort(
        key=lambda row: (row["id_produto"], row["codunidade"])
    )

    metrics = {
        "produtos": len(dim_produto),
        "unidades": len(dim_unidade),
        "registros_estoque": len(fato_estoque),
        "estoque_total": sum(row["qdeestoque"] for row in dim_produto),
        "validacoes": {
            "ids_produto_filho_coincidem": True,
            "nomes_produto_coincidem": True,
            "sem_duplicidade_produto_unidade": True,
            "metadados_unidade_consistentes": True,
            "estoque_total_confere_com_unidades": True,
        },
    }

    return dim_produto, dim_unidade, fato_estoque, metrics


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Transforma o estoque bruto da API Vivver.")
    parser.add_argument("input_file", type=Path, help="Arquivo JSON/TXT extraído da API")
    parser.add_argument("output_dir", type=Path, help="Diretório para os dados transformados")
    args = parser.parse_args()

    with args.input_file.open("r", encoding="utf-8") as file:
        raw = json.load(file)

    if not isinstance(raw, list):
        raise ValueError("O arquivo de entrada deve conter uma lista JSON.")

    validate_schema(raw)

    dim_produto, dim_unidade, fato_estoque, metrics = transform(raw)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    write_csv(
        args.output_dir / "dim_produto.csv",
        dim_produto,
        ["id_produto", "nomproduto", "unidade_fornecimento", "qdeestoque"],
    )
    write_csv(
        args.output_dir / "dim_unidade.csv",
        dim_unidade,
        [
            "codmunicipio",
            "codunidade",
            "nomfantasia",
            "numtelefone",
            "endereco_unidade",
        ],
    )
    write_csv(
        args.output_dir / "fato_estoque.csv",
        fato_estoque,
        ["id_produto", "codmunicipio", "codunidade", "qdeestoque"],
    )

    log = {
        "arquivo_entrada": args.input_file.name,
        "status": "success",
        "metricas": metrics,
    }

    with (args.output_dir / "transform_log.json").open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(log, file, ensure_ascii=False, indent=2)

    print("Transform concluído com sucesso.")
    print(f"Produtos: {metrics['produtos']}")
    print(f"Unidades: {metrics['unidades']}")
    print(f"Registros de estoque: {metrics['registros_estoque']}")
    print(f"Saída: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
