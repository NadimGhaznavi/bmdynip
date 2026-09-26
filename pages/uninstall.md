---
title: Uninstall
author_profile: true
layout: single
---

[Documentation index]({% link index.md %})

From your MyDynIP checkout, run as root on the production host:

```sh
./scripts/uninstall.sh
```

This removes `/opt/prod/mydynip/bin/mydynip` and `/etc/cron.d/mydynip`.
Configuration, saved data, and `/etc/mydynip/auto.env` remain for
[reinstallation]({% link pages/installation.md %}). DNS records are not deleted.
