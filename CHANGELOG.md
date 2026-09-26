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
