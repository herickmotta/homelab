#!/usr/bin/env python3
"""Emit Prometheus textfile metrics for local Docker inventory.

Does not print Env, bind-mount sources, or credentials. Used by host_metrics
probes and the observability guest textfile collector.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def prom_label(value: object, limit: int = 160) -> str:
    text = str(value or "").replace("\\", "\\\\").replace("\n", " ").replace('"', '\\"')
    return text[:limit]


def docker_lines(args: list[str]) -> list[str]:
    fixture = os.environ.get("DOCKER_INVENTORY_FIXTURE_DIR")
    if fixture:
        path = Path(fixture) / ("-".join(args).replace("/", "_") + ".txt")
        if path.exists():
            return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return []
    try:
        raw = subprocess.check_output(["docker", *args], stderr=subprocess.DEVNULL)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []
    return [line for line in raw.decode().splitlines() if line.strip()]


def docker_json(args: list[str]) -> Any:
    fixture = os.environ.get("DOCKER_INVENTORY_FIXTURE_DIR")
    if fixture:
        path = Path(fixture) / ("-".join(args).replace("/", "_") + ".json")
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return []
    try:
        raw = subprocess.check_output(["docker", *args], stderr=subprocess.DEVNULL)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []
    raw = raw.strip()
    if not raw:
        return []
    return json.loads(raw)


def compose_label(labels: dict[str, str], key: str) -> str:
    return labels.get(key) or labels.get(key.replace(".", "_")) or ""


def health_status(state: dict[str, Any], running: bool) -> str:
    health = state.get("Health")
    if isinstance(health, dict) and health.get("Status"):
        return str(health["Status"])
    return "none" if running else "stopped"


def emit(name: str, labels: dict[str, str], value: float) -> None:
    encoded = ",".join(f'{key}="{prom_label(val)}"' for key, val in labels.items() if val)
    print(f"{name}{{{encoded}}} {value}")


def main() -> int:
    containers_path = os.environ.get("DOCKER_INVENTORY_CONTAINERS")
    networks_path = os.environ.get("DOCKER_INVENTORY_NETWORKS")
    if containers_path:
        inspects = json.loads(Path(containers_path).read_text(encoding="utf-8"))
        networks = (
            json.loads(Path(networks_path).read_text(encoding="utf-8"))
            if networks_path
            else []
        )
    else:
        container_ids = docker_lines(["ps", "-aq"])
        inspects = docker_json(["inspect", *container_ids]) if container_ids else []
        network_ids = docker_lines(["network", "ls", "-q"])
        networks = (
            docker_json(["network", "inspect", *network_ids]) if network_ids else []
        )
    if not isinstance(inspects, list):
        inspects = []
    if not isinstance(networks, list):
        networks = []

    print("# HELP homelab_docker_container_running 1 if the container process is running.")
    print("# TYPE homelab_docker_container_running gauge")
    print("# HELP homelab_docker_container_health 1 if healthy, or running with no healthcheck.")
    print("# TYPE homelab_docker_container_health gauge")
    print("# HELP homelab_docker_container_restarts Docker RestartCount.")
    print("# TYPE homelab_docker_container_restarts gauge")
    print("# HELP homelab_docker_container_info Container identity labels; value is always 1.")
    print("# TYPE homelab_docker_container_info gauge")
    print("# HELP homelab_docker_container_network Container IPv4 on a Docker network.")
    print("# TYPE homelab_docker_container_network gauge")
    print("# HELP homelab_docker_published_port Host-published container port.")
    print("# TYPE homelab_docker_published_port gauge")
    print("# HELP homelab_docker_network_info Docker network gateway; value is always 1.")
    print("# TYPE homelab_docker_network_info gauge")

    for item in inspects:
        if not isinstance(item, dict):
            continue
        name = str(item.get("Name") or "").lstrip("/")
        if not name:
            continue
        state = item.get("State") if isinstance(item.get("State"), dict) else {}
        config = item.get("Config") if isinstance(item.get("Config"), dict) else {}
        host_config = item.get("HostConfig") if isinstance(item.get("HostConfig"), dict) else {}
        labels = config.get("Labels") if isinstance(config.get("Labels"), dict) else {}
        running = bool(state.get("Running"))
        status = health_status(state, running)
        healthy = 1 if (status == "healthy" or (status == "none" and running)) else 0
        image = str(config.get("Image") or "")
        project = compose_label(labels, "com.docker.compose.project")
        service = compose_label(labels, "com.docker.compose.service")
        role = str(labels.get("homelab.role") or "")
        identity = {
            "name": name,
            "compose_project": project,
            "compose_service": service,
            "role": role,
        }
        emit("homelab_docker_container_running", identity, 1 if running else 0)
        emit(
            "homelab_docker_container_health",
            {**identity, "health": status},
            healthy,
        )
        emit(
            "homelab_docker_container_restarts",
            identity,
            float(item.get("RestartCount") if item.get("RestartCount") is not None else state.get("RestartCount") or 0),
        )
        emit("homelab_docker_container_info", {**identity, "image": image}, 1)

        nets = item.get("NetworkSettings", {})
        net_map = nets.get("Networks") if isinstance(nets, dict) else {}
        if isinstance(net_map, dict):
            for net_name, net in net_map.items():
                if not isinstance(net, dict):
                    continue
                ip_addr = str(net.get("IPAddress") or "")
                if not ip_addr:
                    continue
                emit(
                    "homelab_docker_container_network",
                    {**identity, "network": net_name, "ip": ip_addr},
                    1,
                )

        bindings = host_config.get("PortBindings")
        if isinstance(bindings, dict):
            for dest, hosts in bindings.items():
                dest_port = str(dest).split("/", 1)[0]
                if not isinstance(hosts, list):
                    continue
                for bind in hosts:
                    if not isinstance(bind, dict):
                        continue
                    emit(
                        "homelab_docker_published_port",
                        {
                            **identity,
                            "host_ip": str(bind.get("HostIp") or "0.0.0.0"),
                            "host_port": str(bind.get("HostPort") or ""),
                            "dest_port": dest_port,
                        },
                        1,
                    )

    for net in networks:
        if not isinstance(net, dict):
            continue
        net_name = str(net.get("Name") or "")
        driver = str(net.get("Driver") or "")
        if not net_name or driver in ("host", "null"):
            continue
        ipam = net.get("IPAM") if isinstance(net.get("IPAM"), dict) else {}
        configs = ipam.get("Config") if isinstance(ipam.get("Config"), list) else []
        gateway = ""
        subnet = ""
        if configs and isinstance(configs[0], dict):
            gateway = str(configs[0].get("Gateway") or "")
            subnet = str(configs[0].get("Subnet") or "")
        emit(
            "homelab_docker_network_info",
            {"network": net_name, "driver": driver, "gateway": gateway, "subnet": subnet},
            1,
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except json.JSONDecodeError:
        sys.stderr.write("docker inventory: invalid JSON\n")
        raise SystemExit(0)
