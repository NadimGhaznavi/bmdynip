---
title: Uninstall
author_profile: true
layout: single
---

[Documentation index]({% link index.md %})

From your BMDynIP checkout, run as root on the production host:

```sh
./scripts/uninstall.sh
```

This removes `/opt/prod/bmdynip/bin/bmdynip` and `/etc/cron.d/bmdynip`.
Configuration, saved data, and `/etc/bmdynip/auto.env` remain for
[reinstallation]({% link pages/installation.md %}). DNS records are not deleted.
