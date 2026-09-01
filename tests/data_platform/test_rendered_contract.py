#!/usr/bin/env python3
"""Render data_platform templates and assert the isolation contract."""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]
ROLE = ROOT / "ansible/roles/data_platform"
TEMPLATES = ROLE / "templates"
DEFAULTS = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
SQL_LEDGER = (ROLE / "files/sql/01-ops_ledger.sql").read_text()
SQL_ROLES = (ROLE / "files/sql/00-roles.sql").read_text()
ABSENT = (ROLE / "tasks/absent.yml").read_text()
VALIDATE = (ROLE / "tasks/validate.yml").read_text()
COMPOSE_TEXT = (ROLE / "templates/compose.yaml.j2").read_text()
EXAMPLE_SITE = yaml.safe_load(
    (ROOT / "examples/site.example.yaml").read_text()
)["site"]

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SECRET_JWT = "super-secret-jwt-token-with-at-least-32-chars"
SECRET_SERVICE = "service-role-jwt-not-for-compose"
SECRET_AWS = "aws-backup-secret-not-for-compose"


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
    env.filters["int"] = int
    env.filters["string"] = lambda value: "" if value is None else str(value)
    context = dict(DEFAULTS)
    context.update(overrides)
    return env.get_template(name).render(context)


def assert_defaults() -> None:
    if DEFAULTS["data_platform_enabled"]:
        raise SystemExit("role defaults must stay disabled")
    if not DEFAULTS["data_platform_preserve_state_on_disable"]:
        raise SystemExit("disable path must preserve state by default")
    for key in (
        "data_platform_postgres_image_digest",
        "data_platform_kong_image_digest",
        "data_platform_postgrest_image_digest",
        "data_platform_gotrue_image_digest",
        "data_platform_studio_image_digest",
        "data_platform_meta_image_digest",
    ):
        if not DIGEST_RE.match(DEFAULTS[key]):
            raise SystemExit(f"{key} must be a sha256 digest")
    if ":" in DEFAULTS["data_platform_postgres_image_repository"]:
        raise SystemExit("image repository must not include a tag")
    print("defaults: disabled, digest-pinned")


def assert_compose_subset() -> None:
    text = render(
        "compose.yaml.j2",
        data_platform_postgres_password="not-in-compose-check",
        data_platform_jwt_secret=SECRET_JWT,
        data_platform_anon_key="anon-key-not-for-compose",
        data_platform_service_role_key=SECRET_SERVICE,
    )
    required = (
        DEFAULTS["data_platform_postgres_image_digest"],
        DEFAULTS["data_platform_kong_image_digest"],
        "127.0.0.1:5432",
        "127.0.0.1:3000",
        "homelab.role: data_platform",
        "PGRST_DB_SCHEMAS: ops_ledger",
        "GOTRUE_DB_NAMESPACE: auth",
        "HOSTNAME: \"0.0.0.0\"",
        "/migrations:ro",
    )
    for item in required:
        if item not in text:
            raise SystemExit(f"compose missing {item!r}")
    for forbidden in (
        "realtime",
        "storage-api",
        "edge-runtime",
        "logflare",
        "imgproxy",
        "vector:",
        SECRET_JWT,
        SECRET_SERVICE,
        "0.0.0.0:5432",
        "0.0.0.0:3000",
    ):
        if forbidden in text:
            raise SystemExit(f"compose must not contain {forbidden!r}")
    if f"{DEFAULTS['data_platform_kong_port']}:8000" not in text:
        raise SystemExit("kong must publish :8000")
    print("compose: subset, loopback postgres/studio, digest pins, no secrets")


def assert_ingress_and_backup() -> None:
    ingress = render(
        "ingress.sh.j2",
        data_platform_api_allow_from=["192.0.2.17/32", "192.0.2.0/24"],
    )
    if "192.0.2.17/32" not in ingress or "-j DROP" not in ingress:
        raise SystemExit("ingress must allowlist then DROP")
    backup = render("backup.sh.j2")
    if SECRET_AWS in backup:
        raise SystemExit("backup.sh must not inline AWS secrets")
    if "pg_dump" not in backup or "pg_dumpall" not in backup or "age -r" not in backup:
        raise SystemExit("backup must dump postgres, roles, and age-encrypt")
    if "exec -T db pg_dump" not in backup or "exec -T db pg_dumpall" not in backup:
        raise SystemExit("backup must dump from the pinned db container")
    if "-h 127.0.0.1" in backup:
        raise SystemExit("backup must not use host pg_dump against loopback")
    if "stack.env" in backup:
        raise SystemExit("container dump must not source stack.env")
    if "aws s3 cp" in backup:
        raise SystemExit("default backup.sh must not upload to S3")
    s3_backup = render("backup.sh.j2", data_platform_backup_s3_enabled=True)
    if "aws s3 cp" not in s3_backup:
        raise SystemExit("S3-enabled backup.sh must upload")
    env = render(
        "backup.env.j2",
        data_platform_backup_aws_secret_access_key=SECRET_AWS,
    )
    if SECRET_AWS not in env:
        raise SystemExit("backup.env should hold the IAM secret")
    present = (ROLE / "tasks/present.yml").read_text()
    if "awscli" in present and "data_platform_backup_s3_enabled" not in present:
        raise SystemExit("awscli must be conditional on S3 backups")
    print("ingress allowlist and backup dump contract")


def assert_sql_contract() -> None:
    if "CREATE SCHEMA IF NOT EXISTS ops_ledger" not in SQL_LEDGER:
        raise SystemExit("ops_ledger schema missing")
    if "CREATE SCHEMA IF NOT EXISTS finance" in SQL_LEDGER or "CREATE SCHEMA IF NOT EXISTS media_catalog" in SQL_LEDGER:
        raise SystemExit("first increment must not create other domains")
    if "append_event" not in SQL_LEDGER or "add_feedback" not in SQL_LEDGER:
        raise SystemExit("RPC functions missing")
    if "ops_ledger_hermes" not in SQL_ROLES:
        raise SystemExit("hermes role missing")
    if "CREATE SCHEMA IF NOT EXISTS auth" not in SQL_ROLES:
        raise SystemExit("GoTrue auth schema missing")
    if "search_path TO auth, public" not in SQL_ROLES:
        raise SystemExit("supabase_auth_admin search_path missing")
    if "GRANT USAGE, CREATE ON SCHEMA public TO supabase_auth_admin" not in SQL_ROLES:
        raise SystemExit("Postgres 15 public CREATE grant missing")
    present = (ROLE / "tasks/present.yml").read_text()
    if present.index("Apply role bootstrap SQL") > present.index(
        "Apply data platform Compose handlers"
    ):
        raise SystemExit("role SQL must run before compose recreate so GoTrue sees grants")
    if "Restart auth and rest after role SQL" not in present:
        raise SystemExit("auth must restart after role SQL")
    if 'owner: "999"' in present:
        raise SystemExit("do not force Docker Hub postgres uid 999 on supabase/postgres data")
    print("sql: ops_ledger only, RPCs present, GoTrue auth schema")


def assert_absent_and_validate() -> None:
    if "data_platform_data_dir" in ABSENT.split("Remove data platform units")[1].split(
        "Leave data platform persistent state"
    )[0]:
        raise SystemExit("absent must not delete the data directory")
    if "data_platform_jwt_secret | length >= 32" not in VALIDATE:
        raise SystemExit("validate must require a long JWT secret")
    if "data_platform_public_url is match('^http://127\\\\.0\\\\.0\\\\.1')" not in VALIDATE:
        raise SystemExit("validate must keep public URL on loopback")
    if "data_platform_backup_s3_enabled" not in VALIDATE:
        raise SystemExit("validate must treat S3 backup as optional")
    print("absent preserves data; validate rejects REPLACE secrets")


def assert_example_and_specs() -> None:
    guest = EXAMPLE_SITE["guests"]["data"]
    if guest["vm_id"] != 118 or guest["ipv4"] != "192.0.2.18":
        raise SystemExit("fictional data guest must stay on documentation IDs")
    if EXAMPLE_SITE["data_platform"]["enabled"]:
        raise SystemExit("example data_platform must stay disabled")
    if EXAMPLE_SITE["data_platform"].get("backup_s3_enabled", True):
        raise SystemExit("example data_platform must leave S3 backups off")
    if "data_platform" not in guest["groups"]:
        raise SystemExit("example guest must include data_platform")
    specs = yaml.safe_load((ROLE / "meta/argument_specs.yml").read_text())
    options = specs["argument_specs"]["main"]["options"]
    for key in DEFAULTS:
        if key not in options:
            raise SystemExit(f"argument spec missing {key}")
    print("example site and argument specs cover the public contract")


def main() -> None:
    assert_defaults()
    assert_compose_subset()
    assert_ingress_and_backup()
    assert_sql_contract()
    assert_absent_and_validate()
    assert_example_and_specs()


if __name__ == "__main__":
    main()
