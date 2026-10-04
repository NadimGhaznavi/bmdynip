---
title: Installation
author_profile: true
layout: single
---

[Documentation index]({{ site.baseurl }}{% link index.md %})

[Installation]({{ site.baseurl }}{% link pages/installation.md %}) · [Configuration]({{ site.baseurl }}{% link pages/configuration.md %}) · [Running and monitoring]({{ site.baseurl }}{% link pages/running.md %})

BMDynIP updates the configured hostnames to this host's public IPv4 address.
It runs as root every five minutes from `/etc/cron.d/bmdynip`.

Run the installation commands below as root on
the production host. Run repository commands from your BMDynIP checkout.

## Install

The host needs Linux, Python 3.10 or newer, curl, logger, a running cron daemon,
and `/opt/prod/godaddy-cli/gddy`. No Python dependencies or virtual environment
are needed.

The installer reuses the root-owned, mode `0600` PAT file `/root/.godaddy-cli`
when `/etc/bmdynip/auto.env` is missing. If you do not already have a PAT,
generate one with `domains.dns:update` permission as described in
[root GoDaddy authentication]({{ site.baseurl }}{% link pages/root-authentication.md %}).
Without that source file, the installer asks for the PAT with input hidden.
It creates `/etc/bmdynip/auto.env`, owned by root with mode `0600`.
Unattended installation can supply `GDDY_PAT` through the environment; it takes
precedence over the source file. Existing installed credentials are validated
and preserved without prompting.

From the checkout, as root:

```sh
./scripts/install.sh
```

The installer creates:

| Location | Contents |
| --- | --- |
| `/opt/prod/bmdynip/bin/bmdynip` | Executable Python archive containing the application |
| `/opt/prod/bmdynip/conf/bmdynip.json` | Domain and relative A-record names |
| `/opt/prod/bmdynip/data/` | Last successful update and process lock |
| `/etc/bmdynip/auto.env` | Root GoDaddy PAT; directory mode `0700`, file mode `0600` |
| `/etc/cron.d/bmdynip` | Root cron job using `DBMDynIP.CRON_SCHEDULE` |

Installation enables cron immediately. It does not run a DNS update itself.
The supplied hostname list is empty, so the job makes no DNS changes until
you populate it. Follow the [configuration guide]({{ site.baseurl }}{% link pages/configuration.md %}),
then see [running and monitoring]({{ site.baseurl }}{% link pages/running.md %}).

## Reinstall after an update

After pulling a release, rerun the installer as root:

```sh
git pull
./scripts/install.sh
```

This replaces the executable and cron job while preserving configuration,
saved state, and credentials. There is no separate upgrade script.
