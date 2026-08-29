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
(Telegram, the model provider, web/browser, public DNS, time) allowed. Later
MCP destinations need explicit ACCEPT rules in that chain before the DROP
lines. Compose DNS is public resolvers, not a LAN resolver.

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

The site supplies `hermes_agent_provider`, `hermes_agent_model`,
`hermes_agent_telegram_user_id` (same value as admin), and runtime secrets
`hermes_agent_telegram_bot_token` plus `hermes_agent_provider_api_key`.

Disable stops and removes the container and managed secrets. Persistent
`/opt/hermes-agent/data` stays unless a site later chooses otherwise.

Backup and restore are upstream commands against that data directory:

```bash
docker exec hermes-agent hermes backup -o /opt/data/backups/hermes.zip
docker exec hermes-agent hermes import /opt/data/backups/hermes.zip --force
```

Treat backup archives as secret. Health is `hermes version` and
`hermes gateway status` inside the container.
