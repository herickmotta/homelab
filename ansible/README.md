# herickmotta.homelab

Public Ansible collection for the homelab implementation.

Roles:

- `herickmotta.homelab.guest_base`: Ubuntu guest baseline with Docker,
  Compose, qemu-guest-agent, and growpart so a later `disk_gb` increase
  expands the root filesystem. Apply does not wait for first-boot SSH;
  OpenTofu and a retry cover a brand-new guest.
- `herickmotta.homelab.network_plane`: AdGuard Home, Caddy DNS-01, and
  Tailscale subnet routing on a dedicated guest. Caddy routes are a typed
  hostname-to-upstream list; AdGuard remains the default route. Compose
  rebuilds only when templates change or the project is not running.
- `herickmotta.homelab.application_runtime`: VirtioFS mounts on the shared
  application VM, including disposable datasets. Optional assert that the
  Intel render node exists after iGPU passthrough.
- `herickmotta.homelab.frigate`: pinned Frigate Compose project with
  OpenVINO, authenticated port 8971 only, and optional generic YOLOv9s-320.
  GPU sites can set `frigate_gpu_hw_decode` for VAAPI HEVC decode before the
  CPU crop; encode stays `h264_vaapi`. Optional `frigate_classifications` emits
  Frigate 0.17 state models; copy crops from the UI, do not invent them.
  Optional MQTT and loopback-only port 5000 support Home Assistant on the same
  guest. Export the ONNX on a workstation with
  [`scripts/export-yolov9-s-320.sh`](../scripts/export-yolov9-s-320.sh); do not
  commit the binary.
- `herickmotta.homelab.mqtt_broker`: Eclipse Mosquitto published on
  `127.0.0.1` only. Frigate joins the named Docker network; Home Assistant
  (host network) uses localhost.
- `herickmotta.homelab.homeassistant`: pinned Home Assistant Container with
  host networking and git-owned `configuration.yaml` (`http` trusted proxies).
  `.storage` stays on disk. MQTT broker settings are pasted in the UI from
  the role env file.
- `herickmotta.homelab.proxmox_host_power`: persistent Linux CPU power
  policy and passive power/thermal telemetry tools for a Proxmox host. The
  policy is reapplied by `systemd-tmpfiles` during boot and each Ansible run;
  no custom helper or service is installed. The role does not change BIOS
  settings or run PowerTOP auto-tuning.
- `herickmotta.homelab.proxmox_host_storage`: configure smartd, packaged
  ZED, and OpenZFS monthly scrub timers. It never creates or repairs pools.
  Live serial/topology inspection is `--tags proof`, not the default apply.
- `herickmotta.homelab.nas_server`: VirtioFS mounts and SMB3 shares on a
  replaceable NAS VM. Guest access and SMB1 stay disabled. The household
  account uses a fixed UID/GID. Optional `nas_server_smb_integration_test`
  writes an SMB probe to each share; it is off by default.
- `herickmotta.homelab.host_metrics`: pinned `node_exporter` as a systemd
  unit on guests and the hypervisor. Optional `smartctl_exporter` and
  `zfs_exporter` on the hypervisor. Listen on a site IPv4, not loopback.
  Optional textfile probes publish loopback TCP and allowlisted Compose
  container state without exposing the Docker socket to other roles.
- `herickmotta.homelab.log_shipper`: pinned Grafana Alloy as a systemd
  unit. It pushes selected journal units (info and above, not debug) and
  optional Docker container logs to Loki. Every host also emits a bounded
  journal heartbeat so a quiet service cannot hide a broken pipeline.
  Alloy's HTTP endpoint defaults to loopback; a site may bind the host IPv4
  so observe can scrape it.
- `herickmotta.homelab.netdata_agent`: optional Netdata Agent with
  file-managed collectors. `netdata_agent_state: present` installs it;
  `absent` uninstalls it without touching smartd, ZED, or msmtp.
- `herickmotta.homelab.sentinel_base`: converge a minimal x86_64 Ubuntu
  24.04 or 26.04 server into the independent Sentinel baseline. It creates
  separate deployment and Hermes identities, hardens SSH, bounds Docker logs,
  and enables a host firewall. Optional extra TCP ports can be opened from
  management CIDRs so observe can scrape a LAN node exporter. Source-specific
  ingress rules open a single host to a single port, used for observe to
  Sentinel Alertmanager. Site apply does not run this role; the bootstrap
  playbook does.
- `herickmotta.homelab.github_actions_runner`: install and register a
  repository-scoped Actions runner as a systemd service. The bootstrap archive
  and checksum are pinned; GitHub's default runner self-update remains enabled
  for service compatibility. First registration takes a short-lived token;
  the token is never persisted in site configuration. Site apply does not
  re-register the runner.
- `herickmotta.homelab.sentinel_monitoring`: run a small Prometheus,
  Alertmanager, Blackbox exporter, node exporter, and optional read-only PVE
  exporter on the Sentinel. Retention is bounded and component endpoints bind
  to loopback by default. A typed LAN bind can expose Alertmanager to the
  observe guest only. A loopback Hermes webhook input exists but stays empty
  until that role is enabled; email routing remains independent.
  Compose recreates only when templates change or the project is
  not running.
- `herickmotta.homelab.observability`: Prometheus, Grafana, and Loki on a
  dedicated Proxmox guest. Retention is longer than Sentinel. Grafana binds
  the guest LAN for Caddy; Prometheus may bind the guest address for later
  read-only consumers; Loki listens on the guest LAN for Alloy push and is
  not published through Caddy. It scrapes guest node exporters, Alloy, the
  Sentinel host Linux exporter, and hypervisor SMART and ZFS, and sends
  selected alerts to Sentinel Alertmanager. The Homelab overview dashboard
  is the fleet/NAS view, while the Operations / Hermes evidence dashboard is
  the stable read-only evidence contract for alerts, target health, storage,
  services, Frigate, and log freshness. Optional read-only PVE exporter uses a
  token distinct from Sentinel. Alertmanager stays on Sentinel. When expected
  log hosts are set, Prometheus alerts per host if Alloy's `loki.write` send
  counter is stale while Alloy is still scrapeable.
- `herickmotta.homelab.hermes_agent`: pinned official Nous Research Hermes
  Agent container. Disabled and conservative by default. A site may enable
  the full upstream Telegram toolset, memory, skills, curator, cron, and
  delegation inside the container without Docker-socket, host-namespace,
  or RFC1918 egress access. Default inference is ChatGPT Codex OAuth
  (`openai-codex`, Luna) with the normal Hermes runtime. Telegram is one
  allowlisted administrator. There is no dashboard, API server, or
  published port. Optional GitHub App installation tokens can clone
  declared repositories and open pull requests; merge stays with the
  operator. Optional PVEAuditor access is GET-only to the hypervisor API
  on TCP 8006; other RFC1918 destinations stay dropped.

Storage architecture, VirtioFS, and monitoring:
[Persistent storage and NAS serving](../docs/persistent-storage.md).
Sentinel recovery and failure boundaries:
[Independent Sentinel host](../docs/sentinel.md).

A private site repository owns inventory, site values, encrypted secrets, and
execution. Call roles by fully qualified collection name. The canonical
repository boundary is
[Public implementation and private deployment](../docs/public-private-separation.md).
