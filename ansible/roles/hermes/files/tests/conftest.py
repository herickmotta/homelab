from __future__ import annotations

import pytest

from hermes_triage.config import Config


def make_config(tmp_path, **overrides) -> Config:
    values = dict(
        listen_host="127.0.0.1",
        listen_port=8787,
        webhook_secret="supersecret-token",
        telegram_bot_token="bot-token",
        telegram_chat_id=4242,
        openai_api_key="sk-test",
        openai_model_default="gpt-5.6-luna",
        openai_model_complex="gpt-5.6-sol",
        sentinel_prometheus_url="http://127.0.0.1:9090",
        observe_prometheus_url="http://192.0.2.16:9090",
        observe_loki_url="http://192.0.2.16:3100",
        pve_url="https://192.0.2.10:8006",
        pve_token_id="hermes@pve!hermes",
        pve_token_secret="pve-secret",
        pve_node="pve-example",
        github_token="github-token",
        github_repository="example/homelab-live",
        allowed_hosts=("net-example", "nas-example", "apps-example"),
        allowed_services=("frigate", "mosquitto", "homeassistant"),
        allowed_vmids=(112, 114, 115),
        allowed_git_paths=("site.yaml", "ansible/site.yml"),
        log_sources=(
            {
                "name": "frigate",
                "host": "apps-example",
                "kind": "container",
                "selector": "frigate",
            },
            {
                "name": "smbd",
                "host": "nas-example",
                "kind": "unit",
                "selector": "smbd.service",
            },
        ),
        state_dir=str(tmp_path),
        conversation_ttl_seconds=86400,
        conversation_max_turns=12,
        max_evidence_chars=6000,
        max_log_lines=20,
        openai_timeout_seconds=60.0,
        evidence_timeout_seconds=10.0,
        diagnosis_cooldown_seconds=120,
    )
    values.update(overrides)
    return Config(**values)


@pytest.fixture
def config(tmp_path):
    return make_config(tmp_path)
