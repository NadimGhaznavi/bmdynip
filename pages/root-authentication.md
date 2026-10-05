---
title: Root GoDaddy authentication
author_profile: true
layout: single
---

[Documentation index]({{ site.baseurl }}{% link index.md %})

BMDynIP and its cron job run as root. They use a GoDaddy Personal Access
Token (PAT) from `/etc/bmdynip/auto.env` for production DNS updates.

## Generate a PAT

Sign in to the GoDaddy account that manages the zone and open the
[Personal Access Token page](https://developer.godaddy.com/personal-access-token).

1. Generate a token named `bmdynip`.
2. Grant `domains.dns:update` permission, which also permits DNS reads.
3. Choose an expiration date and replace the token before it expires.
4. Copy the token when it is displayed; GoDaddy shows it only once.

GoDaddy must issue the PAT. The installer cannot generate a valid token locally.

## Install the credential

Run from the checkout as root:

```sh
./scripts/install.sh
```

Before installation, save the PAT in `$HOME/.godaddy-cli` as root
(normally `/root/.godaddy-cli`). The source file must be owned by root with mode
`0600` and contain either a single `GDDY_PAT=...` assignment or a plain PAT.
It is read without executing shell code and remains unchanged. Environment
tokens do not override it.

The installer creates the credential directory with mode `0700` and the
root-owned file with mode `0600`. Never put the PAT in command arguments,
cron entries, or the repository.

Installation and upgrades refresh the installed PAT from the source file.
Runtime uses only `/etc/bmdynip/auto.env`, so it does not depend on access to the
home file. A failed refresh leaves the previous installed copy intact. Symlinked
credential files or directories are rejected. Uninstall preserves credentials.

The file contains exactly one unquoted assignment:

```text
GDDY_PAT=gd_pat_your_token_here
```

The updater reads this file on each run and passes the PAT through the child
process environment. No root OAuth login or `gddy pat add` step is required.

Check ownership and permissions without displaying the token:

```sh
stat -c '%U:%G %a %n' /etc/bmdynip/auto.env
```

Expected: `root:root 600 /etc/bmdynip/auto.env`.

## Validate authentication and rotate

As root, load the credential for a read-only query:

```sh
python3 - <<'PY'
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, '/opt/prod/bmdynip/bin/bmdynip')
from bmdynip.interface.Credentials import Credentials

environment = dict(os.environ)
environment.pop('GDDY_PAT_PROD', None)
environment['GDDY_PAT'] = Credentials.load(Path('/etc/bmdynip/auto.env'))
result = subprocess.run(
    ['/opt/prod/godaddy-cli/gddy', 'dns', 'list', 'osoyalce.com',
     '--type', 'A', '--env', 'prod', '--timeout', '20s'],
    env=environment, timeout=25)
raise SystemExit(result.returncode)
PY
```

A successful response confirms read access; an empty record list is valid.
HTTP 401 indicates an invalid or expired token. For HTTP 403, check the token's
scopes and access to the zone. `gddy auth status` reports cached OAuth state;
use the DNS query to check this PAT.

To rotate, replace the PAT in `$HOME/.godaddy-cli` as root, run
`./scripts/upgrade.sh` to refresh the installed copy, and repeat the query. Follow the
[running guide]({{ site.baseurl }}{% link pages/running.md %}) to run the updater
against your configured hostname list.
