# herickmotta.homelab

Public Ansible collection for the homelab implementation.

Roles:

- `herickmotta.homelab.guest_base`: Ubuntu guest baseline with Docker,
  Compose, and qemu-guest-agent.
- `herickmotta.homelab.network_plane`: AdGuard Home, Caddy DNS-01, and
  Tailscale subnet routing on a dedicated guest. Caddy routes are a typed
  hostname-to-upstream list; AdGuard remains the default route.
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
- `herickmotta.homelab.proxmox_host_storage`: non-destructive ZFS assertions
  on a Proxmox host. It validates declared pools and serials, configures
  smartd and packaged ZED, and enables OpenZFS monthly scrub timers. It never
  creates or repairs pools.
- `herickmotta.homelab.nas_server`: VirtioFS mounts and SMB3 shares on a
  replaceable NAS VM. Guest access and SMB1 stay disabled. The household
  account uses a fixed UID/GID, and the role writes an SMB probe to each
  share.
- `herickmotta.homelab.netdata_agent`: reusable Netdata Agent install with
  file-managed collectors and a small `health.d` policy. Apply it to the
  hypervisor and to guests that should be observed. The dashboard is not the
  control plane.
- `herickmotta.homelab.sentinel_base`: converge a minimal x86_64 Ubuntu
  24.04 or 26.04 server into the independent Sentinel baseline. It creates
  separate deployment and Hermes identities, hardens SSH, bounds Docker logs,
  and enables a host firewall.
- `herickmotta.homelab.github_actions_runner`: install and register a
  repository-scoped Actions runner as a systemd service. The bootstrap archive
  and checksum are pinned; GitHub's default runner self-update remains enabled
  for service compatibility. First registration takes a short-lived token;
  the token is never persisted in site configuration.
- `herickmotta.homelab.sentinel_monitoring`: run a small Prometheus,
  Alertmanager, Blackbox exporter, node exporter, and optional read-only PVE
  exporter on the Sentinel. Retention is bounded and component endpoints bind
  to loopback by default.
- `herickmotta.homelab.observability`: Prometheus and Grafana on a dedicated
  Proxmox guest. Retention is longer than Sentinel. Grafana binds the guest
  LAN for Caddy; Prometheus and exporters stay on loopback. Optional
  read-only PVE exporter uses a token distinct from Sentinel. Alertmanager
  stays on Sentinel.

Storage architecture, VirtioFS, and monitoring:
[Persistent storage and NAS serving](../docs/persistent-storage.md).
Sentinel recovery and failure boundaries:
[Independent Sentinel host](../docs/sentinel.md).

A private site repository owns inventory, site values, encrypted secrets, and
execution. Call roles by fully qualified collection name. The canonical
repository boundary is
[Public implementation and private deployment](../docs/public-private-separation.md).
