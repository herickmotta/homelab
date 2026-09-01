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
    ].get(context["hermes_agent_provider"], "")
    context.update(overrides)
    return env.get_template(name).render(context)


def load_yaml(name: str, **overrides) -> dict:
    return yaml.safe_load(render(name, **overrides))


def assert_defaults() -> None:
    if DEFAULTS["hermes_agent_enabled"] or DEFAULTS["hermes_agent_full_capability"]:
        raise SystemExit("role defaults must stay disabled and conservative")
    if DEFAULTS["hermes_agent_github_enabled"]:
        raise SystemExit("GitHub App access must stay disabled until a site opts in")
    if DEFAULTS["hermes_agent_pve_enabled"]:
        raise SystemExit("Proxmox API access must stay disabled until a site opts in")
    if DEFAULTS["hermes_agent_grafana_enabled"]:
        raise SystemExit("Grafana MCP access must stay disabled until a site opts in")
    if DEFAULTS["hermes_agent_ops_ledger_enabled"]:
        raise SystemExit("ops_ledger MCP access must stay disabled until a site opts in")
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
    if DEFAULTS["hermes_agent_provider"] != "openai-codex":
        raise SystemExit("reusable default provider must be openai-codex")
    if DEFAULTS["hermes_agent_model"] != "gpt-5.6-luna":
        raise SystemExit("reusable default model must be gpt-5.6-luna")
    if DEFAULTS["hermes_agent_openai_runtime"] != "auto":
        raise SystemExit("openai_runtime must stay auto")
    if "openai-codex" not in DEFAULTS["hermes_agent_oauth_providers"]:
        raise SystemExit("openai-codex must be an OAuth provider")
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
        "BEGIN ",
        "GH_TOKEN",
    )
    for item in forbidden:
        if item in text:
            raise SystemExit(f"compose must not contain {item!r}")
    if "- version" in text and "- --version" not in text:
        raise SystemExit("healthcheck must use hermes --version")
    if "- --version" not in text:
        raise SystemExit("healthcheck must call hermes --version")
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
    if config["model"]["provider"] != "openai-codex":
        raise SystemExit("full-capability default provider must be openai-codex")
    if config["model"]["default"] != "gpt-5.6-luna":
        raise SystemExit("everyday default must be gpt-5.6-luna")
    if config["model"]["openai_runtime"] != "auto":
        raise SystemExit("openai_runtime must stay auto, not codex_app_server")
    aliases = config["model_aliases"]
    if aliases["luna"]["model"] != "gpt-5.6-luna" or aliases["sol"]["model"] != "gpt-5.6-sol":
        raise SystemExit("luna/sol Telegram aliases drifted")
    print("config: one Telegram admin, pairing off, full toolset, Luna runtime")


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
    oauth_env = render(
        "managed.env.j2",
        hermes_agent_telegram_bot_token=SECRET_TOKEN,
        hermes_agent_provider_api_key="",
        hermes_agent_telegram_user_id=TELEGRAM_USER,
        hermes_agent_provider_env_name="",
    )
    if SECRET_TOKEN not in oauth_env:
        raise SystemExit("managed env must hold the Telegram token")
    if SECRET_KEY in oauth_env or "OPENROUTER_API_KEY=" in oauth_env:
        raise SystemExit("oauth managed env must not hold a provider API key")
    if "GATEWAY_ALLOW_ALL_USERS=false" not in oauth_env:
        raise SystemExit("allow-all users must stay disabled")
    if f"TELEGRAM_ALLOWED_USERS={TELEGRAM_USER}" not in oauth_env:
        raise SystemExit("managed env must pin the single Telegram user")
    if "HERMES_GITHUB_APP_ID=" in oauth_env or "GH_TOKEN=" in oauth_env:
        raise SystemExit("GitHub App env must stay out of the default managed env")
    keyed_env = render(
        "managed.env.j2",
        hermes_agent_telegram_bot_token=SECRET_TOKEN,
        hermes_agent_provider_api_key=SECRET_KEY,
        hermes_agent_telegram_user_id=TELEGRAM_USER,
        hermes_agent_provider_env_name="OPENROUTER_API_KEY",
    )
    if SECRET_KEY not in keyed_env or "OPENROUTER_API_KEY=" not in keyed_env:
        raise SystemExit("API-key providers must still render the provider secret")
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
    if "-p tcp --dport 8006 -j ACCEPT" in egress:
        raise SystemExit("default egress must not punch a Proxmox hole")
    if '-d "${SUBNET}" -j RETURN' not in egress:
        raise SystemExit("default egress must RETURN the Compose subnet")
    if "--dport 8000 -j ACCEPT" in egress:
        raise SystemExit("default egress must not punch a data-platform hole")
    ledger_egress = render(
        "egress.sh.j2",
        hermes_agent_ops_ledger_enabled=True,
        hermes_agent_ops_ledger_ipv4="192.0.2.18",
        hermes_agent_ops_ledger_port=8000,
    )
    if "-d 192.0.2.18 -p tcp --dport 8000 -j ACCEPT" not in ledger_egress:
        raise SystemExit("ops_ledger egress must ACCEPT data:8000")
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
        "hermes_agent_openai_runtime == 'auto'",
        "hermes_agent_provider not in hermes_agent_oauth_providers",
        "hermes_agent_provider_api_key | length == 0",
        "hermes_agent_github_enabled | bool",
        "hermes_agent_github_app_id | string is match('^[0-9]+$')",
        "'PRIVATE KEY' in hermes_agent_github_app_private_key",
        "item.url is match(\"^https://github.com/.+\\\\.git$\")",
        "hermes_agent_pve_enabled | bool",
        "hermes_agent_pve_user is match('^[A-Za-z0-9._-]+@pve$')",
        "hermes_agent_pve_token_value is not match('(?i)^replace')",
        "hermes_agent_grafana_enabled | bool",
        "hermes_agent_grafana_viewer_token is not match('(?i)^replace')",
        "hermes_agent_ops_ledger_enabled | bool",
        "hermes_agent_ops_ledger_jwt is not match('(?i)^replace')",
    )
    for snippet in required_snippets:
        if snippet not in VALIDATE:
            raise SystemExit(f"validate.yml missing {snippet}")
    print("validate.yml rejects mutable tags, root, app-server runtime, and REPLACE secrets")


def assert_example_and_specs() -> None:
    hermes = EXAMPLE_SITE["hermes"]
    guest = EXAMPLE_SITE["guests"]["hermes"]
    if guest["hostname"] != "hermes-example" or guest["vm_id"] != 117:
        raise SystemExit("fictional Hermes guest must stay on documentation IDs")
    if guest["ipv4"] != "192.0.2.17":
        raise SystemExit("fictional Hermes IP must stay in TEST-NET-1")
    if hermes["telegram_user_id"] != TELEGRAM_USER:
        raise SystemExit("example Telegram user ID drifted")
    if hermes["provider"] != "openai-codex" or hermes["model"] != "gpt-5.6-luna":
        raise SystemExit("example site must bind openai-codex / gpt-5.6-luna")
    if not hermes["enabled"] or not hermes["full_capability"]:
        raise SystemExit("example site must show the opt-in full-capability binding")
    if hermes.get("github", {}).get("enabled"):
        raise SystemExit("example site must keep GitHub App access disabled")
    if hermes.get("pve", {}).get("enabled"):
        raise SystemExit("example site must keep Proxmox API access disabled")
    if hermes.get("grafana", {}).get("enabled"):
        raise SystemExit("example site must keep Grafana MCP access disabled")
    if hermes.get("ops_ledger", {}).get("enabled"):
        raise SystemExit("example site must keep ops_ledger MCP access disabled")
    specs = yaml.safe_load((ROLE / "meta/argument_specs.yml").read_text())
    options = specs["argument_specs"]["main"]["options"]
    for key in DEFAULTS:
        if key not in options:
            raise SystemExit(f"argument spec missing {key}")
    print("example site and argument specs cover the public contract")


def assert_github_draft_pr_helpers() -> None:
    if DEFAULTS["hermes_agent_github_repos"]:
        raise SystemExit("default GitHub repo list must stay empty")
    if DEFAULTS["hermes_agent_github_container_repos_dir"] != "/opt/data/repos":
        raise SystemExit("GitHub clones must live under /opt/data/repos")
    files_dir = ROLE / "files"
    wrapper = (files_dir / "gh").read_text()
    hook = (files_dir / "git-pre-push-no-main").read_text()
    token_helper = (files_dir / "github-app-token").read_text()
    if "must not merge pull requests" not in wrapper:
        raise SystemExit("gh wrapper must refuse merge")
    if "refs/heads/main" not in hook:
        raise SystemExit("pre-push hook must block main")
    if "sys.stdout.write(token)" not in token_helper:
        raise SystemExit("token helper must print only the token")
    github_env = render(
        "managed.env.j2",
        hermes_agent_telegram_bot_token=SECRET_TOKEN,
        hermes_agent_provider_api_key="",
        hermes_agent_telegram_user_id=TELEGRAM_USER,
        hermes_agent_provider_env_name="",
        hermes_agent_github_enabled=True,
        hermes_agent_github_app_id="4765344",
        hermes_agent_github_installation_id="157602350",
    )
    if "HERMES_GITHUB_APP_ID=4765344" not in github_env:
        raise SystemExit("enabled GitHub env must pin the App ID")
    if "GH_TOKEN=" in github_env or "BEGIN " in github_env:
        raise SystemExit("managed env must not hold GH_TOKEN or the PEM")
    if "/opt/hermes-policy/bin" not in github_env:
        raise SystemExit("GitHub helpers must be first on PATH")
    soul = render("SOUL.md.j2", hermes_agent_github_enabled=True)
    if "Never merge" not in soul or "gh pr merge" not in soul:
        raise SystemExit("SOUL.md must forbid GitHub merges when the App is enabled")
    github_tasks = (ROLE / "tasks/github.yml").read_text()
    if "github-app.pem" not in github_tasks or "mode: \"0640\"" not in github_tasks:
        raise SystemExit("GitHub App PEM must be installed mode 0640")
    print("github draft-PR helpers: token mint, no merge, no PEM in env")


def assert_pve_read_only_helpers() -> None:
    helper = (ROLE / "files/pve-get").read_text()
    if "-X GET" not in helper or "PVEAPIToken=" not in helper:
        raise SystemExit("pve-get must be a GET-only Proxmox client")
    if "status/start" not in helper:
        raise SystemExit("pve-get must refuse guest start paths")
    if 'pvedir=$(CDPATH= cd -- "${bindir}/../pve" && pwd)' not in helper:
        raise SystemExit("pve-get must read credentials from managed/pve files")
    pve_env = render(
        "managed.env.j2",
        hermes_agent_telegram_bot_token=SECRET_TOKEN,
        hermes_agent_provider_api_key="",
        hermes_agent_telegram_user_id=TELEGRAM_USER,
        hermes_agent_provider_env_name="",
        hermes_agent_pve_enabled=True,
        hermes_agent_pve_ipv4="192.0.2.10",
        hermes_agent_pve_user="hermes@pve",
        hermes_agent_pve_token_name="hermes",
        hermes_agent_pve_token_value="pve-secret-not-for-compose",
    )
    if "PVE_API_TOKEN_SECRET=" in pve_env or "PVE_API_TOKEN_ID=" in pve_env:
        raise SystemExit("managed env must not hold PVE TOKEN/SECRET names")
    if "pve-secret-not-for-compose" in pve_env:
        raise SystemExit("managed env must not hold the PVE token secret")
    if "/opt/hermes-policy/bin" not in pve_env:
        raise SystemExit("PVE helper must be first on PATH")
    pve_tasks = (ROLE / "tasks/pve.yml").read_text()
    if "managed_dir }}/pve/token-secret" not in pve_tasks:
        raise SystemExit("pve.yml must install the token secret as a file")
    if "no_log: true" not in pve_tasks:
        raise SystemExit("pve.yml must no_log the token secret task")
    compose = render(
        "compose.yaml.j2",
        hermes_agent_pve_enabled=True,
        hermes_agent_pve_token_value="pve-secret-not-for-compose",
    )
    if "pve-secret-not-for-compose" in compose or "PVE_API_TOKEN_SECRET" in compose:
        raise SystemExit("Compose must not hold the PVE token")
    egress = render(
        "egress.sh.j2",
        hermes_agent_pve_enabled=True,
        hermes_agent_pve_ipv4="192.0.2.10",
    )
    accept = "-d 192.0.2.10 -p tcp --dport 8006 -j ACCEPT"
    if accept not in egress:
        raise SystemExit("enabled PVE egress must ACCEPT hypervisor :8006 before DROP")
    drop_at = egress.find("-d 192.168.0.0/16 -j DROP")
    if drop_at < 0 or egress.find(accept) > drop_at:
        raise SystemExit("PVE ACCEPT must be inserted before RFC1918 DROP")
    soul = render("SOUL.md.j2", hermes_agent_pve_enabled=True)
    if "pve-get" not in soul or "PVEAuditor" not in soul:
        raise SystemExit("SOUL.md must describe GET-only Proxmox access")
    if "/opt/hermes-policy/bin/pve-get" not in soul or "execute_code" not in soul:
        raise SystemExit("SOUL.md must point Hermes at the deployed pve-get binary")
    if "{{ hermes_agent_managed_dir }}/pve" not in ABSENT:
        raise SystemExit("absent.yml must remove managed/pve credentials")
    print("pve read-only: GET helper, :8006 hole, secret stays out of Compose")


def assert_grafana_mcp_sidecar() -> None:
    viewer = "glsa-viewer-secret-not-for-hermes"
    caller = "mcp-caller-secret-not-for-logs"
    grafana_env = render(
        "grafana-mcp.env.j2",
        hermes_agent_grafana_enabled=True,
        hermes_agent_grafana_url="http://192.0.2.15:3000",
        hermes_agent_grafana_viewer_token=viewer,
        hermes_agent_grafana_mcp_server_token=caller,
    )
    if f"GRAFANA_URL=http://192.0.2.15:3000" not in grafana_env:
        raise SystemExit("grafana-mcp env must pin the Grafana URL")
    if f"GRAFANA_SERVICE_ACCOUNT_TOKEN={viewer}" not in grafana_env:
        raise SystemExit("grafana-mcp env must hold the Viewer token")
    if f"MCP_GRAFANA_SERVER_TOKEN={caller}" not in grafana_env:
        raise SystemExit("grafana-mcp env must hold the MCP caller token")
    managed = render(
        "managed.env.j2",
        hermes_agent_telegram_bot_token=SECRET_TOKEN,
        hermes_agent_provider_api_key="",
        hermes_agent_telegram_user_id=TELEGRAM_USER,
        hermes_agent_provider_env_name="",
        hermes_agent_grafana_enabled=True,
        hermes_agent_grafana_url="http://192.0.2.15:3000",
        hermes_agent_grafana_viewer_token=viewer,
        hermes_agent_grafana_mcp_server_token=caller,
    )
    if "GRAFANA_SERVICE_ACCOUNT_TOKEN=" in managed or viewer in managed:
        raise SystemExit("Hermes managed .env must not hold the Grafana Viewer token")
    if caller in managed:
        raise SystemExit("Hermes managed .env must not hold the MCP caller token")
    config = render(
        "config.yaml.j2",
        hermes_agent_grafana_enabled=True,
        hermes_agent_grafana_mcp_server_token=caller,
    )
    if "url: \"http://grafana-mcp:8000/mcp\"" not in config:
        raise SystemExit("Hermes config must point at Docker DNS grafana-mcp")
    if f"Bearer {caller}" not in config:
        raise SystemExit("Hermes config must send the MCP caller token")
    if viewer in config or "GRAFANA_SERVICE_ACCOUNT_TOKEN" in config:
        raise SystemExit("Hermes config must not hold the Grafana Viewer token")
    compose = render(
        "compose.yaml.j2",
        hermes_agent_grafana_enabled=True,
        hermes_agent_grafana_viewer_token=viewer,
        hermes_agent_grafana_mcp_server_token=caller,
    )
    if re.search(r"^\s+- -addr\s*$", compose, re.M):
        raise SystemExit("grafana-mcp must use --address, not -addr")
    if "--address" not in compose:
        raise SystemExit("grafana-mcp must pass --address")
    if "--enabled-tools" not in compose:
        raise SystemExit("grafana-mcp must pass --enabled-tools")
    if "prometheus" not in compose or "loki" not in compose:
        raise SystemExit("grafana-mcp must enable prometheus and loki query tools")
    env_file = DEFAULTS["hermes_agent_grafana_mcp_env_file"]
    if env_file not in compose:
        raise SystemExit("grafana-mcp env_file must stay outside the policy mount")
    if DEFAULTS["hermes_agent_managed_dir"] + "/grafana-mcp.env" in compose:
        raise SystemExit("grafana-mcp env must not live in the Hermes policy mount")
    if viewer in compose or caller in compose:
        raise SystemExit("Compose must not hold Grafana or MCP tokens")
    egress = render(
        "egress.sh.j2",
        hermes_agent_grafana_enabled=True,
        hermes_agent_grafana_ipv4="192.0.2.15",
    )
    if '-d "${SUBNET}" -j RETURN' not in egress:
        raise SystemExit("egress must RETURN the Compose subnet before RFC1918 DROP")
    accept = "-d 192.0.2.15 -p tcp --dport 3000 -j ACCEPT"
    if accept not in egress:
        raise SystemExit("enabled Grafana egress must ACCEPT :3000 before DROP")
    drop_at = egress.find("-d 172.16.0.0/12 -j DROP")
    if drop_at < 0 or egress.find('-d "${SUBNET}" -j RETURN') > drop_at:
        raise SystemExit("Compose subnet RETURN must be inserted before 172.16/12 DROP")
    if egress.find(accept) > drop_at:
        raise SystemExit("Grafana ACCEPT must be inserted before RFC1918 DROP")
    if 'dest: "{{ hermes_agent_managed_dir }}/grafana-mcp.env"' in PRESENT:
        raise SystemExit("present.yml must not write grafana-mcp.env into the policy mount")
    if "python3" in PRESENT and "\n      - -\n" in PRESENT:
        raise SystemExit("acceptance must not pipe the helper through python3 -")
    if "/bin/check-grafana-mcp.py" not in PRESENT:
        raise SystemExit("present.yml must docker exec the Grafana MCP helper from hermes-agent")
    if "{{ hermes_agent_grafana_mcp_env_file }}" not in ABSENT:
        raise SystemExit("absent.yml must remove the Grafana MCP env file")
    if "{{ hermes_agent_managed_dir }}/bin/check-grafana-mcp.py" not in ABSENT:
        raise SystemExit("absent.yml must remove the Grafana MCP acceptance helper")
    if "{{ hermes_agent_managed_dir }}/grafana-mcp.env" not in ABSENT:
        raise SystemExit("absent.yml must remove leftover policy-mount Grafana env")
    soul = render("SOUL.md.j2", hermes_agent_grafana_enabled=True)
    if "grafana-mcp" not in soul or "Viewer token" not in soul:
        raise SystemExit("SOUL.md must describe sidecar-only Grafana access")
    if "Telegram channel" not in soul or "pager" not in soul:
        raise SystemExit("SOUL.md must describe channel+email paging")
    if "HMAC-v2" not in soul and "webhook" not in soul.lower():
        raise SystemExit("SOUL.md must describe the Grafana webhook triage path")
    if "payload is the alert" not in soul.lower() and "webhook payload" not in soul.lower():
        raise SystemExit("SOUL.md must treat the webhook payload as alert identity")
    if "homelab_docker_" not in soul:
        raise SystemExit("SOUL.md must point Hermes at homelab_docker_* Grafana metrics")
    if "homelab_local_tcp_up" not in soul or "Do not request guest SSH" not in soul:
        raise SystemExit("SOUL.md must correlate host TCP probes without requesting SSH")
    check = (ROLE / "files/check-grafana-mcp.py").read_text()
    if "socket.gethostbyname" not in check or "healthz" not in check:
        raise SystemExit("acceptance helper must resolve grafana-mcp and hit healthz")
    if "print(" in check and "token" in check.lower() and "MCP_CALLER_TOKEN" in check:
        # allow reading the env name, not printing the value
        for line in check.splitlines():
            if "print(" in line and "token" in line.lower() and "MCP_CALLER_TOKEN" not in line and "missing" not in line:
                raise SystemExit(f"acceptance helper must not print tokens: {line}")
    print("grafana mcp: --address, sidecar env, subnet RETURN, apply checks")


def assert_webhook_disabled_by_default() -> None:
    if DEFAULTS["hermes_agent_webhook_enabled"]:
        raise SystemExit("Grafana webhook must stay disabled until a site opts in")
    compose = render("compose.yaml.j2")
    if "8644" in compose or "8787" in compose:
        raise SystemExit("disabled Hermes Compose must not publish webhook ports")
    config = render(
        "config.yaml.j2",
        hermes_agent_telegram_user_id=TELEGRAM_USER,
        hermes_agent_telegram_admin_id=TELEGRAM_USER,
        hermes_agent_grafana_enabled=True,
        hermes_agent_grafana_mcp_server_token="mcp-caller-secret-not-for-logs",
    )
    if "webhook:" in config:
        raise SystemExit("disabled Hermes config must not declare a webhook route")
    managed = render(
        "managed.env.j2",
        hermes_agent_telegram_bot_token=SECRET_TOKEN,
        hermes_agent_provider_api_key="",
        hermes_agent_telegram_user_id=TELEGRAM_USER,
        hermes_agent_provider_env_name="",
    )
    if "WEBHOOK_ENABLED=true" in managed:
        raise SystemExit("managed .env must not enable a Hermes webhook by default")
    if "hermes-alert-adapter.service" not in PRESENT:
        raise SystemExit("present.yml must stop leftover adapter unit")
    if "{{ hermes_agent_relay_unit }}" not in PRESENT:
        raise SystemExit("present.yml must manage the Grafana HMAC relay")
    print("webhook: disabled by default; leftover adapter still cleaned")


def assert_webhook_enabled_loopback() -> None:
    compose = render("compose.yaml.j2", hermes_agent_webhook_enabled=True)
    if '"127.0.0.1:8644:8644"' not in compose.replace(" ", ""):
        if "127.0.0.1:8644:8644" not in compose:
            raise SystemExit("enabled webhook must publish 127.0.0.1:8644 only")
    if "0.0.0.0:8644" in compose:
        raise SystemExit("Hermes webhook must not bind the LAN")
    config = render(
        "config.yaml.j2",
        hermes_agent_telegram_user_id=TELEGRAM_USER,
        hermes_agent_telegram_admin_id=TELEGRAM_USER,
        hermes_agent_webhook_enabled=True,
        hermes_agent_webhook_secret="hermes-hmac-secret-16",
        hermes_agent_grafana_enabled=True,
        hermes_agent_grafana_mcp_server_token="mcp-caller-secret-not-for-logs",
    )
    if "grafana-alert" not in config or "deliver: telegram" not in config:
        raise SystemExit("enabled webhook route must deliver Grafana events to Telegram")
    if "terminal" in config.split("grafana-alert", 1)[-1][:400]:
        raise SystemExit("webhook route must not grant terminal")
    if "INSECURE_NO_AUTH" in config:
        raise SystemExit("webhook must not disable HMAC")
    required_prompt = (
        "Scope all investigation to the",
        "not escalate unrelated firing rules",
        "test is not a",
        "visual format",
        "blank lines between blocks",
        "🚦 *STATUS:* 🔴 ACTION_REQUIRED",
        "🚨 *ALERT:*",
        "🎯 *TARGET:*",
        "📝 *RESULT:*",
        "🔎 *EVIDENCE:*",
        "➡️ *NEXT:*",
        "📊 *CONFIDENCE:* HIGH",
        "Status icons:",
        "Internal payload for investigation only",
        "{__raw__}",
        "{alert_summary}",
    )
    for snippet in required_prompt:
        if snippet not in config:
            raise SystemExit(f"webhook prompt missing {snippet!r}")
    if "Grafana-managed" not in config:
        raise SystemExit("webhook prompt must not treat empty Grafana rules as missing identity")
    ingress = render(
        "relay-ingress.sh.j2",
        hermes_agent_relay_allow_from="192.0.2.16",
        hermes_agent_relay_listen_port=8787,
    )
    if "192.0.2.16" not in ingress or "8787" not in ingress:
        raise SystemExit("relay ingress must allow only the observe IPv4")
    if "hermes_agent_webhook_secret" not in VALIDATE:
        raise SystemExit("validate.yml must require webhook secrets")
    print("webhook: loopback publish, HMAC route, observe-IP ingress")


def main() -> None:
    assert_defaults()
    assert_compose_isolation()
    assert_full_capability_config()
    assert_conservative_config()
    assert_secrets_and_egress()
    assert_disable_preserves_state()
    assert_validation_contract()
    assert_example_and_specs()
    assert_github_draft_pr_helpers()
    assert_pve_read_only_helpers()
    assert_grafana_mcp_sidecar()
    assert_webhook_disabled_by_default()
    assert_webhook_enabled_loopback()
    print("hermes_agent rendered contract ok")


if __name__ == "__main__":
    main()
