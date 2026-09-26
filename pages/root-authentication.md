---
title: Root GoDaddy authentication
author_profile: true
layout: single
---

[Documentation index]({% link index.md %})

MyDynIP runs as root on Sally, including its cron job. It authenticates to
GoDaddy using a Personal Access Token (PAT) in `/etc/mydynip/auto.env`.
For GoDaddy CLI setup, see the
[GoDaddy CLI reference](https://kb.osoyalce.com/pages/godaddy-cli.html).

## Why a separate credential was needed

The `gddy` commands worked as `dan` because that account had a valid,
refreshable OAuth login with DNS-update permission. Root did not share that
login. The token initially copied from `/home/dan/.godaddy-cli` matched the
installed file, but GoDaddy rejected it with HTTP 401 Unauthorized.

Supplying `GDDY_PAT` makes `gddy` use that PAT ahead of a cached OAuth login.
We generated a new PAT named `mydynip`, replaced the installed token, and
confirmed that root could query DNS and run the updater successfully.

## Generate a PAT

Sign in to the GoDaddy account that manages the zone and open the
[Personal Access Token page](https://developer.godaddy.com/personal-access-token).

1. Generate a token named `mydynip`.
2. Grant `domains.dns:update` permission, which also permits DNS reads.
3. Choose an expiration date and arrange to replace the token before it expires.
4. Copy the token when it is displayed; GoDaddy shows it only once.

The PAT belongs to the GoDaddy account. Its name is a label; it is not a
Linux username, hostname, or DNS record name. Root on Sally uses it because
root can read the installed credential file.

## Install the credential

Run these commands as root on the production host:

```sh
install -d -m 0700 /etc/mydynip
(umask 077; touch /etc/mydynip/auto.env)
chown root:root /etc/mydynip/auto.env
chmod 0600 /etc/mydynip/auto.env
vi /etc/mydynip/auto.env
```

Store exactly one unquoted assignment, replacing the placeholder with the
new token:

```text
GDDY_PAT=gd_pat_your_token_here
```

The updater reads this file and passes the token through the child process's
environment. Do not put the token in command arguments, cron entries, or the
repository. No root OAuth login or `gddy pat add` step is required.

Check ownership and permissions without displaying the token:

```sh
stat -c '%U:%G %a %n' /etc/mydynip/auto.env
```

Expected: `root:root 600 /etc/mydynip/auto.env`.

## Validate authentication

As root, load the credential for one read-only query. The subshell keeps the
token out of the parent shell's environment:

```sh
(
    set -a
    . /etc/mydynip/auto.env
    set +a
    /opt/prod/godaddy-cli/gddy dns list osoyalce.com --type A --env prod --timeout 20s
)
```

A successful response confirms read access; an empty record list is also a
valid result. If GoDaddy returns 401, check that the new token was installed
correctly and is still active. A 403 indicates an authorization problem;
check its scopes and access to the zone. `gddy auth status` reports cached
OAuth state and does not establish that this PAT works.

After the query succeeds, follow the
[running guide]({% link pages/running.md %}) to execute MyDynIP against the
configured hostname list. During setup on Sally, we verified the configured
A record matched `/opt/prod/mydynip/data/state.json` after the successful run.

To rotate the token, replace the assignment and repeat this check. MyDynIP
reads the file on each run, so no reinstall is needed. Installation and
uninstall both preserve the credential file.
