---
title: Web interface preview
---

[Documentation index]({{ site.baseurl }}{% link index.md %})

From the development checkout, start the UI preview with Python 3.10 or newer:

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
The existing installer and cron updater remain independent of this preview.

Stop the preview with Ctrl+C.
