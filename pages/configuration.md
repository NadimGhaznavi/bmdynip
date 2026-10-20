---
title: Configuration
author_profile: true
layout: single
---

[Documentation index]({{ site.baseurl }}{% link index.md %})

[Installation]({{ site.baseurl }}{% link pages/installation.md %}) · [Configuration]({{ site.baseurl }}{% link pages/configuration.md %}) · [Running and monitoring]({{ site.baseurl }}{% link pages/running.md %})

Edit the configuration as root on the production host.

## Configure the domain

Edit `/opt/prod/bmdynip/conf/bmdynip.json`:

```json
{
   "domain": "osoyalce.com"
}
```

Set `domain` to your DNS zone before installation, or update the installed file
and restart the Web UI.

## Configure the Web UI listener

Listener defaults come from `DBMDynIP.CMDB_NETWORK`: `0.0.0.0:49700` for `http`.
Override either field in the installed `conf/bmdynip.json`:

```json
{
  "domain": "osoyalce.com",
  "network": {
    "http": {"interface": "127.0.0.1", "port": 49701}
  }
}
```

Omitted fields inherit the defaults. Unknown listener names or fields, invalid
IPv4 addresses, and ports outside 1–65535 are rejected. Ports must be integers.
Apply changes with `sudo ./scripts/restart.sh` from the checkout. The command
validates configuration before restarting and checks the configured readiness
address. Reinstall and upgrade preserve existing configuration files.

For a direct server invocation, `--host` and `--port` override the JSON settings
for that process. Restart processes after editing configuration.

## CMDB discovery

Register **BMDynIP** through CMDB's Add Application and use Re-Scan Applications
on the production host. The installer publishes the literal version and CMDB
metadata at `/opt/prod/bmdynip/bmdynip/constants/DBMDynIP.py`.
Development checkouts under `/opt/dev` are not discovery targets.

`CMDB_COMPONENTS` declares the configuration and saved-state directories and
supplies their runtime paths. `CMDB_DATABASES` declares the local MariaDB catalog
and supplies the database name for initial provisioning. Existing database
credentials remain authoritative for an installation; using a different catalog
requires updating the declaration to match it. Credentials are not discovery metadata.
`CMDB_NETWORK` supplies listener defaults; CMDB network discovery is pending.

## Manage records

Add and delete managed names in the
[Web UI]({{ site.baseurl }}{% link pages/web-interface.md %}). The runner reads
hostnames from MariaDB; no managed names means no DNS changes. Adding a name
starts the runner immediately, even if the IP has not changed.
Deleting a name stops managing it; its existing DNS record remains in place.

Names added through the UI must be single labels (e.g. `www` or `count`). 
Installation and upgrades preserve managed names in MariaDB. 

Each configured name is managed as a single A record. On a changed IP or
configuration, the updater deletes **all A records at that name** and creates
one with the new address. Other record types and unconfigured names are left
alone. `gddy` uses its default TTL of 3600 seconds.