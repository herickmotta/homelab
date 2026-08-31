#!/usr/bin/env python3
"""Assert Grafana operations dashboard queries Docker inventory metrics."""

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]


def test_operations_dashboard_queries_docker_inventory() -> None:
    path = ROOT / "ansible/roles/observability/files/dashboards/operations.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    exprs = []
    for panel in data["panels"]:
        for target in panel.get("targets") or []:
            exprs.append(target.get("expr") or "")
    joined = "\n".join(exprs)
    assert "homelab_docker_container_running" in joined
    assert "homelab_docker_container_network" in joined
    assert "homelab_docker_network_info" in joined
    titles = [panel.get("title") for panel in data["panels"]]
    assert "Local TCP probes" in titles


def test_observe_node_exporter_reads_textfile() -> None:
    compose = (
        ROOT / "ansible/roles/observability/templates/compose.yaml.j2"
    ).read_text(encoding="utf-8")
    assert "--collector.textfile.directory=/textfile" in compose
    assert "./textfile:/textfile:ro" in compose


if __name__ == "__main__":
    test_operations_dashboard_queries_docker_inventory()
    test_observe_node_exporter_reads_textfile()
    print("operations dashboard includes docker inventory")
