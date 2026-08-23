# herickmotta.homelab

Public Ansible collection for the homelab implementation.

Roles:

- `herickmotta.homelab.guest_base`: Ubuntu guest baseline with Docker,
  Compose, and qemu-guest-agent.
- `herickmotta.homelab.network_plane`: AdGuard Home, Caddy DNS-01, and
  Tailscale subnet routing on a dedicated guest.
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

Storage architecture, VirtioFS, and monitoring:
[Persistent storage and NAS serving](../docs/persistent-storage.md).

The calling repository owns inventory, site values, encrypted secrets, and
execution. Call roles by fully qualified collection name. The canonical
repository boundary is
[Public implementation and private deployment](../docs/public-private-separation.md).
