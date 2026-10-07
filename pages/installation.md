---
title: Installation
author_profile: true
layout: single
---

[Documentation index]({{ site.baseurl }}{% link index.md %})

BMDynIP updates your managed DNS hostnames to your server's public IPv4 address. The DNS updater runs as a root cron job every five minutes by default. The web interface runs as a separate systemd service.

## Prerequisites

Install BMDynIP on a Linux host with:

- systemd and a running cron daemon.
- Python 3.10 or newer with virtual environment support.
- `curl`, `getent`, and `logger`.
- A running MariaDB server and the `mariadb` command-line client.
- The GoDaddy CLI installed at `/opt/prod/godaddy-cli/gddy`.

On Debian or Ubuntu, install `python3-venv` (`sudo apt install python3-venv`) if it is not already available.

Installation and upgrades need access to the Python package index. The scripts bundle the dependencies from `requirements.txt` into the application executables. No global Python package installation is required.

### GoDaddy authentication

Configure the GoDaddy CLI as root and verify that it can query your DNS records. Follow the [root GoDaddy authentication guide]({{ site.baseurl }}{% link pages/root-authentication.md %}) before continuing.

BMDynIP uses root's configured GoDaddy authentication and inherited environment. It does not require or copy a separate PAT file.

See my [Knowlege Base](https://kb.osoyalce.com/pages/godaddy-cli/) notes on setting up the GoDaddy PAT.

### MariaDB access

For a new installation, root must be able to connect to the local MariaDB server using Unix socket authentication.

The installer automatically:

- Creates the `bmdynip` database and a local database account.
- Generates a password and applies the database schema.
- Saves the credentials in `/etc/bmdynip/database.env`.

The credentials file is readable only by root (`0600`), and its directory is accessible only to root (`0700`).

If the database account already exists but the credentials file is missing, the installer resets the account's password. If the credentials file exists, the installer validates and retains it.

An existing configured database account must have these privileges on its database:

`SELECT`, `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `ALTER`, `INDEX`, and `REFERENCES`.

## Install BMDynIP

Run the following command as root, from your BMDynIP checkout on the production host:

```sh
./scripts/install.sh
```