# Persistent storage and NAS serving

Public implementation for host-owned ZFS monitoring and a replaceable NAS VM.
Site-specific pool names, disk serials, addresses, and credentials belong in
the private deployment repository.

## Ownership

ZFS pools stay on the Proxmox host. Guests never receive HBA passthrough, raw
disks, or nested ZFS. Guest OS disks remain on NVMe `local-lvm`. HDD datasets
hold data only.

The serving layer is an ordinary Ubuntu VM. It mounts host directories through
Proxmox VirtioFS and exports them with SMB3. The VM is replaceable. Destroying
it must not destroy the pools.

## Data path

```text
host ZFS dataset
  -> explicit POSIX mountpoint
  -> Proxmox directory mapping
  -> VirtioFS device
  -> guest mount
  -> SMB3 share
```

Do not use 9p. Do not add an emergency NFS export from the hypervisor as a
workaround. NFSv4 may be added later for Linux clients; it is not enabled by
this collection.

## OpenTofu

`modules/proxmox-vm` accepts:

- `virtiofs`: zero or more directory mapping attachments. The default is no
  devices, so existing guests are unchanged.
- `startup`: optional start/shutdown order. Null leaves the host setting
  unmanaged.

`modules/proxmox-guests` composes those inputs through the stable guest map
and optionally manages `proxmox_hardware_mapping_dir` resources. Mapping
identifiers must match `virtiofs[].mapping`.

bpg/proxmox 0.111.1 can attach VirtioFS devices and directory mappings. It
does not expose a hypervisor read-only flag. Enforce read-only in the guest
mount and Samba share when needed.

Directory mapping create/update needs Proxmox `Mapping.Modify` in addition to
`Mapping.Use`. If the provider cannot manage a mapping, keep VM-side VirtioFS
support and create the mapping with idempotent `pvesh` in the private
bootstrap documentation.

## Ansible

`herickmotta.homelab.proxmox_host_storage` is non-destructive. It validates
declared serials, pools, datasets, and mountpoints; configures smartd, ZED,
and systemd scrub/health timers; and exposes:

```bash
homelab-storage-health
homelab-storage-health --json
homelab-storage-health --prometheus
homelab-storage-health --test-warning
homelab-storage-mail-test ADDRESS
```

It never creates, destroys, imports, replaces, or clears ZFS topology.

`herickmotta.homelab.nas_server` mounts declared VirtioFS filesystems,
configures SMB3 without guest access or SMB1, and exposes:

```bash
homelab-nas-health
homelab-nas-health --json
homelab-nas-health --prometheus
homelab-nas-health --test-warning
```

Exit codes: `0` healthy, `1` warning/degraded but available, `2` critical or
configuration mismatch. Prometheus textfiles are written atomically. Logs go
to journald. Credentials are not included in JSON, metrics, or logs.

## Out of scope here

- Creating or destroying ZFS pools
- Nextcloud, Frigate, Jellyfin, or another application workload
- NFS
- A backup product
- Prometheus, Grafana, Loki, Alertmanager, or another central monitoring stack
- LDAP, Active Directory, quotas, or a web file manager
