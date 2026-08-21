# AGENTS.md

## Purpose

This is the **public** repository for the versioned homelab implementation.

The project is both:

* a functional infrastructure project;
* a learning/portfolio project focused on production-relevant engineering practices.

The private `homelab-live` repository is a thin deployment binding. It pins a
reviewed commit from this repository and supplies site-specific configuration,
encrypted secrets, state backend configuration, and the apply workflow.

The boundary and release choreography are
[docs/public-private-separation.md](docs/public-private-separation.md).

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
* tests;
* CI configuration;
* public architecture documentation.

This repository must NOT contain:

* real private IP addresses;
* internal hostnames;
* credentials or secrets;
* private network topology;
* environment-specific identifiers;
* OpenTofu state;
* configuration that only makes sense for the private deployment.

The private `homelab-live` repository consumes components from this repository.

Do not introduce dependencies from this repository to `homelab-live`.

## Public/private implementation rules

* Implementation belongs here; site binding belongs in `homelab-live`.
* Do not copy a public role, module, template, or Compose file into
  `homelab-live`. Add a typed input here when a real site variation is needed.
* Keep secure, tested defaults public. Make values configurable because they
  vary by site, not merely because they can be made configurable.
* Public examples use reserved domains, documentation addresses, fake keys,
  and fictional hardware identifiers.
* Treat module variables and Ansible role argument specifications as public
  APIs. Preserve compatibility within a release series and document breaking
  changes.
* Release OpenTofu and Ansible content from the same commit. The live
  repository pins that immutable commit in both dependency declarations.
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
needed by the live site or the reference environment.

## Validation

Where applicable, run:

* `tofu fmt -check`
* `tofu validate`
* `ansible-lint`
* YAML/shell linting
* relevant tests

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
