#!/usr/bin/env python3
"""Render and regression-test per-host Alloy log freshness."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "alloy-v1.19.2-loki-write.metrics"
PROM_VERSION = "3.14.0"
PROMTOOL_URL = (
    "https://github.com/prometheus/prometheus/releases/download/"
    f"v{PROM_VERSION}/prometheus-{PROM_VERSION}.linux-amd64.tar.gz"
)
EXPECTED_HOST_COUNT = 6


def unique(values):
    seen = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


def as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return value in (1, "1", "true", "True", "yes", "Yes")


def scrape_host(target: dict) -> str:
    return target["host"] if target.get("host") else target["name"]


def render(template_rel: str, **values) -> str:
    env = Environment(
        loader=FileSystemLoader(str(ROOT)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    env.filters["regex_escape"] = re.escape
    env.filters["unique"] = unique
    env.filters["bool"] = as_bool
    return env.get_template(template_rel).render(**values)


def load_example_observability() -> tuple[list[str], list[dict]]:
    site = yaml.safe_load((ROOT / "examples" / "site.example.yaml").read_text())
    obs = site["site"]["monitoring"]["observability"]
    return obs["expected_log_hosts"], obs["alloy_targets"]


def assert_fixture() -> None:
    text = FIXTURE.read_text()
    if "loki_write_sent_entries_total" not in text:
        raise SystemExit("fixture is missing loki_write_sent_entries_total")
    match = re.search(
        r'^loki_write_sent_entries_total\{([^}]+)\}',
        text,
        re.MULTILINE,
    )
    if match is None:
        raise SystemExit("fixture is missing a loki_write_sent_entries_total sample")
    labels = dict(
        re.findall(r'([A-Za-z_][A-Za-z0-9_]*)="([^"]*)"', match.group(1))
    )
    if ":" not in labels.get("host", ""):
        raise SystemExit(
            "Alloy v1.19.2 native host label must be the Loki endpoint, not the shipper"
        )
    if labels.get("component_id") != "loki.write.observe":
        raise SystemExit("fixture component_id must be loki.write.observe")
    print("fixture: loki_write_sent_entries_total host is the Loki endpoint")


def assert_rendered_rules(rules: str, hosts: list[str], targets: list[dict]) -> None:
    stale = re.findall(r"(?m)^\s+- alert: AlloyLogPipelineStale$", rules)
    if len(stale) != EXPECTED_HOST_COUNT:
        raise SystemExit(
            f"expected {EXPECTED_HOST_COUNT} AlloyLogPipelineStale rules, found {len(stale)}"
        )
    if "LokiIngestionStale" in rules:
        raise SystemExit("per-host mode must not render LokiIngestionStale")
    if "vector(0)" not in rules:
        raise SystemExit("missing-series must become zero via vector(0)")
    for host in hosts:
        target = next(item for item in targets if scrape_host(item) == host)
        dependency = target.get("dependency", "none")
        if f'host="{host}"' not in rules:
            raise SystemExit(f"missing PromQL host matcher for {host}")
        if f'host: "{host}"' not in rules:
            raise SystemExit(f"missing alert host label for {host}")
        if f'dependency: "{dependency}"' not in rules:
            raise SystemExit(f"missing dependency {dependency} for {host}")
        if f'up{{job="alloy",host="{host}"}} == 1' not in rules:
            raise SystemExit(f"missing Alloy-up gate for {host}")
    print(f"rendered rules: {EXPECTED_HOST_COUNT} hosts with scrape-host dependencies")


def assert_fallback(rules: str) -> None:
    if "LokiIngestionStale" not in rules:
        raise SystemExit("empty expected hosts must keep LokiIngestionStale")
    if "AlloyLogPipelineStale" in rules:
        raise SystemExit("empty expected hosts must not render AlloyLogPipelineStale")
    print("fallback: LokiIngestionStale retained when no expected hosts")


def assert_heartbeat_config() -> None:
    docker_only = render(
        "ansible/roles/log_shipper/templates/config.alloy.j2",
        log_shipper_loki_url="http://192.0.2.16:3100/loki/api/v1/push",
        log_shipper_site_label="example",
        log_shipper_host_label="apps-example",
        log_shipper_journal_units=[],
        log_shipper_heartbeat_unit="alloy-heartbeat.service",
        log_shipper_docker=True,
    )
    if "alloy-heartbeat.service" not in docker_only:
        raise SystemExit("docker-only shipper must still keep the journal heartbeat")
    if "loki.source.journal" not in docker_only:
        raise SystemExit("heartbeat requires loki.source.journal on every host")
    prometheus = (
        ROOT / "ansible/roles/observability/templates/prometheus.yml.j2"
    ).read_text()
    if "honor_labels: false" not in prometheus:
        raise SystemExit("Alloy scrape must set honor_labels: false")
    print("heartbeat and scrape-label collision guards are present")


def write_promtool_test(directory: Path, hosts: list[str], targets: list[dict]) -> Path:
    deps = {scrape_host(target): target.get("dependency", "none") for target in targets}
    stale_host = "apps-example"
    sentinel_host = "sentinel-example"
    down_host = "nas-example"
    if stale_host not in hosts or sentinel_host not in hosts or down_host not in hosts:
        raise SystemExit("example expected_log_hosts no longer include the test hosts")

    def write_series(name: str, selector: str, values: str) -> str:
        return (
            f"      - series: '{name}{{{selector}}}'\n"
            f"        values: '{values}'\n"
        )

    def host_write_labels(host: str) -> str:
        return (
            f'job="alloy",host="{host}",exported_host="192.0.2.16:3100",'
            f'tenant="",component_id="loki.write.observe"'
        )

    def traffic(up_hosts: dict[str, str], write_hosts: dict[str, str]) -> str:
        chunks = []
        for host, values in write_hosts.items():
            chunks.append(
                write_series(
                    "loki_write_sent_entries_total",
                    host_write_labels(host),
                    values,
                )
            )
        for host, values in up_hosts.items():
            chunks.append(write_series("up", f'job="alloy",host="{host}"', values))
        return "".join(chunks)

    increasing = {host: "0+10x30" for host in hosts}
    all_up = {host: "1x30" for host in hosts}
    missing_apps_writes = {host: "0+10x30" for host in hosts if host != stale_host}
    missing_sentinel_writes = {
        host: "0+10x30" for host in hosts if host != sentinel_host
    }
    flat_apps_writes = {
        host: ("0x30" if host == stale_host else "0+10x30") for host in hosts
    }
    alloy_down_writes = {
        host: ("0x30" if host == down_host else "0+10x30") for host in hosts
    }
    alloy_down_up = {host: ("0x30" if host == down_host else "1x30") for host in hosts}

    all_healthy = traffic(all_up, increasing)
    missing_apps = traffic(all_up, missing_apps_writes)
    missing_sentinel = traffic(all_up, missing_sentinel_writes)
    flat_apps = traffic(all_up, flat_apps_writes)
    alloy_down = traffic(alloy_down_up, alloy_down_writes)

    def stale_alert(host: str) -> str:
        dependency = deps[host]
        return f"""          - exp_labels:
              alertname: AlloyLogPipelineStale
              severity: critical
              dependency: "{dependency}"
              host: {host}
            exp_annotations:
              summary: Alloy on {host} has not sent logs to Loki
              description: loki.write sent no entries for 15 minutes while Alloy is still scrapeable. A broken journal or Docker pipeline is more likely than a quiet host; every shipper emits a bounded heartbeat.
"""

    test_yaml = f"""rule_files:
  - observability.yml

evaluation_interval: 1m

tests:
  - interval: 1m
    input_series:
{all_healthy}
    alert_rule_test:
      - eval_time: 20m
        alertname: AlloyLogPipelineStale
        exp_alerts: []
      - eval_time: 20m
        alertname: LokiIngestionStale
        exp_alerts: []

  - interval: 1m
    input_series:
{missing_apps}
    alert_rule_test:
      - eval_time: 20m
        alertname: AlloyLogPipelineStale
        exp_alerts:
{stale_alert(stale_host)}
  - interval: 1m
    input_series:
{missing_sentinel}
    alert_rule_test:
      - eval_time: 20m
        alertname: AlloyLogPipelineStale
        exp_alerts:
{stale_alert(sentinel_host)}
  - interval: 1m
    input_series:
{flat_apps}
    alert_rule_test:
      - eval_time: 20m
        alertname: AlloyLogPipelineStale
        exp_alerts:
{stale_alert(stale_host)}
  - interval: 1m
    input_series:
{alloy_down}
    alert_rule_test:
      - eval_time: 20m
        alertname: AlloyLogPipelineStale
        exp_alerts: []
      - eval_time: 20m
        alertname: AlloyDown
        exp_alerts:
          - exp_labels:
              alertname: AlloyDown
              severity: critical
              job: alloy
              host: {down_host}
            exp_annotations:
              summary: Alloy on {down_host} is down
              description: Observe cannot scrape the Grafana Alloy HTTP endpoint.
"""
    path = directory / "rules.test.yml"
    path.write_text(test_yaml)
    return path


def ensure_promtool() -> str:
    explicit = os.environ.get("PROMTOOL")
    if explicit:
        return explicit
    on_path = shutil.which("promtool")
    if on_path:
        return on_path

    cache = Path.home() / ".cache" / "homelab-promtool" / PROM_VERSION
    binary = cache / "promtool"
    if binary.exists() and os.access(binary, os.X_OK):
        return str(binary)

    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / "prometheus.tar.gz"
    print(f"downloading pinned promtool {PROM_VERSION}")
    urllib.request.urlretrieve(PROMTOOL_URL, archive)
    with tarfile.open(archive, "r:gz") as tar:
        member = next(
            item for item in tar.getmembers() if item.name.endswith("/promtool")
        )
        member.name = "promtool"
        tar.extract(member, path=cache, filter="data")
    binary.chmod(0o755)
    archive.unlink(missing_ok=True)
    return str(binary)


def run_promtool(test_file: Path) -> None:
    command = [
        ensure_promtool(),
        "test",
        "rules",
        str(test_file),
    ]
    print("running", " ".join(command))
    subprocess.run(command, check=True, cwd=test_file.parent)
    print("promtool: per-host freshness cases passed")


def main() -> int:
    os.chdir(ROOT)
    hosts, targets = load_example_observability()
    if len(hosts) != EXPECTED_HOST_COUNT:
        raise SystemExit(
            f"example expected_log_hosts must contain {EXPECTED_HOST_COUNT} hosts"
        )
    if {scrape_host(target) for target in targets} < set(hosts):
        raise SystemExit("every expected log host must be an Alloy scrape host")

    assert_fixture()
    assert_heartbeat_config()

    per_host = render(
        "ansible/roles/observability/templates/rules.yml.j2",
        observability_alert_for="2m",
        observability_expected_log_hosts=hosts,
        observability_alloy_targets=targets,
    )
    assert_rendered_rules(per_host, hosts, targets)

    fallback = render(
        "ansible/roles/observability/templates/rules.yml.j2",
        observability_alert_for="2m",
        observability_expected_log_hosts=[],
        observability_alloy_targets=targets,
    )
    assert_fallback(fallback)

    with tempfile.TemporaryDirectory(prefix="log-freshness-") as tmp:
        directory = Path(tmp)
        (directory / "observability.yml").write_text(per_host)
        write_promtool_test(directory, hosts, targets)
        run_promtool(directory / "rules.test.yml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
