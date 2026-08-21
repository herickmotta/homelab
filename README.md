# homelab-infra

Public reusable infrastructure for a homelab. This repository is both a working project and a learning/portfolio artifact.

The private [homelab-live](https://github.com/herickmotta/homelab-live) repository consumes components from here. This repository must not depend on `homelab-live`.

## Current status

First reusable OpenTofu module: `modules/proxmox-vm` (Proxmox cloud-init VM via bpg/proxmox 0.111.1). Dummy usage is in `examples/proxmox-vm`. Tagged `v0.1.0`. No Ansible roles yet.

QEMU guest agent: `modules/proxmox-vm` sets `agent.enabled = true` and expects cloud-init vendor-data at `local:snippets/qemu-guest-agent.yaml` (copy [`modules/proxmox-vm/cloud-init/vendor-data.yaml`](modules/proxmox-vm/cloud-init/vendor-data.yaml) onto the node). Snippet upload via the provider needs SSH to Proxmox; this module stays API-only, so that file is a one-time host step. Enable **Snippets** on datastore `local` first.

## What belongs here

Reusable OpenTofu modules, Ansible roles, generic cloud-init, examples with dummy values, tests, CI, and public architecture notes.

This repository must **not** contain:

- real private IP addresses or internal hostnames
- credentials, secrets, or private keys
- private network topology or environment-specific identifiers
- OpenTofu state

## Intended layout

```
modules/     reusable OpenTofu modules (first module lands here)
examples/    dummy-value usage examples only; no live IPs or hostnames
roles/       reusable Ansible roles, when OS configuration is needed
playbooks/   reusable playbooks, when needed
.github/     CI workflows
```

Do not add empty trees in advance. The stack is OpenTofu → Proxmox → cloud-init → Ansible → Docker Compose. Kubernetes is deferred until there is a concrete reason to introduce it.

## Consuming modules from homelab-live

Pin a git tag (or commit) when a module exists. Do not copy modules into the live repository.

```hcl
module "example" {
  source = "git::https://github.com/herickmotta/homelab-infra.git//modules/<name>?ref=v0.1.0"
}
```

## Validation

CI runs OpenTofu `fmt`/`validate` and `ansible-lint` only when matching files exist. Until then the workflow stays green.

Locally, when those files exist:

- `tofu fmt -check`
- `tofu validate`
- `ansible-lint`

See [AGENTS.md](AGENTS.md) for repository boundaries, workflow, and safety rules.
