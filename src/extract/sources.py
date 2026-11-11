"""Source adapters for retrieving public stock records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..config import Config
from .source import ExtractedResponse, fetch_stock


class StockSource(Protocol):
    """Contract implemented by each authorized stock-data source."""

    source_id: str
    display_name: str

    def fetch(self, config: Config) -> ExtractedResponse:
        """Return the raw response and its collection metadata."""
        ...


@dataclass(frozen=True)
class VivverSource:
    """Adapter for the Vivver public stock portal."""

    source_id: str = "vivver"
    display_name: str = "Portal Cidadão – Estoque (Vivver)"

    def fetch(self, config: Config) -> ExtractedResponse:
        """Fetch the current stock response from the Vivver portal."""
        return fetch_stock(config)


DEFAULT_STOCK_SOURCE = VivverSource()
