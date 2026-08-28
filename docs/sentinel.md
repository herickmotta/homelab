# Independent Sentinel host

The Sentinel is a small physical machine outside the Proxmox failure domain.
It has two jobs: run the reviewed deployment workflow and retain enough
independent evidence to say whether the hypervisor and critical household
services are alive. It is not the rich observability system and it is not a
state backend.

## Bootstrap boundary

The operator installs a minimal x86_64 Ubuntu Server 24.04 or 26.04 image,
allocates the system disk, configures initial network/SSH access, and runs a
site-owned bootstrap playbook from a workstation. Ansible owns everything
after that first SSH connection:

1. `sentinel_base` installs packages, creates the `gha` deployment identity
   and an isolated non-login `hermes` identity, hardens SSH, enables automatic
   security updates, bounds Docker logs, and configures the firewall.
2. `github_actions_runner` verifies the pinned bootstrap archive checksum,
   performs first registration with a short-lived token, and installs the
   runner as a systemd service. GitHub's default runner self-update remains
   enabled; the bootstrap version is not a long-lived enforcement control.
3. `sentinel_monitoring` renders and starts the pinned monitoring Compose
   project, alert rules, notification routing, and optional external
   heartbeat timer.

The site repository owns the real address, repository URL, probe targets,
notification routing, encrypted credentials, and bootstrap runbook.

## Security boundary

The runner is deployment authority. Membership in the Docker group and
passwordless sudo are root-equivalent and are intentionally limited to its
dedicated Unix account. A site should scope the runner to one private
deployment repository and protect its apply environment.

The `hermes` user has no login shell, sudo, Docker group, runner home, SOPS
key, SSH private key, or apply credentials. This role only reserves the
identity; an agent runtime is a later capability with its own typed
interface.

The age private key and deployment SSH private key are not stored in either
repository. They must be restored through the site's private recovery
procedure after a reinstall.

## Monitoring boundary

Sentinel monitoring is deliberately small:

- Prometheus keeps 72 hours and 10 GB by default;
- Blackbox probes ICMP, HTTP(S), and TCP endpoints;
- typed direct scrapes can retain a small service signal such as Frigate
  camera input FPS;
- the PVE exporter uses a dedicated `PVEAuditor` token;
- node exporter reports Sentinel disk and memory pressure;
- Alertmanager groups notifications and inhibits guest alerts while the
  hypervisor is unreachable;
- an optional systemd timer pings an external dead-man service.

Prometheus, exporters, and their APIs bind to loopback by default.
Alertmanager stays loopback unless a site sets a LAN bind address, typically
`0.0.0.0:9093`. That listener is not on Caddy and is not a management UI.
A host firewall rule must allow only the observability guest to reach it.
Sentinel Prometheus continues to use loopback. Raw email and Proxmox-down
inhibition stay on this Alertmanager regardless of observe or Hermes.

Grafana, longer Prometheus retention, detailed application metrics, and
later log search belong on the Proxmox observability guest
(`herickmotta.homelab.observability`). Losing Proxmox can therefore make
Grafana temporarily unavailable, but it does not remove independent
detection or notification. Do not run Grafana on Sentinel.

## Failure behavior

| Failure | Remaining evidence and action |
| --- | --- |
| One VM or service fails | Sentinel probes and the PVE API identify the scope; Alertmanager notifies. |
| Observability VM fails | Sentinel remains independent and reports it like another critical endpoint. |
| Proxmox fails | Sentinel retains its pre-failure probes and alerts without producing a VM alert storm. |
| Sentinel fails or the site loses power/Internet | An external missed heartbeat is the only reliable off-site signal. |
| Model provider or Hermes fails | Raw Alertmanager notifications and all household services continue. |
