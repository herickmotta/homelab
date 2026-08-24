# AGENTS.md

## Purpose

This is the **public** repository for the versioned homelab implementation.

The project is both:

* a functional infrastructure project;
* a learning/portfolio project focused on production-relevant engineering
  practices.

Reusable modules, roles, templates, and architecture live here. A **private
site repository** (not this one) pins a reviewed commit and supplies
site-specific configuration, encrypted secrets, state backend configuration,
and the apply workflow.

The boundary and release choreography are
[docs/public-private-separation.md](docs/public-private-separation.md).

Public documentation describes that private-companion pattern. Do not name a
specific private repository, live hostname, or real address here.

## Principles

* Prefer simple, maintainable solutions.
* Prefer widely adopted technologies and patterns.
* Avoid premature abstractions.
* Keep changes small and reviewable.
* Explain important architectural decisions and tradeoffs.
* Optimize for understanding, not maximum AI-generated code.
* Challenge unnecessary complexity.

## Repository Boundary

This repository may contain:

* reusable OpenTofu modules;
* the public Ansible collection and reusable roles;
* Docker Compose and application templates owned by those roles;
* generic cloud-init configuration;
* a complete reference environment with fictional values;
* CI configuration;
* public architecture documentation.

This repository must NOT contain:

* real private IP addresses;
* internal hostnames;
* credentials or secrets;
* private network topology;
* environment-specific identifiers;
* OpenTofu state;
* configuration that only makes sense for one private deployment.

Private site repositories consume components from this repository.

Do not introduce dependencies from this repository to any private site
repository.

## Public/private implementation rules

* Implementation belongs here; site binding belongs in a private site
  repository.
* Do not copy a public role, module, template, or Compose file into a private
  site repository. Add a typed input here when a real site variation is
  needed.
* Keep secure, tested defaults public. Make values configurable because they
  vary by site, not merely because they can be made configurable.
* Public examples use reserved domains, documentation addresses, fake keys,
  and fictional hardware identifiers.
* Treat module variables and Ansible role argument specifications as public
  APIs. Preserve compatibility within a release series and document breaking
  changes.
* Release OpenTofu and Ansible content from the same commit. A site repository
  pins that immutable commit in both dependency declarations.
* A public change cannot trigger a live deployment. Promotion happens only in
  a reviewed private PR that updates the pinned commit and reviews a real plan.

## Infrastructure Responsibilities

* **OpenTofu:** infrastructure provisioning and Proxmox resources.
* **cloud-init:** minimal first-boot bootstrap.
* **Ansible:** operating-system configuration.
* **Docker Compose:** application/service definitions.

Avoid overlapping ownership between these layers.

## Development Workflow

For non-trivial changes:

1. Inspect existing code and documentation.
2. Propose the approach before implementing large changes.
3. Prefer the smallest useful implementation.
4. Implement.
5. Run relevant validation.
6. Review the resulting diff.
7. Update documentation when architectural behavior changes.

Do not create speculative modules, roles, or directories before they are
needed by a real site or the reference environment.

## Validation

Where applicable, run:

* `tofu fmt -check`
* `tofu validate`
* `ansible-lint`
* YAML/shell linting
* `ansible-galaxy collection build` when collection files change

If validation cannot be run, explicitly state why.

## Security

* Never commit plaintext secrets.
* Never commit OpenTofu state.
* Never expose private homelab information in this repository.
* Do not weaken security merely to simplify automation.

## Architecture Changes

For significant architectural changes:

* explain the problem;
* explain the proposed solution;
* mention relevant alternatives;
* explain the tradeoffs.

Do not silently introduce major new technologies.

## Documentation

This repository does not track live site status. Living status belongs in the
private site repository that deploys this implementation.

Read this file every session. Open other docs only for the slice you are
changing.

| File | Owns |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Public contract: purpose, boundary, workflow, this map |
| [README.md](README.md) | What this repository ships, how a site repo consumes it, and the **running-system mermaid** |
| [docs/public-private-separation.md](docs/public-private-separation.md) | Canonical public/private contract and promotion |
| [docs/persistent-storage.md](docs/persistent-storage.md) | Public storage and NAS architecture |
| [ansible/README.md](ansible/README.md) | Collection role index |
| [examples/](examples/) | Fictional site shape |

### Update when you change

| Change | Update |
| --- | --- |
| Boundary, promotion, or public/private rules | this file and `docs/public-private-separation.md` |
| New or removed module, role, or shipped capability | `README.md` (what ships) and `ansible/README.md` if a role changed |
| Guest, GPU/PCI, proxy, camera, or data-path topology | README Architecture mermaid (mandatory) |
| Storage architecture | `docs/persistent-storage.md` plus the README mermaid if the data path changed |
| Typed public API | module variables / role argument specs, examples, and the README that describes them |
| Live leftovers, pins, or household topology | nothing here; that belongs in the private site repository |

Do not copy private proven-slice narratives, leftover lists, or a specific
private repository name into this repository.

### Visual architecture

This file is the shared contract across workstations. Do not put this in
`.cursor/rules`.

A guest, GPU/PCI, proxy, camera, or data-path change is not documented until
the README Architecture mermaid shows it. A text-only README update is not
enough. If the diagram would still be true without the new path, it is stale.
