#!/usr/bin/env python3
"""Assert Loki and Alloy expose Compose/journal names to Grafana Logs Drilldown."""

from pathlib import Path
import re

from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]


def render(template: str, **values) -> str:
    env = Environment(
        loader=FileSystemLoader(str(ROOT)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    env.filters["regex_escape"] = re.escape
    env.filters["unique"] = lambda values: list(dict.fromkeys(values))
    env.filters["bool"] = lambda value: value in (True, "true", "True", 1, "1")
    return env.get_template(template).render(**values)


def test_loki_indexes_compose_and_journal_services() -> None:
    text = render(
        "ansible/roles/observability/templates/loki.yml.j2",
        observability_loki_http_listen_address="0.0.0.0",
        observability_loki_http_listen_port=3100,
        observability_loki_grpc_listen_address="127.0.0.1",
        observability_loki_grpc_listen_port=9096,
        observability_loki_retention_period="336h",
    )
    assert "volume_enabled: true" in text
    assert "pattern_ingester:" in text
    assert "discover_service_name:" in text
    assert "- compose_service" in text
    assert "- unit" in text
    names = text.split("discover_service_name:", 1)[1]
    names = names.split("pattern_ingester:", 1)[0]
    assert "- job" not in names
    assert "- container" not in names


def test_alloy_sets_service_name() -> None:
    journal = render(
        "ansible/roles/log_shipper/templates/config.alloy.j2",
        log_shipper_loki_url="http://192.0.2.15:3100/loki/api/v1/push",
        log_shipper_host_label="nas",
        log_shipper_site_label="example",
        log_shipper_docker=False,
        log_shipper_journal_units=["smbd.service"],
        log_shipper_heartbeat_unit="alloy-heartbeat.service",
    )
    assert 'target_label  = "service_name"' in journal
    docker = render(
        "ansible/roles/log_shipper/templates/config.alloy.j2",
        log_shipper_loki_url="http://192.0.2.15:3100/loki/api/v1/push",
        log_shipper_host_label="apps",
        log_shipper_site_label="example",
        log_shipper_docker=True,
        log_shipper_journal_units=[],
        log_shipper_heartbeat_unit="alloy-heartbeat.service",
    )
    assert "com_docker_compose_service" in docker
    assert docker.count('target_label  = "service_name"') >= 2


if __name__ == "__main__":
    test_loki_indexes_compose_and_journal_services()
    test_alloy_sets_service_name()
    print("loki and alloy expose service_name for logs drilldown")
