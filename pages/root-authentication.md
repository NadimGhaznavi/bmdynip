---
title: Root GoDaddy authentication
author_profile: true
layout: single
---

[Documentation index]({{ site.baseurl }}{% link index.md %})

BMDynIP's Web UI and cron runner run as root and invoke
`/opt/prod/godaddy-cli/gddy` directly for production DNS updates. Authentication
belongs to `gddy`, using root's configured credentials and the inherited environment.

## Verify authentication

As root, run a read-only query for your configured domain:

```sh
/opt/prod/godaddy-cli/gddy dns list osoyalce.com --type A --env prod --output json --timeout 20s
```

A successful response confirms read access; an empty record list is valid.
Configure root's `gddy` authentication to permit DNS reads and updates. To
configure an interactive login, run as root:

```sh
/opt/prod/godaddy-cli/gddy auth login --env prod --scope domains.dns:update
```

Use `gddy`'s authentication commands to manage its credentials. If you use
environment credentials, make them available to both the Web UI service and cron
runner; variables exported in an interactive shell do not automatically reach them.
Keep tokens out of command arguments, cron entries, service logs, and the repository.

BMDynIP does not read `$HOME/.godaddy-cli` or `/etc/bmdynip/auto.env`. Existing
copies are preserved during installation, upgrades, and uninstallation.
