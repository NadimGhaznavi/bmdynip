---
title: Configuration
author_profile: true
layout: single
---

[Documentation index]({% link index.md %})

[Installation]({% link pages/installation.md %}) · [Configuration]({% link pages/configuration.md %}) · [Running and monitoring]({% link pages/running.md %})

Run these commands as root on the production host.

## Configure records

Edit `/opt/prod/bmdynip/conf/bmdynip.json`:

```json
{
  "domain": "osoyalce.com",
  "hostnames": []
}
```

Populate `hostnames` with the relative names to manage in this zone. Use `@`
for the domain's apex. No hostnames are included by default.
An empty hostname list disables DNS updates. Changes are read on each run;
adding or changing names triggers an update even if the IP has not changed.
Removing a name stops managing it; its existing DNS record remains in place.

Each configured name is managed as a single A record. On a changed IP or
configuration, the updater deletes **all A records at that name** and creates
one with the new address. Other record types and unconfigured names are left
alone. `gddy` uses its default TTL of 3600 seconds.

