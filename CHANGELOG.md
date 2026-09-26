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

### Summary

Add the cron-driven public IPv4 updater for configurable hostnames, with root
installation and uninstall scripts that preserve configuration and data.

### Added

- Configure one domain and a hostname list, empty by default; no application hostnames are hardcoded.
- Add public-IP discovery, DNS record entities, and the update activity with GoDaddy CLI and saved-state interfaces.
- Add root installation under `/opt/prod/mydynip` and a cron job every five minutes.
- Read the root-owned GoDaddy PAT from `/etc/mydynip/auto.env` with mode `0600`.
- Preserve saved state on DNS failure, skip overlapping runs, and refresh records when configuration changes.
- Document installation, configuration, logging, and uninstall behavior.
- Include production credential setup and installation verification commands in the user guides.
- Add the GoDaddy CLI path as `DMyDynIP.GODADDY_CLI`.
- Add the ipify and ifconfig.me URLs as `DMyDynIP.PUBLIC_IP_URLS`.
- Define the five-minute cron schedule as `DMyDynIP.CRON_SCHEDULE`.

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
- Follow Ax3l's constants convention with `DMyDynIP.VERSION` in `DMyDynIP.py`.
- Adapt the release script to read and update the MyDynIP version constant.
- Use Jekyll-generated documentation links and remove links to missing pages inherited from R3el.

### Removed

---
