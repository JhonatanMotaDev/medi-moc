from __future__ import annotations

import pandas as pd


def quality_report(df: pd.DataFrame) -> pd.DataFrame:
    report = pd.DataFrame({
        "coluna": df.columns,
        "tipo": [str(df[c].dtype) for c in df.columns],
        "linhas": len(df),
        "nulos": [int(df[c].isna().sum()) for c in df.columns],
        "nulos_pct": [round(float(df[c].isna().mean() * 100), 2) for c in df.columns],
        "distintos": [int(df[c].nunique(dropna=True)) for c in df.columns],
    })
    return report
