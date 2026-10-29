---
title: Running and monitoring
author_profile: true
layout: single
---

[Documentation index]({{ site.baseurl }}{% link index.md %})

[Installation]({{ site.baseurl }}{% link pages/installation.md %}) · [Configuration]({{ site.baseurl }}{% link pages/configuration.md %}) · [Running and monitoring]({{ site.baseurl }}{% link pages/running.md %})

Run these commands as root on the production host.

## Check the installation

Check the installed version and cron entry:

```sh
/opt/prod/bmdynip/bin/bmdynip --version
cat /etc/cron.d/bmdynip
```

Use the [Web UI runner schedule]({{ site.baseurl }}{% link pages/web-interface.md %}#runner-schedule)
to enable or disable scheduled runs and change the cron expression.
The default, `*/5 * * * *`, runs every five minutes.

## Run immediately

To start the runner manually:

```sh
/opt/prod/bmdynip/bin/bmdynip
```

Both ipify and ifconfig.me must return the same public IPv4 address.
Failed requests, invalid responses, or disagreement prevent DNS changes.

Once submitted, an unchanged public IP and unchanged managed hostname list
produce no output. Overlapping runs are skipped using a file lock.

With no managed hostnames, the runner still records the observed public IPv4
address without changing DNS.

## DNS updates and retries

The runner waits for each DNS command to finish. For each managed hostname, it
deletes all A records at that name, then adds one with the submitted address
if deletion succeeds. Commands run sequentially with a 60-second CLI timeout
and a 65-second process timeout.

The runner saves the IP and hostname list after all commands exit successfully.

The Web UI displays the submitted address and last submission time. Its status
column independently checks DNS on page load and every refresh.
DNS caching can delay visible changes.

A failed or timed-out command causes the runner to exit with a nonzero status
and retain the previous saved state for retry. Failures appear in status messages
and the service log or cron output. GoDaddy authentication must work unattended
for root; an interactive login cannot complete in the runner.

An add failure can leave a hostname without an A record until a retry succeeds.
Updates to multiple hostnames are not atomic.

### Force an update

The saved state is a cache, not a continuous DNS audit. To retry a background
failure at the same public IP, or restore a managed A record that someone
changed manually, remove the saved state:

```sh
rm -f /opt/prod/bmdynip/data/state.json
```

The next scheduled or manual run will submit the DNS updates again.

## Logs

Cron sends output to syslog with the tag `bmdynip`.
On systems using journald, view it with:

```sh
journalctl -t bmdynip
```

For commands launched through the Web UI, check the service log:

```sh
journalctl -u bmdynip-web.service
```
