#!/usr/bin/env python3
"""Unit tests for the Alertmanager → Hermes HMAC adapter."""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    ROOT
    / "ansible/roles/hermes_agent/files/alertmanager_adapter.py"
)


def load_adapter():
    spec = importlib.util.spec_from_file_location("alertmanager_adapter", MODULE)
    if spec is None or spec.loader is None:
        raise SystemExit("cannot load alertmanager_adapter")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    adapter = load_adapter()
    payload = adapter.bound_payload(
        {
            "version": "4",
            "status": "firing",
            "alerts": [
                {
                    "labels": {
                        "alertname": "ZfsPoolUnhealthy",
                        "severity": "critical",
                        "host": "pve",
                    },
                    "annotations": {
                        "summary": "pool iron is not online",
                        "description": "health != 0",
                    },
                }
            ],
        }
    )
    if payload["alertname"] != "ZfsPoolUnhealthy" or payload["status"] != "firing":
        raise SystemExit("bound_payload must keep allowlisted alert fields")
    if "version" in payload or "alerts" in payload:
        raise SystemExit("bound_payload must not forward the raw Alertmanager body")
    try:
        adapter.bound_payload({"status": "firing", "alerts": []})
    except ValueError:
        pass
    else:
        raise SystemExit("empty alerts must be rejected")
    raw = b'{"alertname":"test"}'
    timestamp = "1700000000"
    signature = adapter.sign_v2("super-secret-value", timestamp, raw)
    expected = hmac.new(
        b"super-secret-value",
        timestamp.encode("ascii") + b"." + raw,
        hashlib.sha256,
    ).hexdigest()
    if signature != expected:
        raise SystemExit("HMAC-v2 signature must be hex(timestamp.body)")
    print("alert adapter unit tests ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
