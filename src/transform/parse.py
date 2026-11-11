"""Parse supported JSON and HTML responses into tabular rows."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup


def _rows_from_json(obj: Any) -> list[dict]:
    """Extract row objects from common JSON response shapes."""
    if isinstance(obj, list):
        return [dict(x) for x in obj if isinstance(x, Mapping)]

    if isinstance(obj, Mapping):
        for key in ("data", "rows", "results", "records", "items"):
            value = obj.get(key)
            if isinstance(value, list):
                return [dict(x) for x in value if isinstance(x, Mapping)]
        if all(not isinstance(v, (list, dict)) for v in obj.values()):
            return [dict(obj)]

    return []


def _parse_html_table(html: str) -> pd.DataFrame | None:
    """Choose the most complete HTML table while preserving text identifiers."""
    soup = BeautifulSoup(html, "lxml")
    candidates = []

    for table in soup.select("table"):
        rows = []
        for tr in table.select("tr"):
            cells = [cell.get_text(" ", strip=True) for cell in tr.select("th, td")]
            if cells:
                rows.append(cells)

        if len(rows) >= 2:
            header = rows[0]
            body = rows[1:]
            width = len(header)
            body = [r[:width] + [None] * max(0, width - len(r)) for r in body]
            candidates.append(pd.DataFrame(body, columns=header))

    if candidates:
        return max(candidates, key=lambda df: (len(df), len(df.columns)))

    return None


def parse_response(content: str, content_type: str = "") -> pd.DataFrame:
    """Parse a source response as JSON or as an HTML table."""
    text = content.lstrip("\ufeff \n\t")

    # Prefer JSON when the response declares it or looks like JSON.
    if "json" in content_type.lower() or text.startswith(("{", "[")):
        try:
            rows = _rows_from_json(json.loads(text))
            if rows:
                return pd.DataFrame(rows)
        except json.JSONDecodeError:
            pass

    # Parse HTML manually to preserve identifiers such as "007".
    table = _parse_html_table(text)
    if table is not None:
        return table

    raise ValueError("Resposta sem JSON ou tabela HTML detectável.")
