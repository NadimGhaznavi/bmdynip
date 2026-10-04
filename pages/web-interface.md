---
title: Web interface preview
---

[Documentation index]({{ site.baseurl }}{% link index.md %})

Installation starts the Web UI preview as `bmdynip-web.service` on port `49700`
and enables it at boot. Open `http://<server-address>:49700/`.
To restart it from the checkout as root:

```sh
./scripts/restart.sh
```

The command checks that the service is active and HTTP responds, then prints:

```text
BMDynIP Web UI: active on port 49700 (listening on 0.0.0.0)
```

View service logs with `journalctl -u bmdynip-web.service`.

From a development checkout, start a separate preview with Python 3.10 or newer:

```sh
python3 -m bmdynip.server
```

Open `http://127.0.0.1:49700/`. To access the preview from another machine:

```sh
python3 -m bmdynip.server --host 0.0.0.0
```

The interface has no authentication. It displays sample system status and A
records for `osoyalce.com`. Add accepts a single hostname label, such as
`wintermute`; nested names and the apex are excluded. Delete asks for confirmation.

Changes affect only the current browser page and reset on reload. The preview
does not call GoDaddy, save configuration, or run the IP update worker.
The cron updater runs independently of the Web UI service.

Stop a development preview with Ctrl+C.
