---
title: Dynamic DNS Service
author_profile: true
layout: single
---

![BMDynIP Logo](/pages/images/bmdynip-logo.png)

**BMDynIP** is a dynamic DNS service for people who:

- Have a dynamic public Internet IP address.
- Have a domain registered with GoDaddy, such as **osoyalce.com**.
- Want to host one or more Internet services.

BMDynIP uses the [GoDaddy CLI tool](https://github.com/godaddy/cli) to manage DNS A records for one or more hostnames, such as `www.osoyalce.com`. It keeps those records pointed at your current public IP address.

The service:

- Runs as a Linux service.
- Provides a web interface for configuring the service and managing hostnames.
- Detects your public IP address and checks it periodically.
- Updates your GoDaddy DNS records when your IP address changes.
- Stores state and history in MariaDB.

---

## User Guides

- [Architecture]({{ site.baseurl }}{% link pages/architecture.md %})
- [Installation]({{ site.baseurl }}{% link pages/installation.md %})
  - [Root GoDaddy authentication]({{ site.baseurl }}{% link pages/root-authentication.md %})
- [Configuration]({{ site.baseurl }}{% link pages/configuration.md %})
- [Uninstall]({{ site.baseurl }}{% link pages/uninstall.md %})
- [Web interface]({{ site.baseurl }}{% link pages/web-interface.md %})
- [Running and monitoring]({{ site.baseurl }}{% link pages/running.md %})

---

## Developer Guidelines

- [Coding guidelines]({{ site.baseurl }}{% link pages/coding-guidelines.md %})
- [Database schema]({{ site.baseurl }}{% link pages/database-schema.md %})