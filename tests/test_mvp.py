from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.extract.collector import collect
from src.transform.snapshot import SnapshotValidationError, normalize_stock
from src.diagnostics import diagnose
from src.web import _raw_collection_time, create_app
from src.extract.sources import VivverSource


FIXTURE = Path(__file__).parent / "fixtures" / "stock_demo.json"


def test_normalize_stock_keeps_unit_records_and_explains_freshness():
    snapshot = normalize_stock(
        FIXTURE.read_text(encoding="utf-8"),
        "https://source.example/stock",
        "2026-09-30T12:00:00+00:00",
    )

    assert snapshot["metadata"]["product_count"] == 2
    assert snapshot["metadata"]["unit_stock_rows"] == 3
    assert snapshot["metadata"]["source_updated_at"] is None
    assert snapshot["products"][0]["units"][0]["quantity"] == 12
    assert "não informa quando" in snapshot["metadata"]["freshness_note"]


def test_vivver_source_has_explicit_identity():
    source = VivverSource()

    assert source.source_id == "vivver"
    assert source.display_name == "Portal Cidadão – Estoque (Vivver)"


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        "[]",
        '[{"id_produto":1,"nomproduto":"SEM ESTOQUE_UNIDADE"}]',
        '[{"id_produto":1,"nomproduto":"TESTE","estoque_unidade":[{"codunidade":1,"nomfantasia":"UBS","qdeestoque":-1}]}]',
        '[{"id_produto":1,"nomproduto":"TESTE","estoque_unidade":[{"codunidade":1,"nomfantasia":"UBS","qdeestoque":"x"}]}]',
        '[{"id_produto":1,"nomproduto":"TESTE","estoque_unidade":[{"codunidade":1,"nomfantasia":"UBS","qdeestoque":2},{"codunidade":1,"nomfantasia":"UBS","qdeestoque":3}]}]',
    ],
)
def test_invalid_source_payloads_are_not_publishable(payload):
    with pytest.raises(SnapshotValidationError):
        normalize_stock(payload, "https://source.example/stock", "2026-09-30T12:00:00+00:00")


def test_collection_publishes_fixture_with_demo_label_and_status(tmp_path):
    snapshot_path = tmp_path / "public_snapshot.json"
    status_path = tmp_path / "collection_status.json"
    raw_dir = tmp_path / "raw"

    snapshot = collect(FIXTURE, snapshot_path, status_path, raw_dir)

    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert snapshot["metadata"]["source"] == "Fixture local de demonstração"
    assert "fictícios" in snapshot["metadata"]["freshness_note"]
    assert snapshot_path.exists()
    assert status["last_attempt_status"] == "success"
    assert status["last_success_at"] == snapshot["metadata"]["collected_at"]
    assert Path(status["raw_capture"]).exists()


def test_failed_collection_preserves_last_valid_snapshot_and_records_failure(tmp_path):
    snapshot_path = tmp_path / "public_snapshot.json"
    status_path = tmp_path / "collection_status.json"
    raw_dir = tmp_path / "raw"
    valid_snapshot = collect(FIXTURE, snapshot_path, status_path, raw_dir)
    invalid_fixture = tmp_path / "invalid.json"
    invalid_fixture.write_text("{}", encoding="utf-8")

    with pytest.raises(SnapshotValidationError):
        collect(invalid_fixture, snapshot_path, status_path, raw_dir)

    saved_snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert saved_snapshot == valid_snapshot
    assert status["last_attempt_status"] == "failed"
    assert status["last_success_at"] == valid_snapshot["metadata"]["collected_at"]
    assert "lista não vazia" in status["last_error"]
    assert len(list(raw_dir.glob("*.txt"))) == 2


def test_public_search_filters_medicines_and_units_accent_insensitively(tmp_path):
    snapshot = normalize_stock(
        FIXTURE.read_text(encoding="utf-8"),
        "https://source.example/stock",
        "2026-09-30T12:00:00+00:00",
    )
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    client = create_app(snapshot_path, tmp_path / "status.json").test_client()

    response = client.get("/?q=dipirona&unidade=1")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "DIPIRONA SÓDICA 500 MG" in page
    assert "UBS São Judas" in page
    assert "UBS Maracanã" not in page
    assert "12 COMPRIMIDO na consulta" in page
    assert "tel:3822114461" in page
    assert "não informa quando" in page
    assert "não confirmam o estoque" in page


def test_header_and_search_card_use_concise_independent_project_copy(tmp_path):
    snapshot = normalize_stock(
        FIXTURE.read_text(encoding="utf-8"),
        "https://source.example/stock",
        "2026-09-30T12:00:00+00:00",
    )
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    client = create_app(snapshot_path, tmp_path / "status.json").test_client()

    page = client.get("/").get_data(as_text=True)

    assert "Projeto de extensão · Afya Montes Claros" in page
    assert "Consultar fonte oficial" in page
    assert "Buscar medicamento" in page
    assert "Digite o nome do medicamento" in page
    assert "Você pode digitar o nome completo ou apenas uma parte." in page
    assert "Filtrar por unidade" in page
    assert '<details class="unit-filter">' in page
    assert "O que você está procurando?" not in page
    assert "As sugestões aparecem a partir de 2 letras" not in page


def test_medicine_autocomplete_returns_accent_insensitive_suggestions(tmp_path):
    snapshot = normalize_stock(
        FIXTURE.read_text(encoding="utf-8"),
        "https://source.example/stock",
        "2026-09-30T12:00:00+00:00",
    )
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    client = create_app(snapshot_path, tmp_path / "status.json").test_client()

    response = client.get("/api/medicines?q=dipir")

    assert response.status_code == 200
    assert response.get_json() == ["DIPIRONA SÓDICA 500 MG"]


def test_unit_dropdown_filters_to_selected_unit_and_can_search_without_medicine(tmp_path):
    snapshot = normalize_stock(
        FIXTURE.read_text(encoding="utf-8"),
        "https://source.example/stock",
        "2026-09-30T12:00:00+00:00",
    )
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    client = create_app(snapshot_path, tmp_path / "status.json").test_client()

    filtered = client.get("/?q=dipirona&unidade=1").get_data(as_text=True)
    unit_only = client.get("/?unidade=2").get_data(as_text=True)

    assert 'value="1" selected' in filtered
    assert "UBS São Judas" in filtered
    assert "UBS Maracanã" not in filtered
    assert "DIPIRONA SÓDICA 500 MG" in unit_only
    assert "PARACETAMOL 750 MG" not in unit_only


def test_public_search_shows_failed_update_warning(tmp_path):
    snapshot = normalize_stock(
        FIXTURE.read_text(encoding="utf-8"),
        "https://source.example/stock",
        "2026-09-30T12:00:00+00:00",
    )
    snapshot_path = tmp_path / "snapshot.json"
    status_path = tmp_path / "status.json"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    status_path.write_text(
        json.dumps({"last_attempt_status": "failed", "last_error": "Timeout de rede"}),
        encoding="utf-8",
    )
    client = create_app(snapshot_path, status_path).test_client()

    response = client.get("/")

    assert response.status_code == 200
    assert "A última tentativa de atualização falhou." in response.get_data(as_text=True)


def test_public_page_and_autocomplete_read_raw_txt_without_snapshot(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    raw_path = raw_dir / "vivver_estoque_2026-09-30T101112123456Z.txt"
    raw_path.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    app = create_app(tmp_path / "missing_snapshot.json", tmp_path / "status.json", raw_dir)
    client = app.test_client()

    page = client.get("/?q=dipirona").get_data(as_text=True)
    suggestions = client.get("/api/medicines?q=dipir")

    assert "DIPIRONA SÓDICA 500 MG" in page
    assert suggestions.get_json() == ["DIPIRONA SÓDICA 500 MG"]
    assert "2026-09-30 10:11:12.123456 UTC" in page


def test_raw_collection_time_uses_timestamp_in_historical_filename(tmp_path):
    raw_path = tmp_path / "vivver_estoque_2026-09-22T131443016020+0000.txt"

    assert _raw_collection_time(raw_path) == "2026-09-22T13:14:43.016020+00:00"


def test_latest_fixture_file_is_ignored_in_favor_of_timestamped_raw(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    actual_capture = raw_dir / "vivver_estoque_2026-09-22T131443016020+0000.txt"
    fixture_capture = raw_dir / "vivver_estoque_fixture.txt"
    actual_capture.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    fixture_capture.write_text("not a data capture", encoding="utf-8")
    app = create_app(tmp_path / "missing_snapshot.json", tmp_path / "status.json", raw_dir)
    client = app.test_client()

    response = client.get("/?q=dipirona")
    report = diagnose(
        raw_dir,
        tmp_path / "missing_snapshot.json",
        tmp_path / "status.json",
    )

    assert "DIPIRONA SÓDICA 500 MG" in response.get_data(as_text=True)
    assert "Fonte que a interface deve usar: raw/vivver_estoque_2026-09-22T131443016020+0000.txt" in report
    assert "IGNORADA (captura de demonstração): vivver_estoque_fixture.txt" in report


def test_timestamped_capture_marked_as_fixture_is_ignored_for_real_capture(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    real_payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for product_id in range(1003, 1216):
        product = dict(real_payload[0])
        product["id_produto"] = product_id
        product["nomproduto"] = f"MEDICAMENTO {product_id}"
        product["estoque_unidade"] = [dict(real_payload[0]["estoque_unidade"][0])]
        product["estoque_unidade"][0]["id_produto"] = product_id
        real_payload.append(product)
    real_path = raw_dir / "vivver_estoque_2026-09-22T131443016020+0000.txt"
    real_path.write_text(json.dumps(real_payload, ensure_ascii=False), encoding="utf-8")
    demo_path = raw_dir / "vivver_estoque_2026-09-30T133518192183+0000.txt"
    demo_path.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    status_path = tmp_path / "status.json"
    status_path.write_text(
        json.dumps({
            "last_attempt_status": "success",
            "source_type": "fixture",
            "raw_capture": str(demo_path),
            "last_success_at": "2026-09-30T13:35:18.192183+00:00",
        }),
        encoding="utf-8",
    )
    snapshot_path = tmp_path / "snapshot.json"
    app = create_app(snapshot_path, status_path, raw_dir)
    client = app.test_client()

    page = client.get("/").get_data(as_text=True)
    report = diagnose(raw_dir, snapshot_path, status_path)

    assert "215" in page
    assert "VÁLIDA estruturalmente (SELECIONADA pela interface): vivver_estoque_2026-09-22T131443016020+0000.txt" in report
    assert "VÁLIDA estruturalmente (não selecionada: volume muito menor que a captura maior; origem precisa ser confirmada): vivver_estoque_2026-09-30T133518192183+0000.txt" in report
    assert "215 medicamentos" in report


def test_file_url_identifies_timestamped_fixture_even_without_source_type(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    real_payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for product_id in range(1003, 1216):
        product = dict(real_payload[0])
        product["id_produto"] = product_id
        product["nomproduto"] = f"MEDICAMENTO {product_id}"
        product["estoque_unidade"] = [dict(real_payload[0]["estoque_unidade"][0])]
        product["estoque_unidade"][0]["id_produto"] = product_id
        real_payload.append(product)
    real_path = raw_dir / "vivver_estoque_2026-09-22T131443016020+0000.txt"
    real_path.write_text(json.dumps(real_payload, ensure_ascii=False), encoding="utf-8")
    fixture_path = raw_dir / "vivver_estoque_2026-09-30T133518192183+0000.txt"
    fixture_path.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    status_path = tmp_path / "status.json"
    status_path.write_text(
        json.dumps({
            "last_attempt_status": "success",
            "raw_capture": str(fixture_path),
            "source_url": fixture_path.resolve().as_uri(),
        }),
        encoding="utf-8",
    )
    snapshot_path = tmp_path / "snapshot.json"
    client = create_app(snapshot_path, status_path, raw_dir).test_client()
    report = diagnose(raw_dir, snapshot_path, status_path)

    page = client.get("/").get_data(as_text=True)

    assert "215" in page
    assert "Origem registrada: não informada (file://" in report
    assert "IGNORADA (captura de demonstração): vivver_estoque_2026-09-30T133518192183+0000.txt" in report
    assert "Fonte que a interface deve usar: raw/vivver_estoque_2026-09-22T131443016020+0000.txt" in report


def test_catalog_lists_all_products_in_pages(tmp_path):
    products = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for product_id in range(1003, 1033):
        product = dict(products[0])
        product["id_produto"] = product_id
        product["nomproduto"] = f"MEDICAMENTO {product_id}"
        product["estoque_unidade"] = [dict(products[0]["estoque_unidade"][0])]
        product["estoque_unidade"][0]["id_produto"] = product_id
        products.append(product)
    snapshot = normalize_stock(
        json.dumps(products, ensure_ascii=False),
        "https://source.example/stock",
        "2026-09-30T12:00:00+00:00",
    )
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    client = create_app(snapshot_path, tmp_path / "status.json").test_client()

    first_page = client.get("/?catalogo=1&pagina=1").get_data(as_text=True)
    second_page = client.get("/?catalogo=1&pagina=2").get_data(as_text=True)

    assert "Medicamentos consultados" in first_page
    assert "página 1 de 2" in first_page
    assert "página 2 de 2" in second_page
    assert "MEDICAMENTO 1032" not in first_page
    assert "MEDICAMENTO 1032" in second_page


def test_public_page_includes_unit_map_and_location_directory(tmp_path):
    snapshot = normalize_stock(
        FIXTURE.read_text(encoding="utf-8"),
        "https://source.example/stock",
        "2026-09-30T12:00:00+00:00",
    )
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    client = create_app(snapshot_path, tmp_path / "status.json").test_client()

    page = client.get("/").get_data(as_text=True)

    assert 'id="unit-map"' in page
    assert 'id="map-unit-select"' in page
    assert "UBS São Judas" in page
    assert "Rua Padre Vieira, 620" in page
    assert "medicamentos com quantidade positiva" in page


def test_map_coordinates_are_explicitly_sourced_and_valid():
    locations_path = Path(__file__).parents[1] / "src" / "static" / "unit_locations.json"
    location_data = json.loads(locations_path.read_text(encoding="utf-8"))

    assert location_data["source"] == "OpenStreetMap"
    location_ids = {item["unit_id"] for item in location_data["locations"]}
    assert {"214", "778", "868"}.issubset(location_ids)
    assert len(location_ids) == 31
    for location in location_data["locations"]:
        assert -90 <= location["latitude"] <= 90
        assert -180 <= location["longitude"] <= 180
        assert location["osm_url"].startswith("https://www.openstreetmap.org/")
        assert location["source_address"]
        assert location["location_status"] in {"verified", "provisional"}
        if location["location_status"] == "provisional":
            assert "provisoriamente" in location["source_address_note"]
