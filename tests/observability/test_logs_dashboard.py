#!/usr/bin/env python3
"""Assert Grafana ships a Service logs dashboard from Loki labels."""

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
DASHBOARD = ROOT / "ansible/roles/observability/files/dashboards/logs.json"
TASKS = ROOT / "ansible/roles/observability/tasks/main.yml"


def _exprs(data: dict) -> str:
    exprs: list[str] = []

    def walk(panels: list) -> None:
        for panel in panels:
            for target in panel.get("targets") or []:
                exprs.append(target.get("expr") or "")
            walk(panel.get("panels") or [])

    walk(data.get("panels") or [])
    return "\n".join(exprs)


def _repeats(data: dict) -> set[str]:
    names: set[str] = set()

    def walk(panels: list) -> None:
        for panel in panels:
            repeat = panel.get("repeat")
            if repeat:
                names.add(repeat)
            walk(panel.get("panels") or [])

    walk(data.get("panels") or [])
    return names


def test_logs_dashboard_lists_services_from_loki() -> None:
    data = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    assert data["uid"] == "homelab-logs"
    assert data["title"] == "Service logs"
    variables = {item["name"]: item for item in data["templating"]["list"]}
    assert variables["host"]["query"] == "label_values(host)"
    assert "compose_service" in variables["compose_service"]["query"]
    assert "unit" in variables["unit"]["query"]
    assert variables["filter"]["type"] == "textbox"
    assert _repeats(data) == {"compose_service", "unit"}
    joined = _exprs(data)
    assert '{job="docker", host=~"$host", compose_service="$compose_service"}' in joined
    assert '{job="journal", host=~"$host", unit="$unit"}' in joined
    assert TASKS.read_text(encoding="utf-8").count("dashboards/logs.json") == 1


if __name__ == "__main__":
    test_logs_dashboard_lists_services_from_loki()
    print("service logs dashboard lists compose and journal streams")
