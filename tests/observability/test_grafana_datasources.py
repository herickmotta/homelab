#!/usr/bin/env python3
"""Assert Grafana provisions Prometheus manageAlerts and Sentinel AM read-only."""

from __future__ import annotations

from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = "ansible/roles/observability/templates/grafana-datasources.yml.j2"
PROM = "ansible/roles/observability/templates/prometheus.yml.j2"


def render(template: str, **values) -> dict | str:
    env = Environment(
        loader=FileSystemLoader(str(ROOT)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    env.filters["regex_escape"] = __import__("re").escape
    env.filters["bool"] = lambda value: value in (True, "true", "True", 1, "1")
    text = env.get_template(template).render(**values)
    if template.endswith("prometheus.yml.j2"):
        return text
    return yaml.safe_load(text)


def by_uid(document: dict) -> dict:
    return {item["uid"]: item for item in document["datasources"]}


def main() -> None:
    without_am = by_uid(
        render(
            TEMPLATE,
            observability_prometheus_listen_address="192.0.2.15:9090",
            observability_loki_ready_address="127.0.0.1:3100",
            observability_external_alertmanager_address="",
        )
    )
    prometheus = without_am["prometheus"]
    if prometheus["jsonData"]["manageAlerts"] is not True:
        raise SystemExit("Prometheus datasource must expose rules in Grafana Alerting")
    if "alertmanager" in without_am:
        raise SystemExit("Alertmanager datasource must stay absent without an address")

    with_am = by_uid(
        render(
            TEMPLATE,
            observability_prometheus_listen_address="192.0.2.15:9090",
            observability_loki_ready_address="127.0.0.1:3100",
            observability_external_alertmanager_address="192.0.2.11:9093",
        )
    )
    alertmanager = with_am["alertmanager"]
    if alertmanager["url"] != "http://192.0.2.11:9093":
        raise SystemExit("Alertmanager datasource must proxy Sentinel AM")
    if alertmanager["jsonData"]["handleGrafanaManagedAlerts"] is not False:
        raise SystemExit("Grafana must not send Grafana-managed alerts to Sentinel AM")

    prom = render(
        PROM,
        observability_scrape_interval="30s",
        observability_evaluation_interval="30s",
        observability_site_label="example",
        observability_prometheus_listen_address="192.0.2.16:9090",
        observability_grafana_scrape_address="127.0.0.1:3000",
        observability_loki_ready_address="127.0.0.1:3100",
        observability_node_exporter_listen_address="127.0.0.1:9100",
        observability_grafana_alertmanager_host="127.0.0.1:3000",
        observability_grafana_alertmanager_path_prefix="/api/alertmanager/grafana",
        observability_node_targets=[],
        observability_smartctl_address="",
        observability_zfs_address="",
        observability_alloy_targets=[],
        observability_pve_enabled=False,
        observability_metrics_targets=[],
        observability_http_targets=[],
        observability_tcp_targets=[],
        observability_icmp_targets=[],
        observability_blackbox_listen_address="127.0.0.1:9115",
        observability_pve_exporter_listen_address="127.0.0.1:9221",
        observability_pve_target="",
        observability_accepted_degraded_serials=[],
    )
    if "192.0.2.11:9093" in prom:
        raise SystemExit("Observe Prometheus must not send alerts to Sentinel AM")
    if "/api/alertmanager/grafana" not in prom or "127.0.0.1:3000" not in prom:
        raise SystemExit("Observe Prometheus must send alerts to Grafana AM")
    print("grafana datasources: Sentinel AM read-only; Prom alerts to Grafana AM")


if __name__ == "__main__":
    main()
