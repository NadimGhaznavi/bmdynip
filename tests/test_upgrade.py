"""Verify upgrade delegation without changing the installed application."""

from contextlib import ExitStack
import importlib.util
import io
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import call, patch
import zipfile
import crontab
import pymysql

from bmdynip.constants.DBMDynIP import DBMDynIP
from bmdynip.interface.RunnerSchedule import RunnerSchedule


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("upgrade_installer", ROOT / "scripts/install.py")
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class UpgradeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="bmdynip-upgrade-")
        self.addCleanup(directory.cleanup)
        self.checkout = Path(directory.name) / "checkout with spaces"
        scripts = self.checkout / "scripts"
        scripts.mkdir(parents=True)
        self.script = scripts / "upgrade.sh"
        self.script.write_bytes((ROOT / "scripts/upgrade.sh").read_bytes())
        self.script.chmod(0o755)
        self.marker = self.checkout / "installed"
        self.installer = scripts / "install.py"
        self.installer.write_text(
            'from pathlib import Path\nimport sys\n'
            'assert sys.argv[1:] == ["upgrade"]\n'
            'Path("installed").write_text(str(Path.cwd()))\n')
        self.installer.chmod(0o755)

    def run_upgrade(self, *arguments):
        return subprocess.run([str(self.script), *arguments], cwd=self.checkout.parent,
                              text=True, capture_output=True, timeout=10)

    def test_upgrade_runs_installer_from_checkout(self):
        result = self.run_upgrade()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.marker.read_text().strip(), str(self.checkout))

    def test_installer_failure_is_reported(self):
        self.installer.write_text('import sys\nprint("Installation failed", file=sys.stderr)\nsys.exit(7)\n')
        result = self.run_upgrade()
        self.assertEqual(result.returncode, 7)
        self.assertIn("Installation failed", result.stderr)

    def test_help_does_not_install(self):
        result = self.run_upgrade("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Usage: sudo scripts/upgrade.sh", result.stdout)
        self.assertFalse(self.marker.exists())

    def test_invalid_arguments_do_not_install(self):
        for arguments in (("--unknown",), ("--help", "extra")):
            with self.subTest(arguments=arguments):
                result = self.run_upgrade(*arguments)
                self.assertEqual(result.returncode, 1)
                self.assertIn("Usage:", result.stderr)
                self.assertFalse(self.marker.exists())


class UpgradeDeploymentTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="bmdynip-deployment-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name, value in {
            "INSTALL_DIR": str(self.root / "prod"),
            "WEB_SERVICE_FILE": str(self.root / "bmdynip-web.service"),
            "CRON_FILE": str(self.root / "cron"),
            "CREDENTIALS_FILE": str(self.root / "auto.env"),
            "GODADDY_CLI": "/usr/bin/true",
        }.items():
            self.stack.enter_context(patch.object(DBMDynIP, name, value))
        self.control = self.stack.enter_context(patch.object(installer, "systemctl"))
        self.opener = self.stack.enter_context(patch.object(installer, "build_opener")).return_value
        self.opener.open.return_value.__enter__.return_value.status = 200
        self.stack.enter_context(patch("sys.stdout", new=io.StringIO()))
        self.stack.enter_context(patch.object(RunnerSchedule, "_require_root"))
        self.dependencies = self.stack.enter_context(
            patch.object(installer, "install_dependencies", side_effect=self.stage_dependency))

    @staticmethod
    def stage_dependency(target):
        shutil.copytree(Path(pymysql.__file__).parent, target / "pymysql",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copyfile(crontab.__file__, target / "crontab.py")

    def test_stop_deploy_start_preserves_files_and_permissions(self):
        root = Path(DBMDynIP.INSTALL_DIR)
        (root / "bin").mkdir(parents=True)
        (root / "conf").mkdir()
        (root / "data").mkdir()
        web = root / "bin/bmdynip-web"
        web.write_bytes(b"old executable")
        config = root / "conf/bmdynip.json"
        config.write_text('{"domain":"example.com","hostnames":["home"]}\n')
        state = root / "data/state.json"
        state.write_text('{"ip":"8.8.8.8","records":[]}\n')
        credentials = Path(DBMDynIP.CREDENTIALS_FILE)
        credentials.write_text("GDDY_PAT=gd_pat_test_only\n")
        credentials.chmod(0o600)
        original = {path: path.read_bytes() for path in (config, state, credentials)}

        def control(action, *arguments):
            if action == "stop":
                self.assertEqual(web.read_bytes(), b"old executable")
            if action == "start":
                self.assertTrue(zipfile.is_zipfile(web))
                self.assertTrue(Path(DBMDynIP.CRON_FILE).exists())

        self.control.side_effect = control
        with patch.object(installer.Credentials, "provision"):
            installer.upgrade()
        service = "bmdynip-web.service"
        self.assertEqual(self.control.call_args_list, [
            call("stop", service), call("daemon-reload"), call("enable", service),
            call("start", service), call("is-active", "--quiet", service),
        ])
        for path, content in original.items():
            self.assertEqual(path.read_bytes(), content)
        for name in ("bmdynip", "bmdynip-web"):
            archive = root / "bin" / name
            self.assertEqual(archive.stat().st_mode & 0o777, 0o755)
            with zipfile.ZipFile(archive) as bundle:
                self.assertIn("bmdynip/app/main.py", bundle.namelist())
                self.assertIn("pymysql/__init__.py", bundle.namelist())
                self.assertIn("crontab.py", bundle.namelist())
                self.assertIn("bmdynip/server/static/bmdynip-logo.png", bundle.namelist())
            result = subprocess.run([str(archive), "--help"], text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(credentials.stat().st_mode & 0o777, 0o600)
        cron = Path(DBMDynIP.CRON_FILE)
        self.assertEqual(cron.stat().st_mode & 0o777, 0o644)
        self.assertIn(f"{DBMDynIP.CRON_SCHEDULE} root {root}/bin/bmdynip", cron.read_text())

    def test_upgrade_preserves_custom_disabled_runner_schedule(self):
        with patch.object(installer.Credentials, "provision"):
            installer.install()
            schedule = RunnerSchedule()
            values = schedule.update(False, "30 4 * * 1-5")
            installer.upgrade()
        self.assertEqual(schedule.read(), values)

    def test_stop_failure_prevents_deployment(self):
        self.control.side_effect = subprocess.CalledProcessError(1, "systemctl stop")
        with patch.object(installer.Credentials, "provision"), \
                self.assertRaises(subprocess.CalledProcessError):
            installer.upgrade()
        self.assertFalse((Path(DBMDynIP.INSTALL_DIR) / "bin/bmdynip").exists())
        self.assertFalse(Path(DBMDynIP.CRON_FILE).exists())
        self.control.assert_called_once_with("stop", "bmdynip-web.service")

    def test_dependency_failure_leaves_service_running(self):
        self.dependencies.side_effect = subprocess.CalledProcessError(1, "pip")
        with patch.object(installer.Credentials, "provision"), \
                self.assertRaises(subprocess.CalledProcessError):
            installer.upgrade()
        self.control.assert_not_called()
        self.assertFalse((Path(DBMDynIP.INSTALL_DIR) / "bin/bmdynip").exists())

    def test_inactive_service_is_retried_before_http_check(self):
        self.control.side_effect = [None, subprocess.CalledProcessError(3, "systemctl"), None]
        with patch.object(installer.time, "sleep"):
            installer.start_web("start")
        self.assertEqual(self.control.call_count, 3)
        self.opener.open.assert_called_once()

    def test_inactive_service_times_out_with_journal_hint(self):
        self.control.side_effect = [None, subprocess.CalledProcessError(3, "systemctl")]
        with patch.object(installer.time, "monotonic", side_effect=[0, 11]), \
                self.assertRaisesRegex(ValueError, "journalctl -u bmdynip-web.service"):
            installer.start_web("start")
        self.opener.open.assert_not_called()

    def test_start_failure_is_not_retried(self):
        self.control.side_effect = subprocess.CalledProcessError(1, "systemctl start")
        with self.assertRaises(subprocess.CalledProcessError):
            installer.start_web("start")
        self.control.assert_called_once()


class DependencyTests(unittest.TestCase):
    def test_requirements_are_installed_into_archive_staging(self):
        with tempfile.TemporaryDirectory(prefix="bmdynip-pip-test-") as directory, \
                patch.object(installer.venv, "EnvBuilder") as builder, \
                patch.object(installer.subprocess, "run") as run:
            target = Path(directory)
            installer.install_dependencies(target)
        builder.assert_called_once_with(with_pip=True)
        environment = Path(builder.return_value.create.call_args.args[0])
        run.assert_called_once_with(
            [str(environment / "bin/python"), "-m", "pip", "--disable-pip-version-check",
             "install", "--no-cache-dir", "--no-compile", "--target", str(target),
             "-r", str(ROOT / "requirements.txt")], check=True, timeout=180)
        self.assertFalse(environment.exists())
