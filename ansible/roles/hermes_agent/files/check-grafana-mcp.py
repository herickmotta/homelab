#!/usr/bin/env python3
"""Accept Hermes → grafana-mcp. Do not print secrets or response bodies."""

from __future__ import annotations

import os
import socket
import sys
import urllib.error
import urllib.request

HEALTH = "http://grafana-mcp:8000/healthz"
MCP = "http://grafana-mcp:8000/mcp"
INIT = (
    b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":'
    b'{"protocolVersion":"2024-11-05","capabilities":{},'
    b'"clientInfo":{"name":"ansible","version":"0"}}}'
)


def _open(req: urllib.request.Request, timeout: int = 10):
    return urllib.request.urlopen(req, timeout=timeout)


def reach() -> int:
    socket.gethostbyname("grafana-mcp")
    with _open(urllib.request.Request(HEALTH)) as resp:
        if resp.status != 200:
            print("healthz status", resp.status, file=sys.stderr)
            return 1
    req = urllib.request.Request(MCP, data=b"{}", method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    try:
        _open(req)
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return 0
        print("mcp unauthenticated status", exc.code, file=sys.stderr)
        return 1
    print("mcp unauthenticated did not return 401", file=sys.stderr)
    return 1


def auth() -> int:
    token = os.environ.get("MCP_CALLER_TOKEN", "")
    if not token:
        print("missing caller token", file=sys.stderr)
        return 1
    req = urllib.request.Request(MCP, data=INIT, method="POST")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    try:
        with _open(req) as resp:
            if resp.status in (200, 202):
                return 0
            print("mcp authenticated status", resp.status, file=sys.stderr)
            return 1
    except urllib.error.HTTPError as exc:
        print("mcp authenticated status", exc.code, file=sys.stderr)
        return 1


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "reach"
    if mode == "reach":
        return reach()
    if mode == "auth":
        return auth()
    print("unknown mode", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
