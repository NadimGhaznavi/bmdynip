---
title: Running and monitoring
author_profile: true
layout: single
---

[Documentation index]({% link index.md %})

[Installation]({% link pages/installation.md %}) · [Configuration]({% link pages/configuration.md %}) · [Running and monitoring]({% link pages/running.md %})

Run these commands as root on the production host.

## Run and monitor

Check the installed version and cron entry:

```sh
/opt/prod/mydynip/bin/mydynip --version
cat /etc/cron.d/mydynip
```

To run immediately as root:

```sh
/opt/prod/mydynip/bin/mydynip
```

Both ipify and ifconfig.me must return the same public IPv4 address. Failed
requests, invalid responses, or disagreement prevent DNS changes. Unchanged
addresses produce no output. Overlapping runs are skipped using a file lock.

The saved IP and record names are written only after all DNS commands succeed.
Failures exit nonzero and are retried on the next cron run. Delete and add are
separate operations: an add failure can leave the name without an A record
until a retry succeeds. Multiple names are not updated atomically.

Cron sends output to syslog with the tag `mydynip`. On systems using journald:

```sh
journalctl -t mydynip
```

The saved state is a cache, not a continuous DNS audit. If someone manually
changes a managed A record, remove `/opt/prod/mydynip/data/state.json` to force
the next update.

