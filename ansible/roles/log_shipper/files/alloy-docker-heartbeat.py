#!/usr/bin/env python3
"""Push one Loki line per Compose service so Drilldown can find quiet apps."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request

SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def drop_projects() -> set[str]:
    raw = os.environ.get("LOG_SHIPPER_DOCKER_DROP_PROJECTS", "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def compose_services() -> list[tuple[str, str, str]]:
    output = subprocess.check_output(
        [
            "docker",
            "ps",
            "--format",
            '{{.Label "com.docker.compose.service"}}\t'
            '{{.Label "com.docker.compose.project"}}\t'
            "{{.Names}}",
        ],
        text=True,
    )
    seen: set[str] = set()
    services: list[tuple[str, str, str]] = []
    skip = drop_projects()
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        service, project, name = (part.strip() for part in parts)
        if not service or service in seen:
            continue
        if not SAFE_NAME.match(service) or not SAFE_NAME.match(project):
            continue
        if project in skip:
            continue
        seen.add(service)
        services.append((service, project, name))
    return services


def push(streams: list[dict]) -> None:
    url = os.environ["LOG_SHIPPER_LOKI_URL"]
    payload = json.dumps({"streams": streams}).encode()
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"loki heartbeat push failed: HTTP {exc.code}") from exc


def main() -> None:
    host = os.environ["LOG_SHIPPER_HOST_LABEL"]
    site = os.environ["LOG_SHIPPER_SITE_LABEL"]
    now = str(time.time_ns())
    streams = []
    for service, project, name in compose_services():
        streams.append(
            {
                "stream": {
                    "job": "docker",
                    "host": host,
                    "site": site,
                    "service_name": service,
                    "compose_service": service,
                    "compose_project": project,
                    "container": name,
                },
                "values": [[now, "heartbeat compose service ok"]],
            }
        )
    if streams:
        push(streams)


if __name__ == "__main__":
    main()
