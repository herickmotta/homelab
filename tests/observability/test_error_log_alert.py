from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined


ROOT = Path(__file__).resolve().parents[2]


def test_error_log_alert_is_loki_backed_and_bounded():
    env = Environment(
        loader=FileSystemLoader(str(ROOT)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    rendered = env.get_template(
        "ansible/roles/observability/templates/grafana-error-alerts.yml.j2"
    ).render(
        observability_error_log_alert_threshold=10,
        observability_error_log_alert_window="5m",
        observability_error_log_alert_for="2m",
        observability_site_label="example",
    )
    document = yaml.safe_load(rendered)
    rule = document["groups"][0]["rules"][0]
    assert rule["title"] == "Homelab error log rate"
    assert rule["notification_settings"]["receiver"] == "grafana-notify"
    loki_query = rule["data"][0]["model"]["expr"]
    assert 'job=~"journal|docker"' in loki_query
    assert "count_over_time" in loki_query
    assert "error|failed|failure|critical|fatal|panic" in loki_query
    assert rule["noDataState"] == "OK"
    assert rule["execErrState"] == "Alerting"