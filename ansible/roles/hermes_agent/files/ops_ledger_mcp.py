#!/usr/bin/env python3
"""Typed ops_ledger MCP sidecar. Holds the ledger JWT, not backup IAM keys."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LISTEN = os.environ.get("OPS_LEDGER_MCP_LISTEN", "0.0.0.0:8010")
CALLER = os.environ.get("MCP_CALLER_TOKEN", "")
LEDGER_JWT = os.environ.get("OPS_LEDGER_JWT", "")
LEDGER_URL = os.environ.get("OPS_LEDGER_URL", "").rstrip("/")
PROTOCOL = "2024-11-05"

TOOLS = [
    {
        "name": "list_incidents",
        "description": "List recent ops_ledger incidents",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}},
        },
    },
    {
        "name": "get_incident",
        "description": "Get one incident and its events",
        "inputSchema": {
            "type": "object",
            "properties": {"incident_id": {"type": "string"}},
            "required": ["incident_id"],
        },
    },
    {
        "name": "append_event",
        "description": "Append an incident event via PostgREST RPC",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "kind": {"type": "string"},
                "body": {"type": "object"},
                "incident_id": {"type": "string"},
            },
            "required": ["title", "kind"],
        },
    },
    {
        "name": "add_feedback",
        "description": "Append operator feedback to an incident",
        "inputSchema": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["incident_id", "body"],
        },
    },
]


def _rest(path: str, method: str = "GET", payload: dict | None = None):
    url = LEDGER_URL + path
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + LEDGER_JWT)
    req.add_header("Accept", "application/json")
    if payload is not None:
        req.add_header("Content-Type", "application/json")
        req.add_header("Prefer", "return=representation")
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = resp.read()
        if not body:
            return None
        return json.loads(body.decode())


def _call_tool(name: str, arguments: dict) -> object:
    if name == "list_incidents":
        limit = int(arguments.get("limit") or 20)
        return _rest(f"/rest/v1/incidents?select=*&order=updated_at.desc&limit={limit}")
    if name == "get_incident":
        iid = urllib.parse.quote(str(arguments["incident_id"]))
        incident = _rest(f"/rest/v1/incidents?id=eq.{iid}&select=*")
        events = _rest(
            f"/rest/v1/events?incident_id=eq.{iid}&select=*&order=created_at.asc"
        )
        feedback = _rest(
            f"/rest/v1/feedback?incident_id=eq.{iid}&select=*&order=created_at.asc"
        )
        return {"incident": incident, "events": events, "feedback": feedback}
    if name == "append_event":
        payload = {
            "p_title": arguments["title"],
            "p_kind": arguments["kind"],
            "p_body": arguments.get("body") or {},
        }
        if arguments.get("incident_id"):
            payload["p_incident_id"] = arguments["incident_id"]
        return _rest("/rest/v1/rpc/append_event", method="POST", payload=payload)
    if name == "add_feedback":
        payload = {
            "p_incident_id": arguments["incident_id"],
            "p_body": arguments["body"],
        }
        return _rest("/rest/v1/rpc/add_feedback", method="POST", payload=payload)
    raise ValueError("unknown tool")


def _rpc(message: dict) -> dict | None:
    method = message.get("method")
    req_id = message.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": PROTOCOL,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "ops-ledger", "version": "1"},
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = message.get("params") or {}
        try:
            result = _call_tool(params.get("name"), params.get("arguments") or {})
            text = json.dumps(result)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": text}]},
            }
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, KeyError) as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": type(exc).__name__},
            }
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": "method not found"},
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        return

    def _auth_ok(self) -> bool:
        header = self.headers.get("Authorization", "")
        return bool(CALLER) and header == "Bearer " + CALLER

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") == "/healthz":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") != "/mcp":
            self.send_response(404)
            self.end_headers()
            return
        if not self._auth_ok():
            self.send_response(401)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            message = json.loads(raw.decode() or "{}")
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return
        reply = _rpc(message)
        if reply is None:
            self.send_response(202)
            self.end_headers()
            return
        body = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    host, port_s = LISTEN.rsplit(":", 1)
    server = ThreadingHTTPServer((host, int(port_s)), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
