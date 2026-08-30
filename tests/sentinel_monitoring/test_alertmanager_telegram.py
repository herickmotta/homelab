#!/usr/bin/env python3
"""Render Alertmanager config and assert Telegram paging stays optional."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]
ROLE = ROOT / "ansible/roles/sentinel_monitoring"
TEMPLATES = ROLE / "templates"
DEFAULTS = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
TASKS = (ROLE / "tasks/main.yml").read_text()
EXAMPLE_SITE = yaml.safe_load(
    (ROOT / "examples/site.example.yaml").read_text()
)["site"]

FAKE_BOT = "123456789:FAKESECRET_s2t3u4v5w6x7y8z9a0b1"
CHANNEL = "-1001234567890"


def ansible_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).lower() in ("1", "true", "yes", "on")


def render(name: str, **overrides) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        autoescape=False,
    )
    env.filters["bool"] = ansible_bool
    env.filters["to_json"] = lambda value: json.dumps(value)
    env.filters["int"] = int
    context = dict(DEFAULTS)
    context.update(overrides)
    return env.get_template(name).render(context)


def load_yaml(name: str, **overrides) -> dict:
    return yaml.safe_load(render(name, **overrides))


def assert_defaults_off() -> None:
    if DEFAULTS["sentinel_monitoring_telegram_chat_id"]:
        raise SystemExit("Telegram chat id must default empty")
    if DEFAULTS["sentinel_monitoring_telegram_bot_token"]:
        raise SystemExit("Telegram bot token must default empty")
    if DEFAULTS["sentinel_monitoring_telegram_enabled"]:
        raise SystemExit("Telegram paging must default off")
    if DEFAULTS["sentinel_monitoring_default_receiver"] != "discard":
        raise SystemExit("default receiver must be discard until mail or Telegram is set")


def assert_example_has_fictional_channel() -> None:
    chat_id = EXAMPLE_SITE["monitoring"]["sentinel"]["telegram"]["chat_id"]
    if chat_id != CHANNEL:
        raise SystemExit("example site must use a fictional channel id")


def assert_tasks_reject_partial_and_hermes_token_reuse() -> None:
    if "Reject partial Telegram paging configuration" not in TASKS:
        raise SystemExit("role must reject partial Telegram paging")
    if "Hermes bot token" not in TASKS:
        raise SystemExit("role must warn against reusing the Hermes bot token")
    if "ALERTMANAGER_TELEGRAM_BOT_TOKEN" not in (
        ROOT / "examples/ansible/sentinel.yml"
    ).read_text():
        raise SystemExit("example playbook must read ALERTMANAGER_TELEGRAM_BOT_TOKEN")


def assert_email_only() -> None:
    cfg = load_yaml(
        "alertmanager.yml.j2",
        sentinel_monitoring_mail_enabled=True,
        sentinel_monitoring_email_destination="ops@example.test",
        sentinel_monitoring_default_receiver="notify",
    )
    if cfg["route"]["receiver"] != "notify":
        raise SystemExit("mail-only receiver name must be notify")
    notify = next(r for r in cfg["receivers"] if r["name"] == "notify")
    if "email_configs" not in notify:
        raise SystemExit("mail-only notify receiver needs email_configs")
    if "telegram_configs" in notify:
        raise SystemExit("mail-only notify receiver must omit telegram_configs")


def assert_telegram_and_email() -> None:
    cfg = load_yaml(
        "alertmanager.yml.j2",
        sentinel_monitoring_mail_enabled=True,
        sentinel_monitoring_telegram_enabled=True,
        sentinel_monitoring_email_destination="ops@example.test",
        sentinel_monitoring_telegram_chat_id=CHANNEL,
        sentinel_monitoring_telegram_bot_token=FAKE_BOT,
        sentinel_monitoring_default_receiver="notify",
    )
    if cfg["route"]["receiver"] != "notify":
        raise SystemExit("combined paging must use notify")
    notify = next(r for r in cfg["receivers"] if r["name"] == "notify")
    telegram = notify["telegram_configs"][0]
    if telegram["chat_id"] != int(CHANNEL):
        raise SystemExit("telegram chat_id must render as int")
    if telegram["bot_token"] != FAKE_BOT:
        raise SystemExit("telegram bot_token missing from rendered config")
    if telegram.get("send_resolved") is not True:
        raise SystemExit("telegram must send resolved")
    if "email_configs" not in notify:
        raise SystemExit("combined paging must keep email")


def assert_discard_without_paging() -> None:
    cfg = load_yaml("alertmanager.yml.j2")
    if cfg["route"]["receiver"] != "discard":
        raise SystemExit("no paging configured must discard")
    names = {r["name"] for r in cfg["receivers"]}
    if names != {"discard"}:
        raise SystemExit("no paging configured must not invent notify")


def main() -> None:
    assert_defaults_off()
    assert_example_has_fictional_channel()
    assert_tasks_reject_partial_and_hermes_token_reuse()
    assert_email_only()
    assert_telegram_and_email()
    assert_discard_without_paging()
    print("sentinel_monitoring alertmanager telegram contract ok")


if __name__ == "__main__":
    main()
