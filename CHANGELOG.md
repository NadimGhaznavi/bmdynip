---
title: Changelog
author_profile: true
layout: single
permalink: /CHANGELOG/
---

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Fixed

- Show the sanitized DNS failure reason in status messages, including GoDaddy
  authentication rejection and instructions to refresh the configured PAT.

## [1.6.0] - 2026-10-04 @ 23:05

### Added

- Show hostname addition and runner process steps in the Web UI status messages,
  including discovery, DNS updates, completion, and failures with module names as sources.

## [1.5.0] - 2026-10-04 @ 22:41

### Added

- Start the runner immediately after adding a hostname in the Web UI, with
  clear feedback if the name is saved but the runner cannot launch.

## [1.4.1] - 2026-10-04 @ 22:16

### Fixed

- Refresh installed GoDaddy credentials from `$HOME/.godaddy-cli` during
  installation and upgrades; normal runtime continues to use `/etc/bmdynip/auto.env`.

## [1.4.0] - 2026-10-04 @ 22:02

### Added

- Import existing JSON hostnames into MariaDB once during installation or upgrade,
  preserving later Web UI changes and the original configuration file.
- Connect the Web UI to persistent hostname management, live system status,
  and database-backed DNS change history, with automatic status refresh.
- Provision the local MariaDB database and account, save protected database
  credentials, and apply the schema during installation and upgrades.
- Retain existing database credentials and records when reapplying the schema.

### Fixed

- Wait for database-backed Web UI readiness during installation, upgrades, and
  restarts; report unavailable credentials, schema, or database instead of success.
- Update running and uninstall guidance for database-backed hostname management,
  live status, and retained database records.

## [1.3.0] - 2026-10-04 @ 20:37

### Added

- Expose the runner cron schedule in the Web UI with an enabled checkbox,
  cron expression, and Update button; default to every five minutes.

### Fixed

- Preserve custom and disabled runner schedules during installation and upgrades.

## [1.2.2] - 2026-10-04 @ 20:18

### Fixed

- Declare PyMySQL in `requirements.txt` and bundle it in both executable
  archives during installation and upgrades.

## [1.2.1] - 2026-10-04 @ 20:09

### Fixed

- Stop the Web UI before deploying an upgrade and start it afterward.
- Allow the Web UI time to become active before failing its readiness check.

## [1.2.0] - 2026-10-04 @ 20:02

### Added

- Add `scripts/upgrade.sh` to redeploy BMDynIP and restart the Web UI while
  preserving configuration, saved state, and credentials.

## [1.1.0] - 2026-10-04 @ 19:58

### Added

- Add the MariaDB schema for the CWM WAN connection model, per-record change requests,
  and managed DNS records.

### Fixed

- Show the Web UI listening address in status output instead of the localhost readiness URL.

## [1.0.3] - 2026-10-04 @ 15:05

### Fixed

- Start the Web UI on port 49700 during installation and enable it at boot.
- Restart the Web UI on upgrades and print its status and port after HTTP responds.

### Added

- Add `scripts/restart.sh` to restart the Web UI and report its status and port.

## [1.0.2] - 2026-10-04 @ 10:28

### Fixed

- Create the protected GoDaddy credential file during first installation using
  root's `/root/.godaddy-cli` PAT, `GDDY_PAT`, or hidden PAT entry, and preserve
  existing credentials on reinstall.
- Use the saved production PAT for DNS updates even when `GDDY_PAT_PROD` is set.

## [1.0.1] - 2026-10-04 @ 10:17

### Added

- Add a web UI preview on port 49700 with logo-matched colors, system status,
  sample A-record management, and activity messages. Preview changes reset on reload.

### Summary

Rename the project to BMDynIP (Bear & Moose), updating branding, GitHub and
website references, application names, and installation paths consistently.

### Changed

- Rename the Python package to `bmdynip` and the constants class to `DBMDynIP`.
- Use `bmdynip` for the executable, configuration filename, cron job, and syslog tag.
- Update installation and credential paths to `/opt/prod/bmdynip` and `/etc/bmdynip/auto.env`.
- Update documentation, tests, logo filename, and the site address to `bmdynip.osoyalce.com`.
- Identify BM as Bear & Moose and link to `osoyalce.com` from the documentation index.
- Adopt BMGeoIP's development guidance, adapted to BMDynIP's updater, installation, and verification workflows.

## [1.0.0] - 2026-09-26 @ 14:42

### Added

- Document root's GoDaddy PAT setup, the distinction from dan's OAuth login, authentication checks, and token rotation in a dedicated guide.

## [0.2.0] - 2026-09-26 @ 14:20

### Summary

Add the cron-driven public IPv4 updater for configurable hostnames, with root
installation and uninstall scripts that preserve configuration and data.

### Added

- Configure one domain and a hostname list, empty by default; no application hostnames are hardcoded.
- Add public-IP discovery, DNS record entities, and the update activity with GoDaddy CLI and saved-state interfaces.
- Add root installation under `/opt/prod/bmdynip` and a cron job every five minutes.
- Read the root-owned GoDaddy PAT from `/etc/bmdynip/auto.env` with mode `0600`.
- Preserve saved state on DNS failure, skip overlapping runs, and refresh records when configuration changes.
- Document installation, configuration, logging, and uninstall behavior.
- Include production credential setup and installation verification commands in the user guides.
- Add the GoDaddy CLI path as `DBMDynIP.GODADDY_CLI`.
- Add the ipify and ifconfig.me URLs as `DBMDynIP.PUBLIC_IP_URLS`.
- Define the five-minute cron schedule as `DBMDynIP.CRON_SCHEDULE`.

### Changed

- Move configuration and running instructions into separate guides, linked from installation and the documentation index.
- Move uninstall instructions into their own guide.

## [0.1.0] - 2026-09-26 @ 13:35

### Summary

### Added

- Add isolated release-script checks covering publication to a local Git remote and validation failures.
- Copy `scripts/new-release.sh` from R3el.
- Add the project `VERSION` constant, initially `0.0.1`.
- Document the constants naming convention in the coding guidelines.

### Changed

- Validate release and stored versions as Semantic Versions, rejecting duplicate version declarations and numeric prerelease identifiers with leading zeroes.
- Follow Ax3l's constants convention with `DBMDynIP.VERSION` in `DBMDynIP.py`.
- Adapt the release script to read and update the BMDynIP version constant.
- Use Jekyll-generated documentation links and remove links to missing pages inherited from R3el.

### Removed

---
