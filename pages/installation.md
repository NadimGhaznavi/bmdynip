---
title: Installation
author_profile: true
layout: single
---

[Documentation index]({{ site.baseurl }}{% link index.md %})

[Installation]({{ site.baseurl }}{% link pages/installation.md %}) · [Configuration]({{ site.baseurl }}{% link pages/configuration.md %}) · [Running and monitoring]({{ site.baseurl }}{% link pages/running.md %})

BMDynIP updates the configured hostnames to this host's public IPv4 address.
It runs as root from `/etc/cron.d/bmdynip`, every five minutes by default.

Run the installation commands below as root on
the production host. Run repository commands from your BMDynIP checkout.

## Install

The host needs Linux with systemd, Python 3.10 or newer with venv support, curl,
logger, a running cron daemon, a running MariaDB server with the `mariadb` client,
and `/opt/prod/godaddy-cli/gddy`.
On Debian or Ubuntu, install `python3-venv`. Installation and upgrades require
access to the Python package index to install `requirements.txt` into both
executable archives. PyMySQL is bundled; no global Python package installation
is needed.

The installer reuses the root-owned, mode `0600` PAT file `/root/.godaddy-cli`
when `/etc/bmdynip/auto.env` is missing. If you do not already have a PAT,
generate one with `domains.dns:update` permission as described in
[root GoDaddy authentication]({{ site.baseurl }}{% link pages/root-authentication.md %}).
Without that source file, the installer asks for the PAT with input hidden.
It creates `/etc/bmdynip/auto.env`, owned by root with mode `0600`.
Unattended installation can supply `GDDY_PAT` through the environment; it takes
precedence over the source file. Existing installed credentials are validated
and preserved without prompting.

When `/etc/bmdynip/database.env` is missing, root must be able to connect to the
local MariaDB server using Unix socket authentication. The installer creates
the `bmdynip` database and local account, generates a password, applies the
schema, and saves the credentials with mode `0600` in the mode `0700` directory.
If the account already exists without its credentials file, its password is reset.
Existing credentials are validated and retained; the configured account needs
`SELECT`, `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `ALTER`, `INDEX`, and `REFERENCES`
privileges on its database. Database setup finishes before deployment stops the
Web UI. Reinstallation and uninstallation preserve the database and credentials.

From the checkout, as root:

```sh
./scripts/install.sh
```

The installer creates:

| Location | Contents |
| --- | --- |
| `/opt/prod/bmdynip/bin/bmdynip` | Executable Python archive containing the application |
| `/opt/prod/bmdynip/bin/bmdynip-web` | Web UI executable with bundled assets |
| `/etc/systemd/system/bmdynip-web.service` | Web UI service enabled at boot |
| `/opt/prod/bmdynip/conf/bmdynip.json` | Domain and relative A-record names |
| `/opt/prod/bmdynip/data/` | Last successful update and process lock |
| `/etc/bmdynip/auto.env` | Root GoDaddy PAT; directory mode `0700`, file mode `0600` |
| `/etc/bmdynip/database.env` | Root-owned MariaDB credentials, mode `0600` |
| `/etc/cron.d/bmdynip` | Root cron job using `DBMDynIP.CRON_SCHEDULE` |
| MariaDB `bmdynip` database | Application tables and CWM history |

Installation enables cron immediately. It does not run a DNS update itself.
Existing custom or disabled schedules are retained. Change the schedule in the
[Web UI]({{ site.baseurl }}{% link pages/web-interface.md %}#runner-schedule).
It starts the [Web UI]({{ site.baseurl }}{% link pages/web-interface.md %})
on port `49700` and prints its status after checking HTTP readiness.
The supplied hostname list is empty, so the job makes no DNS changes until
you populate it. Follow the [configuration guide]({{ site.baseurl }}{% link pages/configuration.md %}),
then see [running and monitoring]({{ site.baseurl }}{% link pages/running.md %}).

## Upgrade

After pulling a release, run the upgrade script as root:

```sh
git pull
./scripts/upgrade.sh
```

This stops the Web UI, replaces the executables and cron job while preserving
configuration, saved state, and credentials, then starts the Web UI and prints
its status and port after checking readiness. If deployment fails after the
service stops, fix the reported error and rerun the upgrade.
