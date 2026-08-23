# Persistent storage and NAS serving

Public implementation for host-owned ZFS and a replaceable NAS VM.
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
- `machine` and `hostpci`: optional QEMU machine type and PCI resource
  mapping attachments. Defaults omit both, so existing guests stay on `pc`
  with no host PCI devices. `hostpci` uses Proxmox mapping names only, not
  raw PCI addresses.

`modules/proxmox-guests` composes those inputs through the stable guest map
and optionally manages `proxmox_hardware_mapping_dir` and
`proxmox_hardware_mapping_pci` resources. Directory mapping identifiers must
match `virtiofs[].mapping`. PCI mapping identifiers must match
`hostpci[].mapping`.

bpg/proxmox 0.111.1 can attach VirtioFS devices and directory mappings. It
does not expose a hypervisor read-only flag. Enforce read-only in the guest
mount and Samba share when needed. `expose_acl: true` also turns on
`expose_xattr`; Proxmox rejects ACL shares when xattr is sent as false.

Directory mapping create/update needs Proxmox `Mapping.Modify` in addition to
`Mapping.Use`. If the provider cannot manage a mapping, keep VM-side VirtioFS
support and create the mapping with idempotent `pvesh` in the private
bootstrap documentation.

## Ansible

`herickmotta.homelab.proxmox_host_storage` is non-destructive. It asserts
declared serials, pool topology, datasets, and mountpoints; configures smartd
short/long tests; edits the packaged ZED `zed.rc` with `lineinfile` only;
enables OpenZFS `zfs-scrub-monthly@<pool>.timer`; and sets a stable numeric
owner on NAS-exported datasets. It never creates, destroys, imports, replaces,
or clears ZFS topology.

`herickmotta.homelab.nas_server` mounts declared VirtioFS filesystems, creates
the household Samba account with a fixed UID/GID, configures SMB3 without
guest access or SMB1, and writes a probe file to each share to confirm the
file appears on the matching guest path only.

`herickmotta.homelab.netdata_agent` is the reusable metrics and alert agent
for the lab, not a NAS-only sidecar. Apply it to the Proxmox host and to
guests that should be observed. It installs the official Netdata Agent and
manages collectors and `health.d` rules as files. The local dashboard is a
view, not the control plane, and Netdata Cloud is left disabled. Collectors
used here:

- Proxmox host/VM/systemd metrics from the agent on the hypervisor
- `zfspool` and `smartctl` on the hypervisor
- `samba` on the NAS VM (`smbd profiling level = count`)
- agent-dispatched email when SMTP is configured
- Prometheus-compatible `/api/v1/allmetrics?format=prometheus` for a later
  central stack

Custom `health.d` rules cover pool not online, SMART failed and critical
sector counters, inactive `smbd`/smartd/ZED or VirtioFS mount units, and
free-space thresholds on declared data mounts.

Runtime health belongs to Netdata, ZED, and smartd. Recovery and debug stay
on standard commands: `zpool status`, `smartctl -j`, `systemctl`, and
`smbstatus`.

## Stable data owner

VirtioFS maps UIDs 1:1. The household Samba account must keep the same UID
and GID across NAS rebuilds so files on host datasets stay writable. Declare
those IDs in site configuration (10000/10000 in the example), create the
guest user with them, and `chown` NAS-exported host mountpoints to the same
numbers. Do not let the guest allocate a dynamic system UID.

## Disposable camera footage

Frigate recordings belong on a disposable host dataset mapped into the
application guest with VirtioFS. That path is not an SMB share. The NAS role
still rejects `volatile` in Samba mounts. Config, SQLite, and detector models
stay on the guest OS disk and are reproducible from git except event history.

## Out of scope here

- Creating or destroying ZFS pools
- Nextcloud, Jellyfin, or another application workload besides Frigate
  footage on a disposable VirtioFS dataset
- Treating Frigate recordings, event history, or detector models as backed up
- NFS
- A backup product
- Prometheus, Grafana, Loki, Alertmanager, or another central monitoring stack
- LDAP, Active Directory, quotas, or a web file manager
