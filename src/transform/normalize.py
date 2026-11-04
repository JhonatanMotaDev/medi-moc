from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

import pandas as pd


ALIASES = {
    "codigo municipio": "codigo_municipio",
    "codigo do municipio": "codigo_municipio",
    "código municipio": "codigo_municipio",
    "codigo unidade": "codigo_unidade",
    "codigo da unidade": "codigo_unidade",
    "código unidade": "codigo_unidade",
    "unidade": "unidade",
    "nome unidade": "unidade",
    "produto": "medicamento",
    "medicamento": "medicamento",
    "nome produto": "medicamento",
    "descricao": "medicamento",
    "descrição": "medicamento",
    "estoque": "quantidade_estoque",
    "quantidade": "quantidade_estoque",
    "qtd": "quantidade_estoque",
    "quantidade estoque": "quantidade_estoque",
    "id produto": "id_produto",
    "id do produto": "id_produto",
    "observacao": "observacao",
    "observação": "observacao",
}


def _key(value: object) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().lower()


def _clean_text(series: pd.Series) -> pd.Series:
    return (
        series.astype("string")
        .str.normalize("NFC")
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
        .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    )


def _to_number(series: pd.Series) -> pd.Series:
    s = _clean_text(series)

    def parse_one(x):
        if pd.isna(x):
            return pd.NA

        x = str(x).replace("\xa0", " ").strip()
        x = re.sub(r"[^\d,\.\-]", "", x)
        if not x:
            return pd.NA

        # Brazilian thousands/decimal conventions:
        # 1.250 -> 1250
        # 1.250,50 -> 1250.50
        # 1250,50 -> 1250.50
        # 1250.50 -> 1250.50
        if "," in x:
            if "." in x:
                x = x.replace(".", "").replace(",", ".")
            else:
                x = x.replace(",", ".")
        elif "." in x:
            parts = x.split(".")
            if len(parts) > 1 and len(parts[-1]) == 3 and all(p.isdigit() for p in parts):
                x = "".join(parts)

        try:
            n = float(x)
            return int(n) if n.is_integer() else n
        except ValueError:
            return pd.NA

    return s.map(parse_one)


def normalize(
    df: pd.DataFrame,
    municipio: str = "3143302",
    collected_at: str | None = None,
    source_url: str | None = None,
) -> pd.DataFrame:
    out = df.copy()

    # Map source-specific labels to a canonical schema.
    columns = []
    for col in out.columns:
        normalized = _key(col)
        columns.append(ALIASES.get(normalized, normalized.replace(" ", "_")))
    out.columns = columns

    # Remove accidental index columns.
    out = out.loc[:, ~pd.Index(out.columns).str.match(r"^unnamed(_|$)", case=False)]

    if "codigo_municipio" not in out.columns:
        out["codigo_municipio"] = municipio

    # Identifier fields must stay strings; this preserves leading zeros.
    for col in ("codigo_municipio", "codigo_unidade", "id_produto"):
        if col in out.columns:
            out[col] = _clean_text(out[col])

    for col in out.columns:
        if col not in {"codigo_municipio", "codigo_unidade", "id_produto", "quantidade_estoque"}:
            out[col] = _clean_text(out[col])

    if "quantidade_estoque" in out.columns:
        out["quantidade_estoque"] = _to_number(out["quantidade_estoque"]).astype("Float64")

    # Keep source text and add an analysis-friendly canonical text field.
    if "medicamento" in out.columns:
        out["medicamento_normalizado"] = (
            _clean_text(out["medicamento"])
            .str.upper()
            .str.replace(r"\s+", " ", regex=True)
        )

    out["codigo_municipio"] = out["codigo_municipio"].fillna(municipio)
    out["municipio"] = "Montes Claros"
    out["uf"] = "MG"
    out["fonte"] = "vivver"
    out["coletado_em_utc"] = collected_at or datetime.now(timezone.utc).isoformat()

    if source_url:
        out["url_fonte"] = source_url

    # Exact duplicate rows are not useful in the curated layer.
    out = out.drop_duplicates().reset_index(drop=True)

    preferred = [
        "codigo_municipio", "municipio", "uf",
        "codigo_unidade", "unidade",
        "id_produto", "medicamento", "medicamento_normalizado",
        "quantidade_estoque", "observacao",
        "fonte", "coletado_em_utc", "url_fonte",
    ]
    ordered = [c for c in preferred if c in out.columns]
    remaining = [c for c in out.columns if c not in ordered]

    return out[ordered + remaining]
