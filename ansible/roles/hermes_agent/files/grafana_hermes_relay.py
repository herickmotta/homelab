#!/usr/bin/env python3
"""Translate Grafana Alerting HMAC webhooks into Hermes HMAC-v2.

Single-purpose: authenticate Grafana, bound the body, drop duplicates, sign
Nous HMAC-v2, and POST to loopback Hermes. No shell, no Docker, no forward
except the configured Hermes URL.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MAX_SKEW_SECONDS = 300


def grafana_signature(secret: bytes, body: bytes, timestamp: str | None) -> str:
    if timestamp:
        signed = timestamp.encode() + b":" + body
    else:
        signed = body
    return hmac.new(secret, signed, hashlib.sha256).hexdigest()


def nous_v2_signature(secret: bytes, body: bytes, timestamp: str) -> str:
    return hmac.new(secret, f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()


def fingerprints(payload: object, event_type: str) -> list[str]:
    if not isinstance(payload, dict):
        return [hashlib.sha256(f"{event_type}:all".encode()).hexdigest()]
    alerts = payload.get("alerts")
    if not isinstance(alerts, list) or not alerts:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return [hashlib.sha256(event_type.encode() + b":" + raw).hexdigest()]
    keys = []
    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        fp = str(alert.get("fingerprint") or "")
        starts = str(alert.get("startsAt") or "")
        keys.append(hashlib.sha256(f"{event_type}:{fp}:{starts}".encode()).hexdigest())
    return keys or [hashlib.sha256(f"{event_type}:empty".encode()).hexdigest()]


class SeenStore:
    def __init__(self, directory: Path, ttl_seconds: int = 3600) -> None:
        self.directory = directory
        self.ttl_seconds = ttl_seconds
        self.directory.mkdir(parents=True, exist_ok=True)

    def seen(self, key: str) -> bool:
        path = self.directory / key
        if not path.exists():
            return False
        age = time.time() - path.stat().st_mtime
        if age > self.ttl_seconds:
            path.unlink(missing_ok=True)
            return False
        return True

    def remember(self, key: str) -> None:
        path = self.directory / key
        path.write_text("1", encoding="utf-8")


class RateLimiter:
    def __init__(self, per_minute: int) -> None:
        self.per_minute = max(1, per_minute)
        self.events: list[float] = []

    def allow(self) -> bool:
        now = time.time()
        cutoff = now - 60
        self.events = [stamp for stamp in self.events if stamp >= cutoff]
        if len(self.events) >= self.per_minute:
            return False
        self.events.append(now)
        return True


def make_handler(settings: dict):
    grafana_secret = settings["grafana_secret"]
    hermes_secret = settings["hermes_secret"]
    allow_from = settings["allow_from"]
    max_body = settings["max_body"]
    hermes_url = settings["hermes_url"]
    store: SeenStore = settings["store"]
    limiter: RateLimiter = settings["limiter"]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

        def _reject(self, code: int, reason: str) -> None:
            body = json.dumps({"status": "error", "reason": reason}).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _ok(self, payload: dict, code: int = 200) -> None:
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802
            peer = self.client_address[0]
            if peer != allow_from:
                self._reject(403, "source")
                return
            if self.path.rstrip("/") != "/grafana":
                self._reject(404, "path")
                return
            length = int(self.headers.get("Content-Length") or "0")
            if length <= 0 or length > max_body:
                self._reject(413, "size")
                return
            body = self.rfile.read(length)
            timestamp = self.headers.get("X-Grafana-Alerting-Timestamp")
            provided = self.headers.get("X-Grafana-Alerting-Signature") or ""
            expected = grafana_signature(grafana_secret, body, timestamp)
            if not hmac.compare_digest(provided, expected):
                self._reject(401, "hmac")
                return
            if timestamp:
                try:
                    age = abs(time.time() - int(timestamp))
                except ValueError:
                    self._reject(401, "timestamp")
                    return
                if age > MAX_SKEW_SECONDS:
                    self._reject(401, "replay")
                    return
            if not limiter.allow():
                self._reject(429, "rate")
                return
            try:
                payload = json.loads(body.decode())
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._reject(400, "json")
                return
            status = ""
            if isinstance(payload, dict):
                status = str(payload.get("status") or "")
            event_type = "resolved" if status == "resolved" else "firing"
            keys = fingerprints(payload, event_type)
            if keys and all(store.seen(key) for key in keys):
                self._ok({"status": "duplicate"})
                return
            forwarded = json.dumps(
                {
                    "event_type": event_type,
                    "status": status or event_type,
                    "grafana": payload,
                },
                separators=(",", ":"),
            ).encode()
            ts = str(int(time.time()))
            signature = nous_v2_signature(hermes_secret, forwarded, ts)
            request = Request(
                hermes_url,
                data=forwarded,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature-V2": signature,
                    "X-Webhook-Timestamp": ts,
                    "X-Webhook-Event": event_type,
                },
            )
            try:
                with urlopen(request, timeout=20) as response:
                    hermes_status = response.status
                    hermes_body = response.read()[:512]
            except HTTPError as exc:
                self._reject(502, f"hermes-{exc.code}")
                return
            except URLError:
                self._reject(502, "hermes-down")
                return
            if hermes_status >= 400:
                self._reject(502, f"hermes-{hermes_status}")
                return
            for key in keys:
                store.remember(key)
            self._ok({"status": "forwarded", "hermes": hermes_status})

        def do_GET(self) -> None:  # noqa: N802
            if self.path.rstrip("/") == "/healthz":
                self._ok({"status": "ok"})
                return
            self._reject(404, "path")

    return Handler


def main() -> int:
    allow_from = os.environ["RELAY_ALLOW_FROM"]
    grafana_secret = os.environ["GRAFANA_WEBHOOK_HMAC_SECRET"].encode()
    hermes_secret = os.environ["HERMES_ALERT_WEBHOOK_SECRET"].encode()
    listen_host = os.environ.get("RELAY_LISTEN_HOST", "127.0.0.1")
    listen_port = int(os.environ.get("RELAY_LISTEN_PORT", "8787"))
    hermes_url = os.environ.get(
        "HERMES_WEBHOOK_URL",
        "http://127.0.0.1:8644/webhooks/grafana-alert",
    )
    max_body = int(os.environ.get("RELAY_MAX_BODY_BYTES", "65536"))
    rate = int(os.environ.get("RELAY_RATE_PER_MINUTE", "30"))
    state_dir = Path(os.environ.get("RELAY_STATE_DIR", "/var/lib/grafana-hermes-relay"))
    settings = {
        "allow_from": allow_from,
        "grafana_secret": grafana_secret,
        "hermes_secret": hermes_secret,
        "max_body": max_body,
        "hermes_url": hermes_url,
        "store": SeenStore(state_dir),
        "limiter": RateLimiter(rate),
    }
    server = ThreadingHTTPServer((listen_host, listen_port), make_handler(settings))
    server.serve_forever()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyError as exc:
        sys.stderr.write(f"missing env {exc.args[0]}\n")
        raise SystemExit(1)
