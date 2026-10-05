---
title: Uninstall
author_profile: true
layout: single
---

[Documentation index]({{ site.baseurl }}{% link index.md %})

From your BMDynIP checkout, run as root on the production host:

```sh
./scripts/uninstall.sh
```

This stops and disables `bmdynip-web.service`, removes its unit file,
both executables in `/opt/prod/bmdynip/bin/`, and `/etc/cron.d/bmdynip`.
Configuration, saved data, MariaDB records, and both credential files in
`/etc/bmdynip/` remain for
[reinstallation]({{ site.baseurl }}{% link pages/installation.md %}). DNS records are not deleted.
