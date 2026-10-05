---
title: Web interface
---

[Documentation index]({{ site.baseurl }}{% link index.md %})

Installation starts the Web UI as `bmdynip-web.service` on port `49700`
and enables it at boot. Open `http://<server-address>:49700/`.
To restart it from the checkout as root:

```sh
./scripts/restart.sh
```

The command waits for an active service and a successful `/ready` database check,
then prints:

```text
BMDynIP Web UI: active on port 49700 (listening on 0.0.0.0)
```

View service logs with `journalctl -u bmdynip-web.service`.

`GET /ready` and `HEAD /ready` return HTTP `200` when live status and DNS history
can be read, or `503` when the database or its configuration is unavailable.
Installation, upgrades, and restarts wait up to ten seconds for readiness.

From a development checkout with configured database credentials and domain,
start the Web UI with Python 3.10 or newer:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m bmdynip.server
```

Open `http://127.0.0.1:49700/`. To access it from another machine:

```sh
.venv/bin/python -m bmdynip.server --host 0.0.0.0
```

The interface has no authentication. It displays the configured domain, observed
public IPv4 address, last check and update times, managed hostnames, and the latest
100 DNS change requests alongside recent process messages. Messages show hostname
addition, runner launch, discovery, DNS updates, and completion or failure, with
the emitting module as the source. Status refreshes every five seconds; times use your
browser's local timezone. An unavailable database shows an error and disables
hostname changes until status can be refreshed.

**Add hostname** saves a single label, such as `wintermute`, to the database.
Nested names and the apex are excluded. Saving a hostname starts the installed
runner immediately; DNS status and history refresh as the update completes.
If the runner cannot start, the saved hostname remains available for the next
scheduled or manual run and the interface shows an error.
**Delete** asks for confirmation and stops managing the name;
its existing GoDaddy A record and change history are retained. Hostname changes
persist across reloads. If a save request times out, check the refreshed list
before retrying.

## Runner schedule

The **Runner Schedule** panel controls the installed root cron job. Select
**Enabled**, enter a five-field cron expression, and click **Update**. The default,
`*/5 * * * *`, runs every five minutes in the server's local timezone.
Clear **Enabled** and click **Update** to stop future scheduled runs. An update
already in progress finishes normally. Manual runs remain available.

Schedule changes persist across reloads and upgrades. The Web UI service must
run as root to save them. The cron updater runs independently of the Web UI service.

Stop the development server with Ctrl+C.
