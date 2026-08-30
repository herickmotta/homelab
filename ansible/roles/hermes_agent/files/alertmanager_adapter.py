#!/usr/bin/env python3
"""Accept Alertmanager bearer webhooks and sign Hermes HMAC-v2 loopback POSTs.

Do not log secrets, Authorization headers, or raw alert payloads.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MAX_BODY = int(os.environ.get("ADAPTER_MAX_BODY", "65536"))
RATE_PER_MIN = int(os.environ.get("ADAPTER_RATE_PER_MIN", "30"))
DEDUP_TTL = int(os.environ.get("ADAPTER_DEDUP_TTL", "3600"))
LISTEN_HOST = os.environ.get("ADAPTER_LISTEN_HOST", "127.0.0.1")
LISTEN_PORT = int(os.environ.get("ADAPTER_LISTEN_PORT", "8787"))
ALLOW_FROM = os.environ.get("ADAPTER_ALLOW_FROM", "")
BEARER = os.environ.get("ADAPTER_BEARER_TOKEN", "")
HERMES_URL = os.environ.get("HERMES_WEBHOOK_URL", "http://127.0.0.1:8644/webhooks/homelab-ops")
HERMES_SECRET = os.environ.get("HERMES_WEBHOOK_SECRET", "")

_rate_lock = threading.Lock()
_rate_window = 0
_rate_count = 0
_dedup_lock = threading.Lock()
_dedup: dict[str, float] = {}


def _client_ip(handler: BaseHTTPRequestHandler) -> str:
    return handler.client_address[0]


def _allowed(ip: str) -> bool:
    if not ALLOW_FROM:
        return False
    return ip == ALLOW_FROM


def _rate_ok() -> bool:
    global _rate_window, _rate_count
    now = int(time.time() // 60)
    with _rate_lock:
        if now != _rate_window:
            _rate_window = now
            _rate_count = 0
        if _rate_count >= RATE_PER_MIN:
            return False
        _rate_count += 1
        return True


def _dedup_ok(key: str) -> bool:
    now = time.time()
    with _dedup_lock:
        expired = [item for item, expiry in _dedup.items() if expiry <= now]
        for item in expired:
            del _dedup[item]
        if key in _dedup:
            return False
        _dedup[key] = now + DEDUP_TTL
        return True


def _bearer_ok(handler: BaseHTTPRequestHandler) -> bool:
    if not BEARER or len(BEARER) < 16:
        return False
    header = handler.headers.get("Authorization", "")
    expected = "Bearer " + BEARER
    if len(header) != len(expected):
        return False
    return hmac.compare_digest(header, expected)


def _first_str(mapping: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value:
            return value[:500]
    return ""


def bound_payload(body: dict[str, Any]) -> dict[str, str]:
    status = body.get("status")
    if status not in ("firing", "resolved"):
        raise ValueError("status")
    alerts = body.get("alerts")
    if not isinstance(alerts, list) or not alerts:
        raise ValueError("alerts")
    first = alerts[0]
    if not isinstance(first, dict):
        raise ValueError("alert")
    labels = first.get("labels") if isinstance(first.get("labels"), dict) else {}
    annotations = (
        first.get("annotations") if isinstance(first.get("annotations"), dict) else {}
    )
    common = body.get("commonLabels") if isinstance(body.get("commonLabels"), dict) else {}
    return {
        "event_type": "alert",
        "status": status,
        "alertname": _first_str(labels, "alertname") or _first_str(common, "alertname"),
        "severity": _first_str(labels, "severity") or _first_str(common, "severity"),
        "host": _first_str(labels, "host") or _first_str(common, "host"),
        "instance": _first_str(labels, "instance") or _first_str(common, "instance"),
        "summary": _first_str(annotations, "summary"),
        "description": _first_str(annotations, "description"),
        "firing_count": str(min(len(alerts), 50)),
    }


def sign_v2(secret: str, timestamp: str, raw: bytes) -> str:
    message = timestamp.encode("ascii") + b"." + raw
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def forward(payload: dict[str, str]) -> int:
    if not HERMES_SECRET or len(HERMES_SECRET) < 16:
        return 500
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    signature = sign_v2(HERMES_SECRET, timestamp, raw)
    req = Request(HERMES_URL, data=raw, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Webhook-Timestamp", timestamp)
    req.add_header("X-Webhook-Signature-V2", signature)
    req.add_header("X-Request-ID", hashlib.sha256(raw).hexdigest()[:32])
    try:
        with urlopen(req, timeout=15) as resp:
            return int(resp.status)
    except HTTPError as exc:
        return int(exc.code)
    except URLError:
        return 502


class AdapterHandler(BaseHTTPRequestHandler):
    server_version = "hermes-alert-adapter/1"

    def log_message(self, fmt: str, *args: object) -> None:
        sys_stderr = __import__("sys").stderr
        sys_stderr.write(
            "%s %s %s\n" % (self.log_date_time_string(), _client_ip(self), fmt % args)
        )

    def _send(self, code: int, body: bytes, content_type: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] != "/health":
            self._send(404, b'{"status":"not_found"}')
            return
        self._send(200, b'{"status":"ok"}')

    def do_POST(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] != "/alerts":
            self._send(404, b'{"status":"not_found"}')
            return
        if not _allowed(_client_ip(self)):
            self._send(403, b'{"status":"forbidden"}')
            return
        if not _bearer_ok(self):
            self._send(401, b'{"status":"unauthorized"}')
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length < 2 or length > MAX_BODY:
            self._send(413, b'{"status":"too_large"}')
            return
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send(400, b'{"status":"bad_json"}')
            return
        if not isinstance(body, dict):
            self._send(400, b'{"status":"bad_json"}')
            return
        try:
            payload = bound_payload(body)
        except ValueError:
            self._send(400, b'{"status":"bad_payload"}')
            return
        if not _rate_ok():
            self._send(429, b'{"status":"rate_limited"}')
            return
        dedup_key = "|".join(
            (
                payload["status"],
                payload["alertname"],
                payload["host"],
                payload["instance"],
                payload["summary"],
            )
        )
        if not _dedup_ok(dedup_key):
            self._send(200, b'{"status":"duplicate"}')
            return
        status = forward(payload)
        if 200 <= status < 300:
            self._send(200, b'{"status":"forwarded"}')
            return
        self._send(502, b'{"status":"upstream_failed"}')


def main() -> int:
    if len(BEARER) < 16 or len(HERMES_SECRET) < 16 or not ALLOW_FROM:
        print("adapter missing bearer, hmac secret, or allow-from", file=__import__("sys").stderr)
        return 1
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), AdapterHandler)
    print(f"listening on {LISTEN_HOST}:{LISTEN_PORT}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
