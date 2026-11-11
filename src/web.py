from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from .config import COLLECTION_STATUS, PUBLIC_SNAPSHOT, RAW_DIR
from .presentation import build_home_context
from .snapshot_store import (
    SnapshotRepository,
    is_fixture_capture,
    load_public_snapshot,
    raw_collection_time,
    raw_sort_time,
    search_key,
)

# Backwards-compatible aliases: diagnostics and tests import these names.
_raw_collection_time = raw_collection_time
_raw_sort_time = raw_sort_time
_is_fixture_capture = is_fixture_capture
_search_key = search_key
_load_public_snapshot = load_public_snapshot


def create_app(
    snapshot_path: Path = PUBLIC_SNAPSHOT,
    status_path: Path = COLLECTION_STATUS,
    raw_dir: Path = RAW_DIR,
) -> Flask:
    application = Flask(__name__, template_folder="template")
    application.config["TEMPLATES_AUTO_RELOAD"] = True

    repository = SnapshotRepository(snapshot_path, status_path, raw_dir)

    @application.template_filter("phone_href")
    def phone_href(phone: str) -> str:
        digits = "".join(character for character in phone if character.isdigit() or character == "+")
        return f"tel:{digits}"

    @application.get("/api/medicines")
    def medicine_suggestions():
        query = search_key(request.args.get("q", "").strip())
        if len(query) < 2:
            return jsonify([])

        products = repository.load().snapshot.get("products", [])
        if not isinstance(products, list):
            return jsonify([])

        names = {
            str(product.get("name", "")).strip()
            for product in products
            if isinstance(product, dict)
            and product.get("name")
            and query in search_key(
                f"{product.get('name', '')} {product.get('product_id', '')}"
            )
        }
        ordered_names = sorted(
            names,
            key=lambda name: (search_key(name).find(query), search_key(name)),
        )
        return jsonify(ordered_names[:10])

    @application.get("/")
    def index():
        bundle = repository.load()
        context = build_home_context(
            bundle.snapshot,
            bundle.status,
            request.args,
            datetime.now(timezone.utc),
        )
        return render_template("stock.html", **context)

    return application


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"Servidor local iniciado em http://{host}:{port} (Ctrl+C para encerrar)")
    app.run(host=host, port=port, debug=False, threaded=True)
