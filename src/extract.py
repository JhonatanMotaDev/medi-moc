from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

from .config import Config


@dataclass
class ExtractedResponse:
    content: str
    content_type: str
    url: str
    collected_at: str
    status_code: int


def _csrf_from_html(html: str) -> str | None:
    patterns = [
        r'name=["\']authenticity_token["\'][^>]*value=["\']([^"\']+)["\']',
        r'value=["\']([^"\']+)["\'][^>]*name=["\']authenticity_token["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.I)
        if match:
            return match.group(1)
    return None


def fetch_stock(config: Config) -> ExtractedResponse:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; VivverStockMVP/0.1)",
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
    })

    page = session.get(config.stock_page, timeout=30)
    page.raise_for_status()

    token = _csrf_from_html(page.text)

    params = {
        "utf8": "✓",
        "cid_estoque_lista[codigo_municipio]": config.municipio,
        "lookup_key[cid_estoque_lista[codigo_unidade]]": "",
        "cid_estoque_lista[codigo_unidade]": "",
        "lookup_key[cid_estoque_lista[id_produto]]": "",
        "cid_estoque_lista[id_produto]": "",
    }
    if token:
        params["authenticity_token"] = token

    response = session.get(config.grid_url, params=params, timeout=30)
    response.raise_for_status()

    return ExtractedResponse(
        content=response.text,
        content_type=response.headers.get("Content-Type", ""),
        url=response.url,
        collected_at=datetime.now(timezone.utc).isoformat(),
        status_code=response.status_code,
    )


def save_raw(result: ExtractedResponse, raw_dir: Path, prefix: str = "vivver_estoque") -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    stamp = result.collected_at.replace(":", "").replace("+00:00", "Z").replace(".", "")
    path = raw_dir / f"{prefix}_{stamp}.txt"
    path.write_text(result.content, encoding="utf-8")
    return path
