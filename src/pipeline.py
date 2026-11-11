"""Run the optional tabular ETL pipeline from raw source data to CSV/Parquet."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .config import Config, PROCESSED_DIR, RAW_DIR
from .extract.source import ExtractedResponse, public_source_url, save_raw
from .extract.sources import DEFAULT_STOCK_SOURCE, StockSource
from .load.load import save_processed
from .transform.normalize import normalize
from .transform.parse import parse_response
from .transform.quality import quality_report


@dataclass(frozen=True)
class TabularPipeline:
    """Coordinate extraction, parsing, normalization, quality checks, and output.

    The tabular route is kept separate from the public JSON snapshot pipeline:
    it produces CSV/Parquet files for local analysis rather than the website.
    """

    config: Config = field(default_factory=Config)
    raw_dir: Path = RAW_DIR
    processed_dir: Path = PROCESSED_DIR
    source: StockSource = DEFAULT_STOCK_SOURCE

    def extract(self, fixture: Path | None = None) -> ExtractedResponse:
        """Fetch source content or construct a response from a local fixture."""
        if fixture is None:
            return self.source.fetch(self.config)
        return ExtractedResponse(
            content=fixture.read_text(encoding="utf-8"),
            content_type="text/html",
            url=fixture.resolve().as_uri(),
            collected_at="fixture",
            status_code=200,
        )

    def transform(self, response: ExtractedResponse) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Parse the response, normalize columns, and build a quality report."""
        raw_frame = parse_response(response.content, response.content_type)
        normalized_frame = normalize(
            raw_frame,
            municipio=self.config.municipio,
            collected_at=response.collected_at,
            source_url=public_source_url(response.url),
        )
        return normalized_frame, quality_report(normalized_frame)

    def load(
        self,
        frame: pd.DataFrame,
        report: pd.DataFrame,
    ) -> tuple[Path, Path, Path | None]:
        """Write the normalized dataset, quality report, and optional Parquet."""
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        report_path = self.processed_dir / "quality_report.csv"
        report.to_csv(report_path, index=False, encoding="utf-8-sig")
        csv_path, parquet_path = save_processed(frame, self.processed_dir)
        return report_path, csv_path, parquet_path

    def run(self, fixture: Path | None = None) -> None:
        """Run the tabular pipeline and print a short summary of each stage."""
        response = self.extract(fixture)
        raw_path = save_raw(response, self.raw_dir)
        print(f"[extract] status={response.status_code}")
        print(f"[extract] raw={raw_path}")

        frame, report = self.transform(response)
        print(f"[transform] shape={frame.shape}")
        print(frame.head(10).to_string(index=False))

        report_path, csv_path, parquet_path = self.load(frame, report)
        print(f"[quality] report={report_path}")
        print(f"[load] csv={csv_path}")
        print(f"[load] parquet={parquet_path or 'skipped (pyarrow unavailable)'}")


def run(fixture: str | None = None) -> None:
    """Preserve the original command-line entry point for the tabular pipeline."""
    TabularPipeline().run(Path(fixture) if fixture else None)


def main() -> None:
    """Parse command-line options and start the local data pipeline."""
    parser = argparse.ArgumentParser(description="Executa a pipeline tabular do estoque.")
    parser.add_argument("--fixture", help="Usa uma resposta local em vez do endpoint.")
    args = parser.parse_args()
    run(args.fixture)


if __name__ == "__main__":
    main()
