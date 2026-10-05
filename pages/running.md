---
title: Running and monitoring
author_profile: true
layout: single
---

[Documentation index]({{ site.baseurl }}{% link index.md %})

[Installation]({{ site.baseurl }}{% link pages/installation.md %}) · [Configuration]({{ site.baseurl }}{% link pages/configuration.md %}) · [Running and monitoring]({{ site.baseurl }}{% link pages/running.md %})

Run these commands as root on the production host.

## Run and monitor

Check the installed version and cron entry:

```sh
/opt/prod/bmdynip/bin/bmdynip --version
cat /etc/cron.d/bmdynip
```

Use the [Web UI runner schedule]({{ site.baseurl }}{% link pages/web-interface.md %}#runner-schedule)
to enable or disable scheduled runs and change the cron expression. The default
is `*/5 * * * *` (every five minutes).

To run immediately as root:

```sh
/opt/prod/bmdynip/bin/bmdynip
```

Both ipify and ifconfig.me must return the same public IPv4 address. Failed
requests, invalid responses, or disagreement prevent DNS changes. Unchanged
addresses and managed names produce no output once submitted.
Overlapping runs are skipped using a file lock. With no managed names, the runner
still records the observed public IPv4 address without changing DNS.

DNS commands run in detached processes. Each deletes the matching A record and
then adds the submitted address if deletion succeeds. The runner saves the IP
and record names after launching all commands, without waiting for completion
or parsing their output. The Web UI shows the submitted address, a **Submitted**
status, and the last submission time; these do not confirm the provider's result.

A launch failure exits nonzero and preserves the previous saved state for retry.
Errors from detached commands go to the service log or cron output. To retry a
background failure at the same address, remove the saved state as described below.
An add failure can leave the name without an A record until a retry succeeds.
Multiple names are not updated atomically.

Cron sends output to syslog with the tag `bmdynip`. On systems using journald:

```sh
journalctl -t bmdynip
```

The saved state is a cache, not a continuous DNS audit. If someone manually
changes a managed A record, remove `/opt/prod/bmdynip/data/state.json` to force
the next update.
