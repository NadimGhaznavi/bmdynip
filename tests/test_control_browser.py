"""Exercise the real browser controls against a disposable MariaDB-backed server."""

import json
import os
from pathlib import Path
import subprocess
import unittest

from test_control_api import LiveControlFixture, ROOT
from bmdynip.server.__main__ import ControlHandler


class BrowserHandler(ControlHandler):
    def serve(self):
        if self.path == "/__browser-check":
            body = (b'<!doctype html><html><body><pre id="result">Running browser checks</pre>'
                    b'<iframe id="control" src="/" width="1440" height="1200"></iframe>'
                    b'<script type="module" src="/__browser-check.js"></script></body></html>')
            content_type = "text/html"
        elif self.path == "/__browser-check.js":
            body = (ROOT / "tests/browser-control-check.js").read_bytes()
            content_type = "text/javascript"
        else:
            return super().serve()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path == "/__runner-failure":
            self.server.start_runner.side_effect = FileNotFoundError('test-only missing runner')
            self.respond(200, {"failed": True})
            return
        if self.path == "/__failure":
            values = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self.server.db_failure = values["failed"]
            self.respond(200, {"failed": self.server.db_failure})
            return
        super().do_POST()


@unittest.skipUnless(os.environ.get("BMDYNIP_TEST_DB_SOCKET") and os.environ.get("BMDYNIP_TEST_CHROME"),
                     "Set BMDYNIP_TEST_DB_SOCKET and BMDYNIP_TEST_CHROME for browser checks")
class ControlBrowserTests(LiveControlFixture):
    def handler_class(self):
        return BrowserHandler

    def chrome(self, *arguments):
        return subprocess.run(
            [os.environ["BMDYNIP_TEST_CHROME"], "--headless", "--no-sandbox", "--disable-gpu",
             "--disable-dev-shm-usage", "--user-data-dir=" + str(self.root / "chrome"),
             "--virtual-time-budget=60000", *arguments],
            text=True, capture_output=True, check=True, timeout=60)

    def test_live_browser_writes_reload_errors_and_recovery(self):
        self.seed_history(failed=True)
        result = self.chrome("--dump-dom", self.url + "/__browser-check")
        artifacts = os.environ.get("BMDYNIP_TEST_ARTIFACTS")
        if artifacts:
            output = Path(artifacts)
            output.mkdir(parents=True, exist_ok=True)
            (output / "browser-check.html").write_text(result.stdout)
        self.assertIn('data-result="passed"', result.stdout, result.stdout)
        self.assertNotIn('data-result="failed"', result.stdout)
        self.assertTrue(any(record["name"] == "saved" for record in self.request()[1]["records"]))
        if artifacts:
            for name, size in (("desktop", "1440,1400"), ("mobile", "390,1800")):
                self.chrome("--window-size=" + size, "--screenshot=" + str(output / f"{name}.png"), self.url + "/")
