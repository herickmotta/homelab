from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from hermes_triage.audit import audit
from hermes_triage.config import Config
from hermes_triage.engine import Engine


def authorize(header: str | None, secret: str) -> bool:
    if not header:
        return False
    scheme, _, token = header.partition(" ")
    return scheme.lower() == "bearer" and token == secret


def handle_webhook(
    engine: Engine,
    authorization: str | None,
    body: bytes,
) -> tuple[int, bytes]:
    if not authorize(authorization, engine.config.webhook_secret):
        audit("webhook_unauthorized")
        return 401, b"unauthorized\n"
    try:
        payload = json.loads(body.decode() or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 400, b"invalid json\n"
    if not isinstance(payload, dict):
        return 400, b"invalid json\n"
    thread = threading.Thread(
        target=_diagnose_later,
        args=(engine, payload),
        name="hermes-alert",
        daemon=True,
    )
    thread.start()
    audit("webhook_accepted")
    return 200, b"accepted\n"


def _diagnose_later(engine: Engine, payload: dict[str, Any]) -> None:
    try:
        engine.diagnose_alert(payload)
    except Exception as exc:  # noqa: BLE001 - never raise into Alertmanager
        audit("webhook_processing_error", error=str(exc))


class WebhookHandler(BaseHTTPRequestHandler):
    engine: Engine
    config: Config

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/healthz":
            self.send_error(404)
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok\n")

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/webhook/alertmanager":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(min(length, 1_000_000))
        status, response = handle_webhook(
            self.engine,
            self.headers.get("Authorization"),
            body,
        )
        self.send_response(status)
        self.end_headers()
        self.wfile.write(response)


def make_server(config: Config, engine: Engine) -> ThreadingHTTPServer:
    WebhookHandler.engine = engine
    WebhookHandler.config = config
    return ThreadingHTTPServer((config.listen_host, config.listen_port), WebhookHandler)
