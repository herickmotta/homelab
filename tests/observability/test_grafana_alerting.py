#!/usr/bin/env python3
"""Assert Grafana contact points and Observe household blackbox render."""

from __future__ import annotations

from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]


def render(template: str, **values) -> str:
    env = Environment(
        loader=FileSystemLoader(str(ROOT)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    env.filters["to_json"] = lambda value: __import__("json").dumps(value)
    env.filters["bool"] = lambda value: value in (True, "true", "True", 1, "1")
    env.filters["string"] = lambda value: "" if value is None else str(value)
    return env.get_template(template).render(**values)


def main() -> None:
    alerting = yaml.safe_load(
        render(
            "ansible/roles/observability/templates/grafana-alerting.yml.j2",
            observability_mail_enabled=True,
            observability_telegram_enabled=True,
            observability_webhook_enabled=True,
            observability_email_destination="ops@example.test",
            observability_telegram_bot_token="tg-bot-not-for-logs",
            observability_telegram_chat_id="-1001234567890",
            observability_webhook_url="http://192.0.2.17:8787/grafana",
            observability_webhook_hmac_secret="grafana-hmac-secret-16",
        )
    )
    point = alerting["contactPoints"][0]
    types = {item["type"] for item in point["receivers"]}
    if types != {"email", "telegram", "webhook"}:
        raise SystemExit(f"contact point receivers drifted: {types}")
    webhook = next(item for item in point["receivers"] if item["type"] == "webhook")
    if webhook["settings"]["url"] != "http://192.0.2.17:8787/grafana":
        raise SystemExit("webhook URL drifted")
    if "hmacConfig" not in webhook["settings"]:
        raise SystemExit("Grafana webhook must HMAC")
    if alerting["policies"][0]["receiver"] != "grafana-notify":
        raise SystemExit("default policy must use grafana-notify")

    prom = render(
        "ansible/roles/observability/templates/prometheus.yml.j2",
        observability_scrape_interval="30s",
        observability_evaluation_interval="30s",
        observability_site_label="example",
        observability_prometheus_listen_address="192.0.2.16:9090",
        observability_grafana_scrape_address="127.0.0.1:3000",
        observability_loki_ready_address="127.0.0.1:3100",
        observability_node_exporter_listen_address="127.0.0.1:9100",
        observability_grafana_alertmanager_host="",
        observability_grafana_alertmanager_path_prefix="/api/alertmanager/grafana",
        observability_node_targets=[],
        observability_smartctl_address="",
        observability_zfs_address="",
        observability_alloy_targets=[],
        observability_pve_enabled=False,
        observability_metrics_targets=[],
        observability_http_targets=[
            {
                "name": "adguard",
                "address": "https://adguard.lab.example.test",
                "kind": "service",
                "dependency": "pve",
            }
        ],
        observability_tcp_targets=[
            {
                "name": "dns",
                "address": "192.0.2.12:53",
                "kind": "service",
                "dependency": "pve",
            },
            {
                "name": "smb",
                "address": "192.0.2.14:445",
                "kind": "service",
                "dependency": "pve",
            },
        ],
        observability_icmp_targets=[],
        observability_blackbox_listen_address="127.0.0.1:9115",
        observability_pve_exporter_listen_address="127.0.0.1:9221",
        observability_pve_target="",
        observability_accepted_degraded_serials=[],
    )
    if "job_name: blackbox_http" not in prom or "adguard.lab.example.test" not in prom:
        raise SystemExit("Observe Prometheus must scrape household HTTPS probes")
    if "192.0.2.12:53" not in prom or "192.0.2.14:445" not in prom:
        raise SystemExit("Observe Prometheus must scrape DNS and SMB TCP probes")

    rules = render(
        "ansible/roles/observability/templates/rules.yml.j2",
        observability_alert_for="2m",
        observability_expected_log_hosts=[],
        observability_alloy_targets=[],
        observability_http_targets=[{"name": "adguard", "address": "https://adguard.lab.example.test"}],
        observability_tcp_targets=[{"name": "dns", "address": "192.0.2.12:53"}],
        observability_icmp_targets=[],
    )
    if "- alert: HouseholdEndpointUnavailable" not in rules:
        raise SystemExit("household blackbox alerts must render")
    print("grafana contact points and observe blackbox ok")


if __name__ == "__main__":
    main()
