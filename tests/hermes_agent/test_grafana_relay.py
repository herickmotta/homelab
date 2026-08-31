#!/usr/bin/env python3
"""Unit tests for the Grafana-to-Hermes HMAC relay helpers."""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
import tempfile
import unittest
from pathlib import Path

RELAY = (
    Path(__file__).resolve().parents[2]
    / "ansible/roles/hermes_agent/files/grafana_hermes_relay.py"
)


def load_relay():
    spec = importlib.util.spec_from_file_location("grafana_hermes_relay", RELAY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


relay = load_relay()


class RelayHelpers(unittest.TestCase):
    def test_grafana_hmac_with_timestamp(self) -> None:
        body = b'{"status":"firing"}'
        secret = b"grafana-secret"
        ts = "1700000000"
        expected = hmac.new(secret, ts.encode() + b":" + body, hashlib.sha256).hexdigest()
        self.assertEqual(relay.grafana_signature(secret, body, ts), expected)

    def test_nous_v2_hmac(self) -> None:
        body = b'{"event_type":"firing"}'
        secret = b"hermes-secret"
        ts = "1700000000"
        expected = hmac.new(secret, f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
        self.assertEqual(relay.nous_v2_signature(secret, body, ts), expected)

    def test_fingerprints_per_alert(self) -> None:
        payload = {
            "status": "firing",
            "alerts": [
                {"fingerprint": "abc", "startsAt": "2026-01-01T00:00:00Z"},
                {"fingerprint": "def", "startsAt": "2026-01-01T00:00:00Z"},
            ],
        }
        keys = relay.fingerprints(payload, "firing")
        self.assertEqual(len(keys), 2)
        self.assertNotEqual(keys[0], keys[1])

    def test_seen_store_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = relay.SeenStore(Path(tmp), ttl_seconds=60)
            self.assertFalse(store.seen("k1"))
            store.remember("k1")
            self.assertTrue(store.seen("k1"))


if __name__ == "__main__":
    unittest.main()
