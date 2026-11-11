"""Check collection freshness and send a concise operational alert."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from .config import COLLECTION_STATUS, PUBLIC_SNAPSHOT
from .snapshot_store import read_json


@dataclass(frozen=True)
class CollectionMonitor:
    """Detect stale or failed data refreshes and optionally notify a webhook.

    Attributes:
        snapshot_path: Published snapshot used to calculate data age.
        status_path: Most recent collection result.
        webhook_url: Optional Slack-compatible incoming webhook.
        stale_after_hours: Grace period before a snapshot is considered stale.
    """

    snapshot_path: Path = PUBLIC_SNAPSHOT
    status_path: Path = COLLECTION_STATUS
    webhook_url: str = ""
    stale_after_hours: int = 36

    def check(self, now: datetime | None = None) -> list[str]:
        """Return operator-facing reasons to alert, without exposing source URLs."""
        snapshot = read_json(self.snapshot_path)
        status = read_json(self.status_path)
        metadata = snapshot.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        reasons = []
        if status.get("last_attempt_status") == "failed":
            reasons.append("A última tentativa de coleta falhou.")

        collected_at = metadata.get("collected_at")
        try:
            collected = datetime.fromisoformat(str(collected_at).replace("Z", "+00:00"))
            if collected.tzinfo is None:
                collected = collected.replace(tzinfo=timezone.utc)
            current_time = now or datetime.now(timezone.utc)
            if current_time.tzinfo is None:
                current_time = current_time.replace(tzinfo=timezone.utc)
            age = current_time - collected
        except (TypeError, ValueError):
            age = None

        if age is None or age > timedelta(hours=self.stale_after_hours):
            reasons.append(
                f"Os dados publicados têm mais de {self.stale_after_hours} horas "
                "ou o horário da consulta está indisponível."
            )
        return reasons

    def notify(self, reasons: list[str]) -> None:
        """Send an alert when configured; never include source response details."""
        if not reasons or not self.webhook_url:
            return
        message = "Alerta Medi Moc: " + " ".join(reasons)
        try:
            response = requests.post(
                self.webhook_url,
                json={"text": message},
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException:
            raise RuntimeError("Não foi possível enviar o alerta configurado.") from None


def main() -> int:
    """Check collection health and fail scheduled runs when an alert is needed."""
    monitor = CollectionMonitor(
        webhook_url=os.environ.get("COLLECTION_ALERT_WEBHOOK_URL", ""),
        stale_after_hours=int(os.environ.get("COLLECTION_ALERT_AFTER_HOURS", "36")),
    )
    reasons = monitor.check()
    if not reasons:
        print("Coleta saudável: os dados publicados estão atualizados.")
        return 0

    monitor.notify(reasons)
    if not monitor.webhook_url:
        print(
            "ALERTA: " + " ".join(reasons)
            + " Configure COLLECTION_ALERT_WEBHOOK_URL para receber avisos externos."
        )
    else:
        print("Alerta enviado para o canal configurado.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
