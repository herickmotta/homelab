#!/usr/bin/env python3
"""Assert rich-plane ops alerts render and pass promtool."""

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
PROM_VERSION = "3.14.0"
PROMTOOL_URL = (
    "https://github.com/prometheus/prometheus/releases/download/"
    f"v{PROM_VERSION}/prometheus-{PROM_VERSION}.linux-amd64.tar.gz"
)
REQUIRED_ALERTS = (
    "ZfsPoolUnhealthy",
    "ZfsPoolSpaceLow",
    "SmartDeviceFailed",
    "SmartPendingSectors",
    "SmartReallocatedSectors",
    "SmartReallocatedSectorsRising",
    "LinuxExporterDown",
    "GuestRootFilesystemLow",
    "GuestRootInodesLow",
    "ObservePrometheusRuleEvaluationFailures",
    "ObserveAlertNotificationsDropped",
)


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


def load_example() -> tuple[list[str], list[dict]]:
    site = yaml.safe_load((ROOT / "examples" / "site.example.yaml").read_text())
    obs = site["site"]["monitoring"]["observability"]
    return obs["expected_log_hosts"], obs["alloy_targets"]


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


def main() -> int:
    os.chdir(ROOT)
    hosts, targets = load_example()
    rules = render(
        "ansible/roles/observability/templates/rules.yml.j2",
        observability_alert_for="2m",
        observability_expected_log_hosts=hosts,
        observability_alloy_targets=targets,
    )
    for name in REQUIRED_ALERTS:
        if f"- alert: {name}" not in rules:
            raise SystemExit(f"missing observe alert {name}")
    if 'accepted_degraded="true"' not in rules:
        raise SystemExit("standing reallocations must honor accepted_degraded")
    sentinel = render(
        "ansible/roles/sentinel_monitoring/templates/rules.yml.j2",
        sentinel_monitoring_alert_for="2m",
        sentinel_monitoring_pve_enabled=True,
        sentinel_monitoring_critical_guest_ids=[112, 114, 115],
    )
    if "AlertmanagerNotificationsFailed" not in sentinel:
        raise SystemExit("missing Alertmanager delivery alert")
    if "TlsCertificateExpiring" not in sentinel:
        raise SystemExit("missing TLS expiry alert")

    test_yaml = """rule_files:
  - observability.yml

evaluation_interval: 1m

tests:
  - interval: 1m
    input_series:
      - series: 'zfs_pool_health{pool="iron",job="zfs"}'
        values: '0x10'
    alert_rule_test:
      - eval_time: 5m
        alertname: ZfsPoolUnhealthy
        exp_alerts: []
  - interval: 1m
    input_series:
      - series: 'zfs_pool_health{pool="iron",job="zfs"}'
        values: '2x10'
    alert_rule_test:
      - eval_time: 5m
        alertname: ZfsPoolUnhealthy
        exp_alerts:
          - exp_labels:
              alertname: ZfsPoolUnhealthy
              severity: critical
              dependency: pve
              pool: iron
              job: zfs
            exp_annotations:
              summary: ZFS pool iron is not online
              description: Observe reports a ZFS pool health state other than online.
"""
    with tempfile.TemporaryDirectory(prefix="ops-alerts-") as tmp:
        directory = Path(tmp)
        (directory / "observability.yml").write_text(rules)
        test_file = directory / "rules.test.yml"
        test_file.write_text(test_yaml)
        command = [ensure_promtool(), "test", "rules", str(test_file)]
        print("running", " ".join(command))
        subprocess.run(command, check=True, cwd=directory)
    print("promtool: ZFS pool health cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
