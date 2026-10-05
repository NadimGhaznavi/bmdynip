"""Verify the runner cron interface without changing system cron."""

from concurrent.futures import ThreadPoolExecutor
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from crontab import CronTab

from bmdynip.constants.DBMDynIP import DBMDynIP
from bmdynip.interface.RunnerSchedule import RunnerSchedule
from bmdynip.server.__main__ import ControlHandler


class TemporarySchedule(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="bmdynip-schedule-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.schedule = RunnerSchedule(self.root / "cron", self.root / "data")
        root = patch("bmdynip.interface.RunnerSchedule.os.geteuid", return_value=0)
        root.start()
        self.addCleanup(root.stop)

    def jobs(self):
        return list(CronTab(tab=self.schedule.cron_file.read_text(), user=False))


class ScheduleTests(TemporarySchedule):
    def test_default_installs_one_root_job_every_five_minutes(self):
        self.assertEqual(self.schedule.read(), {"enabled": True, "expression": "*/5 * * * *"})
        self.schedule.install()
        jobs = self.jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].user, "root")
        self.assertEqual(jobs[0].command, self.schedule.command)
        self.assertEqual(str(jobs[0].slices), DBMDynIP.CRON_SCHEDULE)
        self.assertTrue(jobs[0].is_enabled())
        self.assertEqual(self.schedule.cron_file.stat().st_mode & 0o777, 0o644)

    def test_custom_disabled_schedule_survives_reload_and_install(self):
        values = {"enabled": False, "expression": "30 4 * * 1-5"}
        self.schedule.update(**values)
        another = RunnerSchedule(self.schedule.cron_file, self.schedule.directory)
        self.assertEqual(another.read(), values)
        self.assertEqual(another.install(), values)
        self.assertFalse(self.jobs()[0].is_enabled())
        self.schedule.update(True, "0 */2 * * *")
        self.assertTrue(self.jobs()[0].is_enabled())
        self.assertEqual(len(self.jobs()), 1)

    def test_legacy_schedule_migrates_without_duplicate_runner(self):
        self.schedule.cron_file.write_text(
            "SHELL=/bin/sh\nHOME=/root\nPATH=/usr/bin:/bin\n"
            f"15 * * * * root {self.schedule.command}\n"
            "0 3 * * * root /other # unrelated\n")
        self.schedule.install()
        self.assertEqual(self.schedule.read(), {"enabled": True, "expression": "15 * * * *"})
        self.assertEqual(len(self.jobs()), 2)
        self.assertEqual(len([job for job in self.jobs() if job.comment == self.schedule.COMMENT]), 1)
        self.schedule.update(False, "*/5 * * * *")
        self.assertEqual(len([job for job in self.jobs() if job.command == "/other"]), 1)
        self.assertIn("HOME=/root", self.schedule.cron_file.read_text())

    def test_invalid_settings_do_not_change_cron(self):
        self.schedule.install()
        previous = self.schedule.cron_file.read_bytes()
        for enabled, expression in ((1, "*/5 * * * *"), (True, "@daily"),
                                    (True, "60 * * * *"), (True, "*/5 * * * *\n"),
                                    (True, "* * * * * /command"), (True, None)):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                self.schedule.update(enabled, expression)
            self.assertEqual(self.schedule.cron_file.read_bytes(), previous)

    def test_failed_publication_preserves_previous_schedule(self):
        self.schedule.install()
        previous = self.schedule.cron_file.read_bytes()
        with patch("pathlib.Path.replace", side_effect=OSError("denied")), self.assertRaises(OSError):
            self.schedule.update(False, "0 3 * * 0")
        self.assertEqual(self.schedule.cron_file.read_bytes(), previous)
        self.assertEqual(list(self.root.glob(".bmdynip-cron-*")), [])

    def test_nonroot_updates_are_rejected(self):
        with patch("bmdynip.interface.RunnerSchedule.os.geteuid", return_value=1000), \
                self.assertRaises(PermissionError):
            self.schedule.update(True, "*/5 * * * *")
        self.assertFalse(self.schedule.cron_file.exists())

    def test_symlink_cron_is_rejected_without_changing_target(self):
        target = self.root / "elsewhere"
        target.write_text("unchanged")
        self.schedule.cron_file.symlink_to(target)
        with self.assertRaises(ValueError):
            self.schedule.update(True, "*/5 * * * *")
        self.assertEqual(target.read_text(), "unchanged")

    def test_concurrent_updates_leave_one_complete_job(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.schedule.update, enabled, expression)
                       for enabled, expression in ((True, "*/5 * * * *"), (False, "0 3 * * 0"))]
            for future in futures:
                future.result(timeout=5)
        self.assertEqual(len(self.jobs()), 1)
        self.assertIn(self.schedule.read(), [
            {"enabled": True, "expression": "*/5 * * * *"},
            {"enabled": False, "expression": "0 3 * * 0"},
        ])


class ScheduleApiTests(TemporarySchedule):
    def request(self, method="GET", body=None, headers=None):
        handler = object.__new__(ControlHandler)
        handler.path = "/api/runner-schedule"
        handler.headers = {"Host": "localhost", "Content-Type": "application/json",
                           "Content-Length": str(len(body or b"")), **(headers or {})}
        handler.rfile = io.BytesIO(body or b"")
        handler.server = SimpleNamespace(runner_schedule=self.schedule,
                                         db_factory=Mock(side_effect=AssertionError("Database accessed")))
        handler.respond = Mock()
        getattr(handler, "do_" + method)()
        return handler.respond.call_args.args

    def test_api_reads_and_updates_real_cron(self):
        status, response = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(response["schedule"], {"enabled": True, "expression": "*/5 * * * *"})
        values = {"enabled": False, "expression": "0 3 * * 0"}
        status, response = self.request("POST", json.dumps(values).encode())
        self.assertEqual((status, response), (200, {"schedule": values}))
        self.assertEqual(self.request()[1], {"schedule": values})

    def test_invalid_requests_do_not_create_cron(self):
        for body in (b"{", b"[]", b"{}", b'{"enabled":true,"expression":"@daily"}',
                     b'{"enabled":true,"expression":"* * * * *","extra":1}'):
            with self.subTest(body=body):
                self.assertEqual(self.request("POST", body)[0], 400)
        self.assertFalse(self.schedule.cron_file.exists())

    def test_cross_origin_and_non_json_writes_are_rejected(self):
        body = b'{"enabled":true,"expression":"*/5 * * * *"}'
        for headers, status in (({"Origin": "https://other.example"}, 403),
                                ({"Sec-Fetch-Site": "cross-site"}, 403),
                                ({"Content-Type": "text/plain"}, 415)):
            self.assertEqual(self.request("POST", body, headers)[0], status)
        self.assertFalse(self.schedule.cron_file.exists())

    def test_save_failure_reports_failure_and_preserves_cron(self):
        self.schedule.install()
        previous = self.schedule.cron_file.read_bytes()
        with patch("pathlib.Path.replace", side_effect=OSError("denied")), self.assertLogs(level="ERROR"):
            self.assertEqual(self.request("POST", b'{"enabled":false,"expression":"0 3 * * 0"}')[0], 503)
        self.assertEqual(self.schedule.cron_file.read_bytes(), previous)
