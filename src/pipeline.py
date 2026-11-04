from __future__ import annotations

import argparse
from pathlib import Path

from .config import Config, PROCESSED_DIR, RAW_DIR
from .extract.source import ExtractedResponse, save_raw
from .extract.sources import DEFAULT_STOCK_SOURCE
from .load.load import save_processed
from .transform.normalize import normalize
from .transform.parse import parse_response
from .transform.quality import quality_report


def run(fixture: str | None = None) -> None:
    config = Config()

    if fixture:
        path = Path(fixture)
        content = path.read_text(encoding="utf-8")
        result = ExtractedResponse(
            content=content,
            content_type="text/html",
            url=f"file://{path.resolve()}",
            collected_at="fixture",
            status_code=200,
        )
    else:
        result = DEFAULT_STOCK_SOURCE.fetch(config)

    raw_path = save_raw(result, RAW_DIR)
    print(f"[extract] status={result.status_code}")
    print(f"[extract] url={result.url}")
    print(f"[extract] raw={raw_path}")

    df_raw = parse_response(result.content, result.content_type)
    print(f"[parse] shape={df_raw.shape}")
    print(f"[parse] columns={list(df_raw.columns)}")

    df = normalize(
        df_raw,
        municipio=config.municipio,
        collected_at=result.collected_at,
        source_url=result.url,
    )
    print(f"[normalize] shape={df.shape}")
    print(df.head(10).to_string(index=False))

    report = quality_report(df)
    report_path = PROCESSED_DIR / "quality_report.csv"
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    report.to_csv(report_path, index=False, encoding="utf-8-sig")

    csv_path, parquet_path = save_processed(df, PROCESSED_DIR)

    print(f"[quality] report={report_path}")
    print(f"[load] csv={csv_path}")
    if parquet_path:
        print(f"[load] parquet={parquet_path}")
    else:
        print("[load] parquet=skipped (pyarrow/fastparquet unavailable)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", help="Usa uma resposta local em vez do endpoint.")
    args = parser.parse_args()
    run(args.fixture)
