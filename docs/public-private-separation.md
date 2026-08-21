# Public implementation and private deployment

## Decision

The homelab is split across two repositories with a dependency in one
direction:

```text
homelab (public, versioned implementation)
        |
        | pinned full commit SHA
        v
homelab-live (private, site binding and deployment authority)
```

`homelab` explains and implements how the system works. `homelab-live`
declares where that implementation runs. The public repository never reads,
imports, or triggers the private repository.

This boundary makes the complete engineering implementation reviewable as a
portfolio artifact without publishing the live network, hardware mappings,
credentials, state, or a LAN-connected deployment runner.

## Public repository responsibilities

The public repository owns:

* reusable and composition-level OpenTofu modules;
* the `herickmotta.homelab` Ansible collection;
* Docker Compose, Caddy, AdGuard, and other application templates rendered by
  collection roles;
* safe and opinionated defaults, including pinned application versions;
* typed module variables and role argument specifications;
* fictional reference configuration and examples;
* architecture decisions, failure modes, recovery guidance, and public build
  notes;
* validation that requires no live credentials or network access.

Public code must not contain real IP addresses, internal hostnames, personal
domains, VM or VLAN IDs, SSH identities, disk serials, bucket names, secrets,
state, raw plans, or deployment logs.

## Private repository responsibilities

The private repository owns:

* one canonical `site.yaml` containing real topology and non-secret site
  values;
* SOPS-encrypted production credentials and the public SOPS recipient;
* the OpenTofu backend and provider binding;
* a thin OpenTofu root that passes `site.yaml` values into public modules;
* a thin Ansible entrypoint that builds inventory from `site.yaml` and invokes
  public roles by fully qualified collection name;
* immutable public dependency pins;
* the self-hosted apply workflow, real plans, apply logs, and operational
  verification.

The private repository must not carry modified copies of public modules,
roles, templates, or Compose files. A site-specific need becomes a typed public
input when it is safe and generally meaningful. A genuinely private one-off
operation stays explicit in the private entrypoint and is documented as an
exception.

## Configuration layers

There are exactly three intended configuration layers:

1. **Public defaults** — secure, tested opinions and pinned software versions.
2. **Private site configuration** — addresses, names, sizing, placement,
   device mappings, and capability selection in `site.yaml`.
3. **Private secrets** — credentials and password material decrypted only for
   an authorized private plan or apply.

Avoid ad hoc command-line variables, copied templates, Git merge overlays, and
untracked Compose overrides. They create a fourth source of truth and make an
upgrade impossible to reproduce.

Configuration should be broad where installations legitimately differ and
opinionated where the implementation has a safe default. Do not expose every
internal task or Compose field as an input. Add an input after a concrete site
variation exists and validate it at the module or role boundary.

## Stable identities and destructive behavior

OpenTofu `for_each` keys are stable resource identities. Use logical keys such
as `network_plane` or `media`, not a hostname, IP address, or display label.
Changing a key is a state migration and requires an explicit `moved` block or a
reviewed state operation. Removing a key requests destruction; an `enabled`
flag is not a harmless feature toggle.

Persistent data must not depend on a replaceable guest OS disk. Storage
modules and roles must document lifecycle, backup, and migration behavior
before they are promoted to the live site.

## Release and promotion workflow

1. Discuss and implement a capability in a public PR.
2. Validate OpenTofu modules, the Ansible collection, rendered configuration,
   and fictional examples without live access.
3. Merge and tag the public release. Record the full commit SHA.
4. Open a private PR that changes both the OpenTofu source and Ansible
   collection requirement to that same SHA.
5. Validate the private `site.yaml`, initialize against the real backend, and
   review a real OpenTofu plan.
6. Merge the private PR to apply on the private self-hosted runner.
7. Publish a sanitized outcome or build note publicly when useful. Never copy
   raw plans or runner logs.

Public pull requests and tags do not dispatch a private deployment. Automated
dependency tools may propose a private pin update, but promotion still requires
the private plan and review.

## Compatibility policy

OpenTofu modules and the Ansible collection are released from the same commit.
The private repository pins that commit in both places. A release must document
new required inputs, changed defaults, replacements, and any state migration.

Prefer backward-compatible optional inputs with explicit defaults. Breaking
module addresses, stable keys, role variables, paths that hold data, and
application configuration require an upgrade note and a live plan before
promotion.

## Future component checklist

For NAS, Frigate, Nextcloud, Jellyfin, or another component:

1. Decide the capability and data lifecycle first.
2. Put provisioning and reusable configuration in the public repository.
3. Put real placement, addresses, devices, datasets, and secrets in the
   private `site.yaml` or SOPS files.
4. Add fictional reference values and public validation.
5. Pin and exercise the public commit through a private PR.
6. Keep household operation independent of the public repository and of any
   AI system after deployment.
