#!/usr/bin/env python3
"""Render Hermes Agent templates and assert the isolation contract."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]
ROLE = ROOT / "ansible/roles/hermes_agent"
TEMPLATES = ROLE / "templates"
DEFAULTS = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
VALIDATE = (ROLE / "tasks/validate.yml").read_text()
ABSENT = (ROLE / "tasks/absent.yml").read_text()
PRESENT = (ROLE / "tasks/present.yml").read_text()
EXAMPLE_SITE = yaml.safe_load(
    (ROOT / "examples/site.example.yaml").read_text()
)["site"]

SECRET_TOKEN = "tg-bot-secret-not-for-compose"
SECRET_KEY = "provider-secret-not-for-compose"
TELEGRAM_USER = "123456789"
SOURCE_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
RFC1918_DNS_RE = re.compile(
    r"^(10\.|127\.|169\.254\.|172\.(1[6-9]|2[0-9]|3[0-1])\.|192\.168\.)"
)


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
    env.filters["string"] = lambda value: "" if value is None else str(value)
    env.filters["int"] = int
    context = dict(DEFAULTS)
    context["hermes_agent_provider_env_name"] = context[
        "hermes_agent_provider_env_names"
    ][context["hermes_agent_provider"]]
    context.update(overrides)
    return env.get_template(name).render(context)


def load_yaml(name: str, **overrides) -> dict:
    return yaml.safe_load(render(name, **overrides))


def assert_defaults() -> None:
    if DEFAULTS["hermes_agent_enabled"] or DEFAULTS["hermes_agent_full_capability"]:
        raise SystemExit("role defaults must stay disabled and conservative")
    if DEFAULTS["hermes_agent_runtime_user"] in ("root", ""):
        raise SystemExit("runtime user must be a non-root identity")
    if int(DEFAULTS["hermes_agent_runtime_uid"]) <= 0:
        raise SystemExit("runtime uid must be non-root")
    if not SOURCE_COMMIT_RE.match(DEFAULTS["hermes_agent_source_commit"]):
        raise SystemExit("source commit must be a 40-character SHA")
    if not DIGEST_RE.match(DEFAULTS["hermes_agent_image_digest"]):
        raise SystemExit("image digest must be an immutable sha256 pin")
    if ":" in DEFAULTS["hermes_agent_image_repository"]:
        raise SystemExit("image repository must not include a tag")
    if not DEFAULTS["hermes_agent_preserve_state_on_disable"]:
        raise SystemExit("disable path must preserve state by default")
    for server in DEFAULTS["hermes_agent_dns_servers"]:
        if RFC1918_DNS_RE.match(server):
            raise SystemExit(f"DNS resolver {server} is not public")
    print("defaults: disabled, conservative, digest-pinned, non-root")


def assert_compose_isolation() -> None:
    text = render(
        "compose.yaml.j2",
        hermes_agent_telegram_bot_token=SECRET_TOKEN,
        hermes_agent_provider_api_key=SECRET_KEY,
    )
    image = (
        f"{DEFAULTS['hermes_agent_image_repository']}@"
        f"{DEFAULTS['hermes_agent_image_digest']}"
    )
    required = (
        image,
        "privileged: false",
        "init: false",
        "no-new-privileges:true",
        "homelab.role: hermes_agent",
        DEFAULTS["hermes_agent_source_commit"],
        'HERMES_DASHBOARD: "0"',
        'API_SERVER_ENABLED: "false"',
        DEFAULTS["hermes_agent_container_data_dir"],
        DEFAULTS["hermes_agent_container_managed_dir"] + ":ro",
    )
    for item in required:
        if item not in text:
            raise SystemExit(f"compose missing {item!r}")
    forbidden = (
        "ports:",
        "privileged: true",
        "/var/run/docker.sock",
        "network_mode: host",
        "pid: host",
        "ipc: host",
        "cap_add:",
        SECRET_TOKEN,
        SECRET_KEY,
        "user: root",
        "user: \"0\"",
    )
    for item in forbidden:
        if item in text:
            raise SystemExit(f"compose must not contain {item!r}")
    print("compose: digest pin, no ports, no host namespaces, no secrets")


def assert_full_capability_config() -> None:
    config = load_yaml(
        "config.yaml.j2",
        hermes_agent_full_capability=True,
        hermes_agent_telegram_user_id=TELEGRAM_USER,
        hermes_agent_telegram_admin_id=TELEGRAM_USER,
    )
    extra = config["gateway"]["platforms"]["telegram"]["extra"]
    if config["unauthorized_dm_behavior"] != "ignore":
        raise SystemExit("pairing must stay ignore")
    if extra["guest_mode"] or extra["group_allowed_chats"] or extra["group_allow_from"]:
        raise SystemExit("guest mode and groups must stay disabled")
    if extra["allow_from"] != [TELEGRAM_USER]:
        raise SystemExit("allow_from must be the single Telegram user")
    if extra["allow_admin_from"] != [TELEGRAM_USER]:
        raise SystemExit("allow_admin_from must match the same user")
    if not config["memory"]["memory_enabled"] or config["memory"]["write_approval"]:
        raise SystemExit("full capability must auto-write memory")
    if not config["auxiliary"]["background_review"]["enabled"]:
        raise SystemExit("curator background review must be enabled")
    if config.get("agent", {}).get("disabled_toolsets"):
        raise SystemExit("full capability must not disable Telegram toolsets")
    print("config: one Telegram admin, pairing off, full toolset")


def assert_conservative_config() -> None:
    config = load_yaml(
        "config.yaml.j2",
        hermes_agent_full_capability=False,
        hermes_agent_telegram_user_id=TELEGRAM_USER,
        hermes_agent_telegram_admin_id=TELEGRAM_USER,
    )
    disabled = set(config["agent"]["disabled_toolsets"])
    required = {
        "terminal",
        "file",
        "web",
        "browser",
        "code_execution",
        "delegation",
        "cronjob",
        "memory",
        "skills",
        "session_search",
    }
    if required - disabled:
        raise SystemExit(f"conservative path missing {required - disabled}")
    if config["memory"]["memory_enabled"]:
        raise SystemExit("conservative path must disable memory")
    print("config: conservative defaults disable the powerful toolsets")


def assert_secrets_and_egress() -> None:
    env_text = render(
        "managed.env.j2",
        hermes_agent_telegram_bot_token=SECRET_TOKEN,
        hermes_agent_provider_api_key=SECRET_KEY,
        hermes_agent_telegram_user_id=TELEGRAM_USER,
        hermes_agent_provider_env_name="OPENROUTER_API_KEY",
    )
    if SECRET_TOKEN not in env_text or SECRET_KEY not in env_text:
        raise SystemExit("managed env must hold the runtime secrets")
    if "GATEWAY_ALLOW_ALL_USERS=false" not in env_text:
        raise SystemExit("allow-all users must stay disabled")
    if f"TELEGRAM_ALLOWED_USERS={TELEGRAM_USER}" not in env_text:
        raise SystemExit("managed env must pin the single Telegram user")
    egress = render("egress.sh.j2")
    for network in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "169.254.0.0/16",
        "127.0.0.0/8",
    ):
        if f'-d {network} -j DROP' not in egress:
            raise SystemExit(f"egress must drop {network}")
    if "Later MCP destinations get explicit ACCEPT" not in egress:
        raise SystemExit("egress must document later MCP exceptions")
    print("secrets stay in 0640 env; egress drops RFC1918 and link-local")


def assert_disable_preserves_state() -> None:
    if DEFAULTS["hermes_agent_data_dir"] in ABSENT.split("loop:")[-1]:
        # The remove loop must not include the persistent data directory.
        remove_block = ABSENT.split("Remove Hermes Agent managed files", 1)[1]
        if DEFAULTS["hermes_agent_data_dir"] in remove_block.split(
            "Leave Hermes Agent persistent state", 1
        )[0]:
            raise SystemExit("disable path must not delete persistent data")
    if "hermes_agent_preserve_state_on_disable" not in ABSENT:
        raise SystemExit("absent tasks must mention state preservation")
    if "groups: docker" in PRESENT or "docker" in PRESENT.split("Create the Hermes Agent runtime user", 1)[1].split("Create Hermes Agent directories", 1)[0]:
        raise SystemExit("runtime user must not be added to the docker group")
    print("disable path preserves /opt/hermes-agent/data; no docker group")


def assert_validation_contract() -> None:
    required_snippets = (
        "hermes_agent_source_commit is match('^[0-9a-f]{40}$')",
        "hermes_agent_image_digest is match('^sha256:[0-9a-f]{64}$')",
        "hermes_agent_runtime_user != 'root'",
        "hermes_agent_telegram_user_id | string is match('^[0-9]+$')",
        "(hermes_agent_telegram_user_id | string) == (hermes_agent_telegram_admin_id | string)",
        "hermes_agent_telegram_bot_token is not match('(?i)^replace')",
        "hermes_agent_provider_api_key is not match('(?i)^replace')",
    )
    for snippet in required_snippets:
        if snippet not in VALIDATE:
            raise SystemExit(f"validate.yml missing {snippet}")
    print("validate.yml rejects mutable tags, root, and REPLACE secrets")


def assert_example_and_specs() -> None:
    hermes = EXAMPLE_SITE["hermes"]
    guest = EXAMPLE_SITE["guests"]["hermes"]
    if guest["hostname"] != "hermes-example" or guest["vm_id"] != 117:
        raise SystemExit("fictional Hermes guest must stay on documentation IDs")
    if guest["ipv4"] != "192.0.2.17":
        raise SystemExit("fictional Hermes IP must stay in TEST-NET-1")
    if hermes["telegram_user_id"] != TELEGRAM_USER:
        raise SystemExit("example Telegram user ID drifted")
    if not hermes["enabled"] or not hermes["full_capability"]:
        raise SystemExit("example site must show the opt-in full-capability binding")
    specs = yaml.safe_load((ROLE / "meta/argument_specs.yml").read_text())
    options = specs["argument_specs"]["main"]["options"]
    for key in DEFAULTS:
        if key not in options:
            raise SystemExit(f"argument spec missing {key}")
    print("example site and argument specs cover the public contract")


def main() -> None:
    assert_defaults()
    assert_compose_isolation()
    assert_full_capability_config()
    assert_conservative_config()
    assert_secrets_and_egress()
    assert_disable_preserves_state()
    assert_validation_contract()
    assert_example_and_specs()
    print("hermes_agent rendered contract ok")


if __name__ == "__main__":
    main()
