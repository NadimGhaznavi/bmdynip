---
title: Coding Guidelines
author_profile: true
layout: single
---

[Documentation index]({{ site.baseurl }}{% link index.md %})

These are BMDynIP's development standards. MUST identifies a requirement;
SHOULD identifies a default whose exceptions need a concrete reason.

## Ownership and scope

The project owner is the architect and release manager. The AI assistant is
the lead developer, responsible for implementation, verification, and documentation.

Changes MUST follow the owner's architecture and the requested scope.
Preserve existing behavior unless the task requires changing it.
Do not expand a task into an unrelated refactor.

ANY edits to files outside of the repository MUST be approved by the user.

Git operations and release scripts may be used within the authorized workflow.

## Architecture

- Each component MUST have a clear responsibility and resource owner.
- Transport, domain rules, persistence, background workflows, and presentation
  MUST remain separate.
- Dependencies SHOULD use narrow interfaces or injected callables.
- Construct and connect resources at explicit application entry points.
- Reuse sound distributed patterns where they provide clear ownership or reuse.
- Introduce abstractions and services only for demonstrated requirements.

Where an authoritative model or specification is adopted, implementations MUST
preserve its semantics. Verify inheritance, relationships, and cardinalities
against that source. Do not substitute an ad-hoc schema for the accepted model.

CWM-based work MUST use OMG CWM 1.1 as its authority. CWM is not required for
unrelated application data.

## Project structure

| Location | Responsibility |
| --- | --- |
| `index.md` | Sole documentation root |
| `pages/` | Guides and documentation images |
| `_config.yml` | Jekyll configuration |
| `scripts/` | Maintenance and release tooling |
| `conf/` | Default domain configuration |
| `bmdynip/app/` | Command entry point and application orchestration |
| `bmdynip/constants/` | Project constants |
| `bmdynip/interface/` | Configuration, credentials, public-IP discovery, DNS, and saved-state interfaces |
| `bmdynip/activity/` | Public-IP update workflow |
| `bmdynip/entity/` | DNS record data objects |
| `tests/` | Application, installation, and release verification |
| `CHANGELOG.md` | User-visible changes |

`DBMDynIP.VERSION` MUST remain a literal string in
`bmdynip/constants/DBMDynIP.py`.

The shared theme owns site presentation. Local overrides SHOULD be added only
for a specific requirement.

## Configuration and external interfaces

- `Configuration` MUST validate domain configuration at the boundary
  and return the validated domain to internal callers.
- `Credentials` MUST own token loading and root ownership and permission checks.
  Tokens MUST NOT appear in logs or command arguments.
- `PublicIpService` MUST validate public IPv4 responses and require agreement
  between the configured discovery services.
- `GoDaddyCli` MUST own subprocess calls and validation of DNS operation results.
- Network and subprocess operations MUST have explicit timeouts.
- Keep project endpoints, installation paths, and the cron schedule in `DBMDynIP`.

Internal callers MUST trust validated objects and established contracts.
Expected external failures MUST produce a clear error and a failing exit status.
Programming errors MUST surface rather than being hidden by broad exception handlers.

## Saved state and installation

`IpState` MUST own saved-state access and process locking. Skip overlapping runs
and release locks reliably. Save state only after all configured DNS updates
succeed; failed updates MUST preserve the previous successful state so the next
run retries the configured records.

Installation MUST include all application modules in the executable archive.
Reinstallation and uninstallation MUST preserve configuration, saved data,
and credentials. Configuration and credential files MUST have restrictive
permissions. The application and cron job MUST run as root.

## Documentation

Public documentation MUST be short, direct, and task-focused.

Include only what readers need to install, use, or develop the software.
Omit implementation narration, repeated explanations, development history,
and speculative features. Put detailed contracts in one reference and link to it.

- Keep `README.md` to a brief overview and website link.
- Every page MUST be reachable from `index.md`.
- Give each page one purpose and YAML front matter with a `title` key.
- Use `site.baseurl` and Jekyll's `link` tag for internal page links.
- Use fenced examples and tables where useful.
- Document verified behavior and commands.
- Credentials and secrets MUST NOT appear in the public site.

## Verification and review

Run checks appropriate to the change. Update-workflow changes MUST cover initial
updates, unchanged addresses, configuration changes, partial DNS failures,
invalid discovery responses, and overlapping runs. Installer changes MUST verify
the executable archive, cron job, permissions, and preservation of existing files.
Release changes MUST use disposable repositories and a local remote.

Review architectural changes with `$review-architecture` when available.
These standards apply whether or not the skill is installed.

Reviews MUST identify concrete evidence, consequences, and bounded corrections.
Trace a normal operation and a relevant failure path. Distinguish defects from
preferences; passing tests alone does not establish architectural correctness.

Check documentation front matter, link targets, and navigation.
Inspect rendered output when presentation changes.

GitHub Pages builds the site. Do not add a Gemfile, require local Jekyll builds,
or commit generated site output. Report checks that could not be run.

## Changelog and releases

Record meaningful changes under `## [Unreleased]` in `CHANGELOG.md`.
Keep entries focused on user-visible outcomes.

Release tooling MUST update `DBMDynIP.VERSION` and assign the changelog version
and timestamp. Verify project paths and release messages before running
`scripts/new-release.sh`.
