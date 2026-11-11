"""Persist the normalized tabular dataset for local analysis."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def save_processed(df: pd.DataFrame, out_dir: Path) -> tuple[Path, Path | None]:
    """Write CSV and, when supported, Parquet output files."""
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "estoque_montes_claros.csv"
    parquet_path = out_dir / "estoque_montes_claros.parquet"

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    # Parquet is optional for this MVP; CSV remains available if pyarrow
    # cannot be installed in the execution environment.
    try:
        df.to_parquet(parquet_path, index=False)
    except ImportError:
        parquet_path = None

    return csv_path, parquet_path
