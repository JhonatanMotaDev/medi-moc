"""HTTP extraction helpers and the immutable raw-response model."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import requests

from ..config import Config


@dataclass(frozen=True)
class ExtractedResponse:
    """Raw response and collection metadata returned by a stock source.

    Attributes:
        content: Response body before parsing or normalization.
        content_type: MIME type reported by the source.
        url: Final URL used to retrieve the response.
        collected_at: UTC timestamp recorded when the response was received.
        status_code: HTTP status code, or 200 for a local fixture.
    """

    content: str
    content_type: str
    url: str
    collected_at: str
    status_code: int


def public_source_url(value: str) -> str:
    """Keep the public source address while removing credentials and query data."""
    parts = urlsplit(value)
    hostname = parts.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    try:
        port = parts.port
    except ValueError:
        port = None
    netloc = f"{hostname}:{port}" if port else hostname
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def _csrf_from_html(html: str) -> str | None:
    """Read the request token needed by the source's stock grid."""
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
    """Request the stock page and return the source's raw JSON response."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "VivverEstoqueMVP/0.2 (academic public-interest project)",
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
    })

    page = _get_with_retries(session, config.stock_page)

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

    time.sleep(0.25)
    response = _get_with_retries(session, config.grid_url, params=params)

    return ExtractedResponse(
        content=response.text,
        content_type=response.headers.get("Content-Type", ""),
        url=response.url,
        collected_at=datetime.now(timezone.utc).isoformat(),
        status_code=response.status_code,
    )


def _get_with_retries(
    session: requests.Session,
    url: str,
    params: dict[str, str] | None = None,
) -> requests.Response:
    """Retry transient HTTP and network errors with a bounded delay."""
    retryable_statuses = {429, 500, 502, 503, 504}

    for attempt in range(3):
        try:
            response = session.get(url, params=params, timeout=20)
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(0.5 * (2 ** attempt))
            continue

        if response.status_code in retryable_statuses and attempt < 2:
            try:
                delay = min(60.0, max(0.0, float(response.headers.get("Retry-After", ""))))
            except ValueError:
                delay = 0.5 * (2 ** attempt)
            time.sleep(delay)
            continue
        response.raise_for_status()
        return response

    raise RuntimeError("A coleta terminou sem resposta válida.")


def save_raw(result: ExtractedResponse, raw_dir: Path, prefix: str = "vivver_estoque") -> Path:
    """Preserve the unmodified response body in the raw-data directory."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    stamp = result.collected_at.replace(":", "").replace("+00:00", "Z").replace(".", "")
    path = raw_dir / f"{prefix}_{stamp}.txt"
    path.write_text(result.content, encoding="utf-8")
    return path
