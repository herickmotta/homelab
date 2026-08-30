#!/usr/bin/env python3
"""Assert Grafana provisions Prometheus manageAlerts and Alertmanager."""

from __future__ import annotations

from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = "ansible/roles/observability/templates/grafana-datasources.yml.j2"


def render(**values) -> dict:
    env = Environment(
        loader=FileSystemLoader(str(ROOT)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    text = env.get_template(TEMPLATE).render(**values)
    return yaml.safe_load(text)


def by_uid(document: dict) -> dict:
    return {item["uid"]: item for item in document["datasources"]}


def main() -> None:
    without_am = by_uid(
        render(
            observability_prometheus_listen_address="192.0.2.15:9090",
            observability_loki_ready_address="127.0.0.1:3100",
            observability_alertmanager_address="",
        )
    )
    prometheus = without_am["prometheus"]
    if prometheus["jsonData"]["manageAlerts"] is not True:
        raise SystemExit("Prometheus datasource must expose rules in Grafana Alerting")
    if prometheus["jsonData"]["prometheusType"] != "Prometheus":
        raise SystemExit("Prometheus datasource type must stay Prometheus, not Mimir")
    if "alertmanager" in without_am:
        raise SystemExit("Alertmanager datasource must stay absent without an address")

    with_am = by_uid(
        render(
            observability_prometheus_listen_address="192.0.2.15:9090",
            observability_loki_ready_address="127.0.0.1:3100",
            observability_alertmanager_address="192.0.2.11:9093",
        )
    )
    alertmanager = with_am["alertmanager"]
    if alertmanager["type"] != "alertmanager":
        raise SystemExit("Alertmanager datasource type drifted")
    if alertmanager["url"] != "http://192.0.2.11:9093":
        raise SystemExit("Alertmanager datasource must proxy Sentinel AM")
    if alertmanager["jsonData"]["implementation"] != "prometheus":
        raise SystemExit("Alertmanager implementation must be prometheus")
    if alertmanager["jsonData"]["handleGrafanaManagedAlerts"] is not False:
        raise SystemExit("Grafana must not send Grafana-managed alerts to Sentinel AM")
    print("grafana datasources: manageAlerts and Alertmanager read surface ok")


if __name__ == "__main__":
    main()
