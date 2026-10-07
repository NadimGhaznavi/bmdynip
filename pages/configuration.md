\---
title: Configuration
author_profile: true
layout: single
\---

[Documentation index]\({{ site.baseurl }}{% link index.md %})

[Installation]\({{ site.baseurl }}{% link pages/installation.md %}) · [Configuration]\({{ site.baseurl }}{% link pages/configuration.md %}) · [Running and monitoring]\({{ site.baseurl }}{% link pages/running.md %})

Edit the configuration as root on the production host.

**## Configure the domain**

Edit \`/opt/prod/bmdynip/conf/bmdynip.json\`:

\`\`\`json
{
&#x20; "domain": "osoyalce.com"
}
\`\`\`

Set \`domain\` to your DNS zone before installation, or update the installed file
and restart the Web UI.

**## Manage records**

Add and delete managed names in the
[Web UI]\({{ site.baseurl }}{% link pages/web-interface.md %}). The runner reads
hostnames from MariaDB; no managed names means no DNS changes. Adding a name
starts the runner immediately, even if the IP has not changed.
Deleting a name stops managing it; its existing DNS record remains in place.

Names added through the UI must be single labels (e.g. `www` or `count`). 
Installation and upgrades preserve managed names in MariaDB. 

Each configured name is managed as a single A record. On a changed IP or
configuration, the updater deletes **\*\*all A records at that name\*\*** and creates
one with the new address. Other record types and unconfigured names are left
alone. \`gddy\` uses its default TTL of 3600 seconds.