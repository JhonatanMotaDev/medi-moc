from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..config import Config
from .source import ExtractedResponse, fetch_stock


class StockSource(Protocol):
    source_id: str
    display_name: str

    def fetch(self, config: Config) -> ExtractedResponse:
        ...


@dataclass(frozen=True)
class VivverSource:
    source_id: str = "vivver"
    display_name: str = "Portal Cidadão – Estoque (Vivver)"

    def fetch(self, config: Config) -> ExtractedResponse:
        return fetch_stock(config)


DEFAULT_STOCK_SOURCE = VivverSource()
