# hermes_agent

Deploy the official [Nous Research Hermes Agent](https://github.com/NousResearch/hermes-agent)
container. This role does not ship a custom agent loop.

The reusable defaults keep the role **disabled** and **conservative**. A site
must set `hermes_agent_enabled: true` and, for the full headless experience,
`hermes_agent_full_capability: true`.

## Upstream pin

| Field | Value |
| --- | --- |
| Source | `https://github.com/NousResearch/hermes-agent` |
| Commit | `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` (tag `v2026.8.27`, Hermes Agent v0.20.6) |
| Image | `nousresearch/hermes-agent@sha256:e0df6adebddf29b91112aefc999d4aaf6846c9eb544faca5672a16a13590ff79` |
| Provenance | OCI label `org.opencontainers.image.revision=5fc308a70719a83cccdbba4c0e39c23f5a8239d5` |

Do not use `latest`, a moving tag, `curl | bash`, or an in-container source
update. Upgrades change the reviewed digest and matching source commit.

## Boundary

The container runs the image entrypoint (s6 as PID 1, then `s6-setuidgid hermes`,
UID 10000). It is not privileged, does not use host namespaces, does not mount
the Docker socket or host `/home`/`/etc`/`/root`, and publishes no ports.

Managed policy lives on the host under `hermes_agent_managed_dir` and is mounted
read-only at `/opt/hermes-policy`. Persistent Hermes state is `/opt/data`.
Secrets are a 0640 `root:hermes` managed `.env`, never Compose environment
values or world-readable managed scope.

A `DOCKER-USER` chain `HERMES-AGENT-EGRESS` drops RFC1918 and link-local
destinations from the dedicated Compose subnet while leaving public Internet
(Telegram, the model provider, web/browser, public DNS, time) allowed. The
Compose subnet itself is RETURNed so sidecars on that network stay reachable.
Later LAN MCP destinations need explicit ACCEPT rules in that chain before
the DROP lines. Containers still use Docker embedded DNS (Compose names);
upstream resolvers are public, not a LAN resolver.

Telegram is one numeric allowlisted user who is also `allow_admin_from`.
Pairing (`unauthorized_dm_behavior: ignore`), guest mode, group allowlists, and
`GATEWAY_ALLOW_ALL_USERS` stay off.

## Full capability keys

When `hermes_agent_full_capability` is true, managed `config.yaml` sets:

- `memory.memory_enabled` / `memory.user_profile_enabled`: true
- `memory.write_approval` / `skills.write_approval`: false
- `auxiliary.background_review.enabled`: true (curator / learning loop)
- empty `agent.disabled_toolsets` so Telegram keeps the upstream
  `hermes-telegram` toolset (terminal, files, web, browser, code execution,
  delegation, cron, memory, skills, session search)

The site supplies `hermes_agent_provider`, `hermes_agent_model`, and
`hermes_agent_telegram_user_id` (same value as admin). Telegram's bot token
is a SOPS secret. `openai-codex` authenticates with ChatGPT device-code OAuth
into `$HERMES_HOME/auth.json` (`/opt/data/auth.json` in the container). Do
not inject an OpenAI or OpenRouter API key for that provider. Keep
`model.openai_runtime: auto` so Hermes retains memory, delegation, session
search, and its complete tool loop. `/codex-runtime codex_app_server` is out
of scope for this role.

## Optional GitHub App draft PRs

Defaults keep GitHub access **off**. A site may set
`hermes_agent_github_enabled: true` and supply a GitHub App installation
(app ID, installation ID, slug, PEM, and `https://github.com/...git`
repositories). The role then:

- writes the PEM as `0640` `root:hermes` under the managed directory
- installs a token helper that mints a one-hour installation token
- pins GitHub CLI `gh` and wraps it so `gh pr merge` is refused
- clones the named repositories into `/opt/data/repos`
- configures git to use the helper and a pre-push hook that blocks `main`

The App is a distinct actor from the operator. Contents and pull-request
write can still merge unless the repository's `main` protection denies that
App. This role does not grant Administration, Actions write, Secrets, or
Workflows. Do not put `GH_TOKEN` in Compose. Do not bind-mount operator
workstations or `.git` credentials.

## Optional read-only Proxmox API

Defaults keep Proxmox access **off**. A site may set
`hermes_agent_pve_enabled: true` with a dedicated `PVEAuditor` user, token
name, token secret, and hypervisor IPv4. The role then:

- writes `PVE_API_*` into the managed `0640` `.env`, never Compose
- installs `pve-get`, a GET-only wrapper around `/api2/json/`
- ACCEPTs TCP 8006 to that one IPv4 in `HERMES-AGENT-EGRESS` before the
  RFC1918 DROP rules

Do not reuse the OpenTofu, Observe, or Sentinel tokens. Do not open SSH or
the rest of the LAN. Guest power and config remain denied by `PVEAuditor`.

## Optional read-only Grafana MCP

Defaults keep Grafana access **off**. A site may set
`hermes_agent_grafana_enabled: true` with a Viewer service-account token, an
MCP caller token, and Grafana's guest IPv4 on port 3000. The role then:

- runs official `grafana/mcp-grafana` on the Hermes Compose network
- writes Viewer and MCP caller tokens to
  `hermes_agent_grafana_mcp_env_file` (`0640` `root:root`), **not** the
  Hermes policy mount or managed `.env`
- points Hermes `mcp_servers.grafana` at `http://grafana-mcp:8000/mcp`
  with the caller token only
- ACCEPTs TCP 3000 to that one Grafana IPv4, and RETURNs the Compose
  subnet so Hermes can reach the sidecar
- at apply time, `docker compose exec` from `hermes-agent` must resolve
  `grafana-mcp`, reach `/healthz`, see `401` without a caller token, and
  `initialize` with the caller token. Those checks do not print secrets.

Listen with `--address`, not `-addr`. Do not put
`GRAFANA_SERVICE_ACCOUNT_TOKEN` in the Hermes process. Do not route
through Caddy; the hole is Grafana's own `:3000`. Write tools stay off.

Telegram aliases `luna` (`gpt-5.6-luna`, default) and `sol` (`gpt-5.6-sol`)
are rendered for `openai-codex`. After login:

```text
/model sol --once
/model sol
/model luna
```

Disable stops and removes the container and managed secrets. Persistent
`/opt/hermes-agent/data` stays unless a site later chooses otherwise.

Backup and restore are upstream commands against that data directory:

```bash
docker exec hermes-agent hermes backup -o /opt/data/backups/hermes.zip
docker exec hermes-agent hermes import /opt/data/backups/hermes.zip --force
```

Treat backup archives as secret. Health is `hermes version` and
`hermes gateway status` inside the container.

Device-code login is interactive and happens after the container is up:

```bash
docker exec -it hermes-agent hermes model
```

Select **ChatGPT or Codex Subscription**, open the URL, and authorize the
ChatGPT account that has Codex access. Prefer `hermes model` over
`hermes auth add openai-codex` at this pin: the latter can write only the
credential pool while the runtime still reads `providers.tokens`. Treat
`auth.json` as secret (mode `0600` on the data volume). Codex CLI is not
required. Plan eligibility and how Hermes usage counts against Codex
subscription limits are not documented upstream; prove a Luna turn and watch
gateway logs for `429`, `invalid_grant`, quota, and re-auth failures.
