"""Verify live hostname APIs with private state and an optional disposable database."""

import http.client
import io
from ipaddress import IPv4Address
import json
import os
from pathlib import Path
import subprocess
import tempfile
from threading import Thread
import unittest
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4
from types import SimpleNamespace
from http.server import ThreadingHTTPServer

from pymysql import OperationalError

from bmdynip.constants.DBMDynIP import DBMDynIP
from bmdynip.interface.DatabaseEnvironment import DatabaseEnvironment
from bmdynip.interface.DatabaseProvisioning import DatabaseProvisioning
from bmdynip.interface.DbMgr import DbMgr
from bmdynip.interface.DiscoveryDb import DiscoveryDb
from bmdynip.interface.DnsRecordDb import DnsRecordDb
from bmdynip.interface.IpState import IpState
from bmdynip.interface.PublicIpDb import PublicIpDb
from bmdynip.interface.RunnerSchedule import RunnerSchedule
from bmdynip.server.__main__ import ControlHandler


ROOT = Path(__file__).resolve().parents[1]


class ApiRequestTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="bmdynip-api-")
        self.addCleanup(directory.cleanup)
        self.db = MagicMock()
        self.db.insert.return_value = 7
        self.factory = Mock(return_value=self.db)
        self.server = SimpleNamespace(db_factory=self.factory, domain="example.test",
                                      state_directory=Path(directory.name), start_runner=Mock())

    def request(self, path="/api/records", method="POST", body=b'{"name":"home"}', headers=None):
        handler = object.__new__(ControlHandler)
        handler.path = path
        handler.headers = {"Host": "localhost", "Content-Type": "application/json",
                           "Content-Length": str(len(body)), **(headers or {})}
        handler.rfile = io.BytesIO(body)
        handler.server = self.server
        handler.respond = Mock()
        getattr(handler, "do_" + method)()
        return handler.respond.call_args.args

    def test_add_normalizes_name_and_closes_database(self):
        def start():
            self.db.close.assert_called_once()
            self.db.transaction.return_value.__exit__.assert_called_once()
            with IpState(self.server.state_directory).lock() as acquired:
                self.assertTrue(acquired)
        self.server.start_runner.side_effect = start
        self.assertEqual(self.request(body=b'{"name":" HOME "}'), (201, {"id": 7, "runnerStarted": True}))
        self.assertEqual(self.db.insert.call_args.args[1], ("example.test", "home"))
        self.db.close.assert_called_once()
        self.server.start_runner.assert_called_once()

    def test_invalid_payloads_do_not_open_database(self):
        for body in (b"{", b"[]", b'{"name":1}', b'{"name":"home","extra":1}'):
            with self.subTest(body=body):
                self.assertEqual(self.request(body=body)[0], 400)
        self.factory.assert_not_called()
        self.server.start_runner.assert_not_called()

    def test_invalid_names_do_not_write_and_close_database(self):
        for name in ("@", "nested.name", "bad name", "-prefix", "suffix-", ""):
            with self.subTest(name=name):
                self.assertEqual(self.request(body=json.dumps({"name": name}).encode())[0], 400)
        self.db.insert.assert_not_called()
        self.assertEqual(self.db.close.call_count, 6)
        self.server.start_runner.assert_not_called()

    def test_cross_origin_and_non_json_writes_do_not_open_database(self):
        for headers, status in (({"Origin": "https://other.example"}, 403),
                                ({"Sec-Fetch-Site": "cross-site"}, 403),
                                ({"Content-Type": "text/plain"}, 415)):
            self.assertEqual(self.request(headers=headers)[0], status)
        self.factory.assert_not_called()

    def test_busy_runner_prevents_write_and_releases_database(self):
        with IpState(self.server.state_directory).lock():
            self.assertEqual(self.request()[0], 409)
        self.db.insert.assert_not_called()
        self.db.close.assert_called_once()
        self.server.start_runner.assert_not_called()

    def test_database_failure_does_not_report_success(self):
        self.db.insert.side_effect = OperationalError(2006, "test-only connection failure")
        self.assertEqual(self.request(), (503, {"error": "Database unavailable."}))
        self.db.close.assert_called_once()
        self.server.start_runner.assert_not_called()

    def test_launch_failure_reports_saved_hostname(self):
        self.server.start_runner.side_effect = FileNotFoundError('runner missing')
        with self.assertLogs(level='ERROR'):
            self.assertEqual(self.request(), (201, {'id': 7, 'runnerStarted': False}))
        self.db.transaction.return_value.__exit__.assert_called_once()

    def test_duplicate_hostname_does_not_trigger_runner(self):
        from pymysql import IntegrityError
        self.db.insert.side_effect = IntegrityError(1062, 'duplicate')
        self.assertEqual(self.request()[0], 409)
        self.server.start_runner.assert_not_called()


class LiveControlFixture(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="bmdynip-live-control-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.socket = os.environ["BMDYNIP_TEST_DB_SOCKET"]
        name = "bmdynip_ui_" + uuid4().hex[:12]
        self.database = name
        self.addCleanup(self.admin, f"DROP DATABASE IF EXISTS `{name}`; DROP USER IF EXISTS '{name}'@'localhost';")
        credentials = self.root / "config/database.env"
        with patch.object(DBMDynIP, "DATABASE_NAME", name), \
                patch.object(DBMDynIP, "DATABASE_USER", name), \
                patch.object(DatabaseProvisioning, "_require_root"):
            DatabaseProvisioning(ROOT / "schema/bmdynip-schema-v1.sql", credentials, self.socket).provision()
        self.values = DatabaseEnvironment.read(credentials)
        state = self.root / "state"
        state.mkdir()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.handler_class())
        self.server.db_factory = self.open_database
        self.server.db_failure = False
        self.server.start_runner = Mock()
        self.server.domain = "example.test"
        self.server.state_directory = state
        self.server.runner_schedule = RunnerSchedule(self.root / "cron", state)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def handler_class(self):
        return ControlHandler

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def open_database(self):
        if self.server.db_failure:
            raise OperationalError(2006, "test-only database unavailable")
        return DbMgr(self.values)

    def admin(self, sql):
        subprocess.run([DBMDynIP.MARIADB, "--no-defaults", "--user=root", "--protocol=socket",
                        "--socket=" + self.socket], input=sql, text=True,
                       capture_output=True, check=True, timeout=30)

    def request(self, path="/api/snapshot", method="GET", value=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request(method, path, body=json.dumps(value) if value is not None else None,
                               headers={"Content-Type": "application/json", **(headers or {})})
            response = connection.getresponse()
            body = response.read()
            value = json.loads(body) if "application/json" in response.getheader("Content-Type", "") else body
            return response.status, value
        finally:
            connection.close()

    def seed_history(self, *, failed=False):
        db = self.open_database()
        try:
            with db.transaction():
                connection = DiscoveryDb(db).reconcile(
                    {"address": "192.0.2.10", "gateway": "192.0.2.1", "interface": "test0",
                     "mac": "02:00:00:00:00:10", "gateway_mac": "02:00:00:00:00:01"},
                    {"hostname": "test-host", "system": {"ID": "test"}})
                DnsRecordDb(db).add("example.test", "existing")
            address = IPv4Address("8.8.8.8")
            audit = PublicIpDb(db, connection)
            audit.observe(address)
            records = DnsRecordDb(db).list_records()
            request = audit.begin(records[0], address)
            audit.succeeded(request)
            audit.applied(records, address)
            if failed:
                with db.transaction():
                    DnsRecordDb(db).add("example.test", "failed")
                record = next(record for record in DnsRecordDb(db).list_records() if record.name == "failed")
                request = audit.begin(record, address)
                audit.failed(request, 'Provider unavailable <img src=x onerror="window.injected=true">')
        finally:
            db.close()


@unittest.skipUnless(os.environ.get("BMDYNIP_TEST_DB_SOCKET"), "Set BMDYNIP_TEST_DB_SOCKET for database checks")
class LiveControlTests(LiveControlFixture):
    def test_add_duplicate_reload_and_delete_persist(self):
        self.assertEqual(self.request()[1]["records"], [])
        status, saved = self.request("/api/records", "POST", {"name": " WinterMute "})
        self.assertEqual(status, 201)
        record = self.request()[1]["records"][0]
        self.assertEqual((record["hostname"], record["address"], record["status"]),
                         ("wintermute.example.test", None, "Pending"))
        self.assertEqual(self.request("/api/records", "POST", {"name": "wintermute"})[0], 409)
        self.assertEqual(len(self.request()[1]["records"]), 1)
        self.assertEqual(self.request(f"/api/records/{saved['id']}", "DELETE"), (200, {"removed": True}))
        self.assertEqual(self.request()[1]["records"], [])
        self.assertEqual(self.request(f"/api/records/{saved['id']}", "DELETE")[0], 404)

    def test_live_status_and_history_survive_record_removal(self):
        self.seed_history(failed=True)
        status, snapshot = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(snapshot["domain"], "example.test")
        self.assertEqual(snapshot["publicIp"], "8.8.8.8")
        self.assertTrue(snapshot["lastCheckedOn"])
        self.assertTrue(snapshot["lastAppliedOn"])
        self.assertIn("Provider unavailable", snapshot["lastError"])
        self.assertEqual([record["status"] for record in snapshot["records"]], ["Current", "Pending"])
        self.assertEqual(len(snapshot["messages"]), 2)
        for record in snapshot["records"]:
            self.assertEqual(self.request(f"/api/records/{record['id']}", "DELETE")[0], 200)
        after = self.request()[1]
        self.assertEqual(after["records"], [])
        self.assertEqual(after["messages"], snapshot["messages"])

    def test_database_outage_and_recovery(self):
        self.server.db_failure = True
        self.assertEqual(self.request(), (503, {"error": "Database unavailable."}))
        self.assertEqual(self.request("/api/records", "POST", {"name": "home"})[0], 503)
        self.server.db_failure = False
        self.assertEqual(self.request()[1]["records"], [])

    def test_busy_runner_blocks_changes_without_blocking_snapshot(self):
        with IpState(self.server.state_directory).lock():
            self.assertEqual(self.request("/api/records", "POST", {"name": "home"})[0], 409)
            self.assertEqual(self.request()[0], 200)
        self.assertEqual(self.request()[1]["records"], [])
