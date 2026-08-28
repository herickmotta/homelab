from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


class ConfigError(ValueError):
    """Raised when required Hermes configuration is missing or unsafe."""


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is required")
    return value


def _csv(name: str) -> tuple[str, ...]:
    raw = os.environ.get(name, "")
    items = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not items:
        raise ConfigError(f"{name} needs at least one value")
    return items


def _json_list(name: str, default: list | None = None) -> list:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return list(default or [])
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ConfigError(f"{name} must be a JSON list")
    return data


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return int(raw)


@dataclass(frozen=True)
class Config:
    listen_host: str
    listen_port: int
    webhook_secret: str
    telegram_bot_token: str
    telegram_chat_id: int
    openai_api_key: str
    openai_model_default: str
    openai_model_complex: str
    sentinel_prometheus_url: str
    observe_prometheus_url: str
    observe_loki_url: str
    pve_url: str
    pve_token_id: str
    pve_token_secret: str
    pve_node: str
    github_token: str
    github_repository: str
    allowed_hosts: tuple[str, ...]
    allowed_services: tuple[str, ...]
    allowed_vmids: tuple[int, ...]
    allowed_git_paths: tuple[str, ...]
    log_sources: tuple[dict, ...]
    state_dir: str
    conversation_ttl_seconds: int = 86400
    conversation_max_turns: int = 12
    max_evidence_chars: int = 6000
    max_log_lines: int = 20
    openai_timeout_seconds: float = 60.0
    evidence_timeout_seconds: float = 10.0
    diagnosis_cooldown_seconds: int = 120
    extra: dict = field(default_factory=dict)

    @property
    def log_source_names(self) -> tuple[str, ...]:
        return tuple(str(item["name"]) for item in self.log_sources)

    @classmethod
    def from_env(cls) -> Config:
        listen = os.environ.get("HERMES_LISTEN_ADDRESS", "127.0.0.1:8787")
        host, port_s = listen.rsplit(":", 1)
        if host != "127.0.0.1":
            raise ConfigError("Hermes must listen on 127.0.0.1")
        secret = _require("HERMES_WEBHOOK_SECRET")
        if len(secret) < 16:
            raise ConfigError("HERMES_WEBHOOK_SECRET must be at least 16 characters")
        log_sources = tuple(_json_list("HERMES_LOG_SOURCES"))
        for item in log_sources:
            if not isinstance(item, dict):
                raise ConfigError("HERMES_LOG_SOURCES items must be objects")
            for key in ("name", "host", "kind", "selector"):
                if not str(item.get(key, "")).strip():
                    raise ConfigError(f"log source {item!r} needs {key}")
            if item["kind"] not in {"unit", "container"}:
                raise ConfigError("log source kind must be unit or container")
        vmids = tuple(int(value) for value in _csv("HERMES_ALLOWED_VMIDS"))
        git_paths = _csv("HERMES_ALLOWED_GIT_PATHS")
        for path in git_paths:
            if path.startswith("/") or ".." in path.split("/") or path.startswith("secrets"):
                raise ConfigError(f"git path {path} is not allowed")
        return cls(
            listen_host=host,
            listen_port=int(port_s),
            webhook_secret=secret,
            telegram_bot_token=_require("HERMES_TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=int(_require("HERMES_TELEGRAM_CHAT_ID")),
            openai_api_key=_require("HERMES_OPENAI_API_KEY"),
            openai_model_default=os.environ.get("HERMES_MODEL_DEFAULT", "gpt-5.6-luna"),
            openai_model_complex=os.environ.get("HERMES_MODEL_COMPLEX", "gpt-5.6-sol"),
            sentinel_prometheus_url=_require("HERMES_SENTINEL_PROMETHEUS_URL").rstrip("/"),
            observe_prometheus_url=os.environ.get("HERMES_OBSERVE_PROMETHEUS_URL", "").rstrip("/"),
            observe_loki_url=os.environ.get("HERMES_OBSERVE_LOKI_URL", "").rstrip("/"),
            pve_url=_require("HERMES_PVE_URL").rstrip("/"),
            pve_token_id=_require("HERMES_PVE_TOKEN_ID"),
            pve_token_secret=_require("HERMES_PVE_TOKEN_SECRET"),
            pve_node=_require("HERMES_PVE_NODE"),
            github_token=_require("HERMES_GITHUB_TOKEN"),
            github_repository=_require("HERMES_GITHUB_REPOSITORY"),
            allowed_hosts=_csv("HERMES_ALLOWED_HOSTS"),
            allowed_services=_csv("HERMES_ALLOWED_SERVICES"),
            allowed_vmids=vmids,
            allowed_git_paths=git_paths,
            log_sources=log_sources,
            state_dir=os.environ.get("HERMES_STATE_DIR", "/var/lib/hermes/state"),
            conversation_ttl_seconds=_int("HERMES_CONVERSATION_TTL_SECONDS", 86400),
            conversation_max_turns=_int("HERMES_CONVERSATION_MAX_TURNS", 12),
            diagnosis_cooldown_seconds=_int("HERMES_DIAGNOSIS_COOLDOWN_SECONDS", 120),
        )
