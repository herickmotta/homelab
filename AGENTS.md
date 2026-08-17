# AGENTS.md

## Purpose

This is the **public** repository for reusable homelab infrastructure code.

The project is both:

* a functional infrastructure project;
* a learning/portfolio project focused on production-relevant engineering practices.

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
* reusable Ansible roles;
* generic cloud-init configuration;
* examples;
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

Do not create speculative modules or directories before they are needed.

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
