"""Explain which stock capture the public page will display."""

from __future__ import annotations

import json
from pathlib import Path

from .config import COLLECTION_STATUS, PUBLIC_SNAPSHOT, RAW_DIR, Config
from .extract.source import public_source_url
from .snapshot_store import is_fixture_capture, raw_collection_time, raw_sort_time
from .transform.snapshot import normalize_stock


def _redact_url(value: object) -> str:
    """Hide query strings, which may contain session or authenticity tokens."""
    try:
        return public_source_url(str(value))
    except ValueError:
        return str(value)


def _snapshot_counts(snapshot: dict) -> tuple[int, int, int]:
    """Count medicines, unit stock rows, and distinct health units."""
    products = snapshot.get("products", [])
    if not isinstance(products, list):
        return 0, 0, 0
    units = [
        unit
        for product in products
        if isinstance(product, dict)
        for unit in product.get("units", [])
        if isinstance(unit, dict)
    ]
    return (
        len(products),
        len(units),
        len({str(unit.get("unit_id", "")) for unit in units if unit.get("unit_id")}),
    )


def diagnose(raw_dir: Path = RAW_DIR, snapshot_path: Path = PUBLIC_SNAPSHOT,
             status_path: Path = COLLECTION_STATUS) -> str:
    """Inspect candidate captures and describe the selected public dataset."""
    lines = ["Diagnóstico local da fonte usada pela interface"]
    status: dict = {}
    try:
        parsed_status = json.loads(status_path.read_text(encoding="utf-8-sig"))
        if isinstance(parsed_status, dict):
            status = parsed_status
    except FileNotFoundError:
        lines.append(f"Status de coleta: ausente ({status_path})")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        lines.append(f"Status de coleta: inválido ({error})")

    if status:
        lines.append(
            "Última tentativa: "
            f"{status.get('last_attempt_status', 'desconhecida')} "
            f"em {status.get('last_attempt_at', 'horário ausente')}"
        )
        lines.append(
            f"Origem registrada: {status.get('source_type', 'não informada')} "
            f"({_redact_url(status.get('source_url') or 'URL não informada')})"
        )
        if status.get("last_error"):
            lines.append(f"Erro da última tentativa: {status['last_error']}")

    candidates = []
    if raw_dir.exists():
        candidates = list(raw_dir.glob("vivver_estoque_*.txt"))
    candidates.sort(key=raw_sort_time, reverse=True)
    valid_snapshots: list[tuple[Path, dict]] = []

    lines.append(f"Capturas encontradas em {raw_dir}: {len(candidates)}")
    for candidate in candidates:
        if is_fixture_capture(candidate, status):
            lines.append(f"- IGNORADA (captura de demonstração): {candidate.name}")
            continue
        try:
            collected_at = raw_collection_time(candidate)
            content = candidate.read_text(encoding="utf-8-sig")
            snapshot = normalize_stock(content, Config().stock_page, collected_at)
        except (OSError, UnicodeDecodeError, TypeError, ValueError) as error:
            lines.append(f"- INVÁLIDA: {candidate.name}: {error}")
            continue

        valid_snapshots.append((candidate, snapshot))

    if valid_snapshots:
        newest_path, newest_snapshot = valid_snapshots[0]
        largest_raw, largest_snapshot = max(
            valid_snapshots,
            key=lambda item: (
                item[1]["metadata"]["product_count"],
                raw_sort_time(item[0]),
            ),
        )
        newest_count = newest_snapshot["metadata"]["product_count"]
        largest_count = largest_snapshot["metadata"]["product_count"]
        selected_raw, selected_snapshot = newest_path, newest_snapshot
        if largest_count >= 50 and newest_count < largest_count * 0.5:
            selected_raw, selected_snapshot = largest_raw, largest_snapshot
            lines.append(
                f"A captura mais recente tem {newest_count} medicamentos, abaixo de 50% "
                f"da captura mais completa ({largest_count}); mantida a captura maior "
                f"como fallback e sinalizada como potencialmente desatualizada."
            )
        for candidate, snapshot in valid_snapshots:
            product_count, row_count, unit_count = _snapshot_counts(snapshot)
            if candidate == selected_raw:
                selection = "SELECIONADA pela interface"
            elif candidate == newest_path and selected_raw != newest_path:
                selection = (
                    "não selecionada: volume muito menor que a captura maior; "
                    "origem precisa ser confirmada"
                )
            else:
                selection = "não selecionada"
            lines.append(
                f"- VÁLIDA estruturalmente ({selection}): {candidate.name} — "
                f"{product_count} medicamentos, {row_count} registros por unidade, "
                f"{unit_count} unidades distintas"
            )
    else:
        selected_raw = None
        selected_snapshot = None

    if selected_raw is not None and selected_snapshot is not None:
        lines.append(f"Fonte que a interface deve usar: raw/{selected_raw.name}")
        counts = _snapshot_counts(selected_snapshot)
        lines.append(
            "Totais exibidos: "
            f"{counts[0]} medicamentos; {counts[1]} registros por unidade; "
            f"{counts[2]} unidades"
        )
        lines.append(
            f"Identificação: {selected_snapshot['metadata']['source']} "
            f"(coletado em {selected_snapshot['metadata']['collected_at']})"
        )
    else:
        lines.append("Nenhuma captura raw válida encontrada; a interface tenta o snapshot JSON.")
        try:
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8-sig"))
            counts = _snapshot_counts(snapshot)
            lines.append(
                f"Snapshot: válido — {counts[0]} medicamentos, "
                f"{counts[1]} registros por unidade, {counts[2]} unidades"
            )
        except FileNotFoundError:
            lines.append(f"Snapshot: ausente ({snapshot_path})")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as error:
            lines.append(f"Snapshot: inválido ({error})")

    if status.get("raw_capture"):
        lines.append(f"Última captura registrada: {status['raw_capture']}")
        if status.get("source_type") is None and status.get("source_url") is None:
            lines.append(
                "Aviso: o status é legado e não registra a origem da última captura. "
                "‘success’ confirma o término do comando, não que a captura represente "
                "o catálogo completo."
            )
    lines.append(
        "Observação: o horário da captura não comprova quando a unidade atualizou o estoque."
    )
    return "\n".join(lines)


def main() -> None:
    """Print the local collection diagnostic report."""
    print(diagnose())


if __name__ == "__main__":
    main()
