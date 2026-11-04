from dataclasses import dataclass
from pathlib import Path

BASE_URL = "https://www.montesclaros-mg.vivver.com"
STOCK_PAGE = f"{BASE_URL}/estoque"
GRID_URL = f"{BASE_URL}/cid/estoque_lista/grid_busca"
MUNICIPIO = "3143302"

DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
AVAILABLE_DIR = DATA_DIR / "avaliable"
PUBLIC_SNAPSHOT = PROCESSED_DIR / "public_snapshot.json"
COLLECTION_STATUS = PROCESSED_DIR / "collection_status.json"

@dataclass(frozen=True)
class Config:
    municipio: str = MUNICIPIO
    stock_page: str = STOCK_PAGE
    grid_url: str = GRID_URL
