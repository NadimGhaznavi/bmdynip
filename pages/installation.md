---
title: Installation
author_profile: true
layout: single
---

[Documentation index]({% link index.md %})

[Installation]({% link pages/installation.md %}) · [Configuration]({% link pages/configuration.md %}) · [Running and monitoring]({% link pages/running.md %})

MyDynIP updates the configured hostnames to this host's public IPv4 address.
It runs as root every five minutes from `/etc/cron.d/mydynip`.

Run the installation commands below as root on
the production host. Run repository commands from your MyDynIP checkout.

## Install

The host needs Linux, Python 3.10 or newer, curl, logger, a running cron daemon,
and `/opt/prod/godaddy-cli/gddy`. No Python dependencies or virtual environment
are needed.

Place a GoDaddy PAT with DNS access in `/etc/mydynip/auto.env`, owned by root
with permissions `0600`. On a new host, prepare and edit the file:

```sh
install -d -m 0700 /etc/mydynip
(umask 077; touch /etc/mydynip/auto.env)
chown root:root /etc/mydynip/auto.env
chmod 0600 /etc/mydynip/auto.env
vi /etc/mydynip/auto.env
```

The file contains one unquoted assignment:

```text
GDDY_PAT=gd_pat_your_token_here
```

The token is passed to `gddy` through its environment. It is not stored in the
repository, executable, cron file, or command arguments. The installer requires
this credential file and preserves it.

From the checkout, as root:

```sh
./scripts/install.sh
```

The installer creates:

| Location | Contents |
| --- | --- |
| `/opt/prod/mydynip/bin/mydynip` | Executable Python archive containing the application |
| `/opt/prod/mydynip/conf/mydynip.json` | Domain and relative A-record names |
| `/opt/prod/mydynip/data/` | Last successful update and process lock |
| `/etc/cron.d/mydynip` | Root cron job using `DMyDynIP.CRON_SCHEDULE` |

Installation enables cron immediately. It does not run a DNS update itself.
The supplied hostname list is empty, so the job makes no DNS changes until
you populate it. Follow the [configuration guide]({% link pages/configuration.md %}),
then see [running and monitoring]({% link pages/running.md %}).

## Reinstall after an update

After pulling a release, rerun the installer as root:

```sh
git pull
./scripts/install.sh
```

This replaces the executable and cron job while preserving configuration,
saved state, and credentials. There is no separate upgrade script.
