from __future__ import annotations

import json
import logging
from typing import Any

_LOG = logging.getLogger("hermes")


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def audit(event: str, **fields: Any) -> None:
    payload = {"event": event, **_redact(fields)}
    _LOG.info(json.dumps(payload, default=str, separators=(",", ":")))


def _redact(fields: dict[str, Any]) -> dict[str, Any]:
    blocked = {
        "token",
        "secret",
        "password",
        "authorization",
        "api_key",
        "webhook_secret",
    }
    clean: dict[str, Any] = {}
    for key, value in fields.items():
        lowered = key.lower()
        if any(part in lowered for part in blocked):
            clean[key] = "[redacted]"
        elif isinstance(value, str) and len(value) > 500:
            clean[key] = value[:500] + "…"
        else:
            clean[key] = value
    return clean
