import importlib.util
from concurrent.futures import ThreadPoolExecutor
import io
from ipaddress import IPv4Address
import json
import os
from pathlib import Path
import socket
import shutil
import subprocess
import tempfile
import time
import unittest
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener
import zipfile
import pymysql
import crontab
from unittest.mock import MagicMock, Mock, patch

from bmdynip.activity.UpdatePublicIp import UpdatePublicIp
from bmdynip.app.main import main
from bmdynip.constants.DBMDynIP import DBMDynIP
from bmdynip.entity.DnsRecord import DnsRecord
from bmdynip.interface.Configuration import Configuration
from bmdynip.interface.Credentials import Credentials
from bmdynip.interface.GoDaddyCli import GoDaddyCli
from bmdynip.interface.IpState import IpState
from bmdynip.interface.PublicIpService import PublicIpService
from bmdynip.interface.StatusMessages import StatusMessages


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bmdynip_installer", ROOT / "scripts/install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
IP = IPv4Address("8.8.8.8")
RECORDS = (DnsRecord("example.com", "api"),)


class TemporaryFiles(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="bmdynip-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def credentials(self):
        path = self.root / "auto.env"
        path.write_text("GDDY_PAT=gd_pat_test_only\n")
        path.chmod(0o600)
        return path


class PublicIpTests(unittest.TestCase):
    def test_matching_public_addresses(self):
        with patch("subprocess.run", return_value=Mock(stdout="8.8.8.8\n")) as run:
            self.assertEqual(PublicIpService().current_address(), IP)
        self.assertEqual(run.call_count, 2)
        for call, url in zip(run.call_args_list, DBMDynIP.PUBLIC_IP_URLS):
            self.assertIn("-4", call.args[0])
            self.assertEqual(call.args[0][-1], url)
            self.assertTrue(call.kwargs["check"])
            self.assertEqual(call.kwargs["timeout"], 25)

    def test_disagreement_and_invalid_addresses(self):
        for value in ("1.1.1.1", "127.0.0.1", "10.0.0.1", "224.0.0.1", "::1", "<html>Error</html>"):
            with self.subTest(value=value), patch("subprocess.run", side_effect=[Mock(stdout="8.8.8.8"), Mock(stdout=value)]):
                with self.assertRaises(ValueError):
                    PublicIpService().current_address()

    def test_timeout_propagates(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("curl", 25)):
            with self.assertRaises(subprocess.TimeoutExpired):
                PublicIpService().current_address()


class FlowTests(TemporaryFiles):
    def setUp(self):
        super().setUp()
        self.state = IpState(self.root)
        self.public_ip = Mock(current_address=Mock(return_value=IP))
        self.dns = Mock()
        self.messages = StatusMessages(self.root / DBMDynIP.STATUS_MESSAGES_FILE)
        self.activity = UpdatePublicIp(self.public_ip, self.dns, self.state, messages=self.messages)

    def test_first_update_then_unchanged(self):
        with patch("sys.stdout", new=io.StringIO()):
            self.assertTrue(self.activity.run(RECORDS))
            self.assertFalse(self.activity.run(RECORDS))
        self.dns.replace.assert_called_once_with(DnsRecord("example.com", "api", IP))
        self.assertTrue(self.state.is_current(IP, RECORDS))
        messages = self.messages.snapshot()
        self.assertTrue(all(entry['source'] == 'bmdynip.activity.UpdatePublicIp' for entry in messages))
        self.assertIn('no DNS update needed', messages[-1]['message'])

    def test_changed_configuration_refreshes_same_ip(self):
        self.state.save(IP, RECORDS)
        records = RECORDS + (DnsRecord("example.com", "home"),)
        with patch("sys.stdout", new=io.StringIO()):
            self.assertTrue(self.activity.run(records))
        self.assertEqual(self.dns.replace.call_count, 2)
        self.assertTrue(self.state.is_current(IP, records))

    def test_partial_failure_preserves_state_and_retries_all_names(self):
        old_address = IPv4Address("1.1.1.1")
        self.state.save(old_address, RECORDS)
        before = self.state.path.read_bytes()
        records = RECORDS + (DnsRecord("example.com", "home"),)
        self.dns.replace.side_effect = [None, ValueError("DNS failed")]
        with self.assertRaisesRegex(ValueError, "DNS failed"):
            self.activity.run(records)
        self.assertEqual(self.state.path.read_bytes(), before)
        self.assertIn('DNS update failed for home.example.com', self.messages.snapshot()[-1]['message'])
        self.dns.replace.side_effect = None
        with patch("sys.stdout", new=io.StringIO()):
            self.assertTrue(self.activity.run(records))
        self.assertEqual(self.dns.replace.call_count, 4)

    def test_discovery_failure_never_changes_dns_or_state(self):
        self.public_ip.current_address.side_effect = ValueError("disagree")
        with self.assertRaises(ValueError):
            self.activity.run(RECORDS)
        self.dns.replace.assert_not_called()
        self.assertFalse(self.state.path.exists())

    def test_launch_failure_preserves_saved_state(self):
        self.activity.dns = GoDaddyCli()
        self.state.save(IPv4Address('1.1.1.1'), RECORDS)
        saved = self.state.path.read_bytes()
        with patch('subprocess.Popen', side_effect=OSError('cannot launch DNS shell')):
            with self.assertRaisesRegex(OSError, 'cannot launch DNS shell'):
                self.activity.run(RECORDS)
        self.assertEqual(self.state.path.read_bytes(), saved)
        self.assertIn('cannot launch DNS shell', self.messages.snapshot()[-1]['message'])

    def test_empty_configuration_does_nothing(self):
        self.assertFalse(self.activity.run(()))
        self.public_ip.current_address.assert_not_called()

    def test_overlapping_lock_is_skipped_then_released(self):
        with self.state.lock() as first:
            self.assertTrue(first)
            with IpState(self.root).lock() as second:
                self.assertFalse(second)
        with self.state.lock() as third:
            self.assertTrue(third)

    def test_invalid_saved_state_stops_dns_changes(self):
        self.state.path.write_text('{"ip": 123, "records": []}')
        with self.assertRaises(ValueError):
            self.activity.run(RECORDS)
        self.dns.replace.assert_not_called()


class BoundaryTests(TemporaryFiles):
    def test_configuration_reads_domain(self):
        path = self.root / "config.json"
        path.write_text(json.dumps({"domain": "example.com"}))
        self.assertEqual(Configuration.domain(path), "example.com")

    def test_legacy_hostname_list_is_ignored(self):
        path = self.root / "config.json"
        for names in (["@", "home", "vpn"], "obsolete", ["bad name"]):
            with self.subTest(names=names):
                path.write_text(json.dumps({"domain": "example.com", "hostnames": names}))
                self.assertEqual(Configuration.domain(path), "example.com")

    def test_bad_configuration_is_rejected(self):
        path = self.root / "config.json"
        for data in ({}, [], {"domain": "--help"}, {"domain": "localhost"},
                     {"domain": "Example.com"}, {"domain": None},
                     {"domain": "a" * 64 + ".com"},
                     {"domain": ".".join(["a" * 63] * 4)},
                     {"domain": "example.com", "unknown": []}):
            with self.subTest(data=data):
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    Configuration.domain(path)

    def test_credential_permissions_and_content(self):
        path = self.credentials()
        self.assertEqual(Credentials.load(path), "gd_pat_test_only")
        path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "0600"):
            Credentials.load(path)
        path.chmod(0o600)
        path.write_text("GDDY_PAT=$(whoami)")
        with self.assertRaises(ValueError):
            Credentials.load(path)

    def test_godaddy_dispatch_does_not_wait_or_capture_output(self):
        with patch('subprocess.Popen') as launch:
            GoDaddyCli().replace(DnsRecord('example.com', 'api', IP))
        command = launch.call_args.args[0]
        self.assertEqual(command[:2], [DBMDynIP.DNS_SHELL, '-c'])
        self.assertIn('dns delete', command[2])
        self.assertIn(' && ', command[2])
        self.assertIn('dns add', command[2])
        self.assertIn('--data 8.8.8.8', command[2])
        self.assertEqual(launch.call_args.kwargs,
                         {'stdin': subprocess.DEVNULL, 'start_new_session': True})
        launch.return_value.wait.assert_not_called()
        launch.return_value.communicate.assert_not_called()

    def test_detached_commands_run_in_order_with_inherited_authentication(self):
        executable = self.root / 'gddy'
        release = self.root / 'release-delete'
        events = self.root / 'events'
        executable.write_text(f'''#!/usr/bin/python3
import os
from pathlib import Path
import sys
import time
assert os.environ['GDDY_PAT_PROD'] == 'gd_pat_working'
assert sys.argv[3] == 'example.com'
assert sys.argv[sys.argv.index('--name') + 1] == 'api'
with Path({str(events)!r}).open('a') as stream:
    stream.write(sys.argv[2] + '\\n')
if sys.argv[2] == 'delete':
    deadline = time.monotonic() + 5
    while not Path({str(release)!r}).exists():
        if time.monotonic() > deadline:
            raise SystemExit(1)
        time.sleep(0.01)
''')
        executable.chmod(0o700)
        children = []
        original = subprocess.Popen
        def launch(*args, **kwargs):
            child = original(*args, **kwargs)
            children.append(child)
            return child
        # No valid JSON is emitted, and delete cannot finish until after replace returns.
        with patch.object(DBMDynIP, 'GODADDY_CLI', str(executable)), \
                patch.dict(os.environ, {'GDDY_PAT_PROD': 'gd_pat_working'}), \
                patch('subprocess.Popen', side_effect=launch):
            GoDaddyCli().replace(DnsRecord('example.com', 'api', IP))
        self.assertIsNone(children[0].poll())
        release.touch()
        self.assertEqual(children[0].wait(timeout=6), 0)
        self.assertEqual(events.read_text().splitlines(), ['delete', 'add'])

    def test_cli_uses_database_records_and_failure_exit(self):
        (self.root / "data").mkdir()
        credential = self.root / "missing-auto.env"
        outputs = [Mock(stdout="8.8.8.8"), Mock(stdout="8.8.8.8"),
                   Mock(returncode=0, stdout='{"data":{"failed":0,"deleted":1}}'),
                   Mock(returncode=0, stdout='{"data":{"failed":0,"created":1}}')]
        with patch.object(DBMDynIP, "INSTALL_DIR", str(self.root)), \
             patch.object(DBMDynIP, "CREDENTIALS_FILE", str(credential)), \
             patch("bmdynip.app.main.os", Mock(geteuid=Mock(return_value=0))), \
             patch("bmdynip.app.main.open_database", return_value=MagicMock()) as database, \
             patch("bmdynip.app.main.DiscoveryCoordinator.run", return_value=7), \
             patch("bmdynip.app.main.DnsRecordDb.list_records", return_value=RECORDS), \
             patch("bmdynip.app.main.PublicIpDb"), \
             patch.object(Credentials, "load", side_effect=AssertionError("Runtime must use gddy authentication")), \
             patch("sys.argv", ["bmdynip"]), patch("sys.stdout", new=io.StringIO()), \
             patch("sys.stderr", new=io.StringIO()):
            with patch("subprocess.run", side_effect=outputs), patch("subprocess.Popen"):
                self.assertEqual(main(), 0)
            saved = (self.root / "data/state.json").read_bytes()
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("curl", 25)):
                self.assertEqual(main(), 1)
            self.assertEqual((self.root / "data/state.json").read_bytes(), saved)
        self.assertEqual(database.return_value.close.call_count, 2)


class InstallationTests(TemporaryFiles):
    def setUp(self):
        super().setUp()
        self.service = self.root / "bmdynip-web.service"
        service_patch = patch.object(DBMDynIP, "WEB_SERVICE_FILE", str(self.service))
        service_patch.start()
        self.addCleanup(service_patch.stop)
        systemctl_patch = patch.object(installer, "systemctl")
        self.systemctl = systemctl_patch.start()
        self.addCleanup(systemctl_patch.stop)
        opener_patch = patch.object(installer, "build_opener")
        self.opener = opener_patch.start().return_value
        self.opener.open.return_value.__enter__.return_value.status = 200
        self.addCleanup(opener_patch.stop)
        source = patch.object(DBMDynIP, "ROOT_CREDENTIALS_FILE", str(self.root / ".godaddy-cli"))
        source.start()
        self.addCleanup(source.stop)
        home = patch("bmdynip.interface.Credentials.Path.home", return_value=self.root)
        home.start()
        self.addCleanup(home.stop)
        (self.root / ".godaddy-cli").write_text("gd_pat_test_only\n")
        (self.root / ".godaddy-cli").chmod(0o600)
        dependencies = patch.object(installer, "install_dependencies", side_effect=self.stage_dependencies)
        dependencies.start()
        self.addCleanup(dependencies.stop)
        schedule_root = patch("bmdynip.interface.RunnerSchedule.RunnerSchedule._require_root")
        schedule_root.start()
        self.addCleanup(schedule_root.stop)
        database = patch.object(installer.DatabaseProvisioning, "provision")
        database.start()
        self.addCleanup(database.stop)

    @staticmethod
    def stage_dependencies(target):
        shutil.copytree(Path(pymysql.__file__).parent, target / "pymysql",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copyfile(crontab.__file__, target / "crontab.py")

    def test_restart_reports_port_after_service_and_http_checks(self):
        with patch("sys.stdout", new=io.StringIO()) as output:
            installer.restart()
        self.assertEqual(self.systemctl.call_args_list, [
            unittest.mock.call("restart", self.service.name),
            unittest.mock.call("is-active", "--quiet", self.service.name),
        ])
        self.assertEqual(output.getvalue(),
                         f"BMDynIP Web UI: active on port {DBMDynIP.WEB_PORT} "
                         f"(listening on {DBMDynIP.WEB_HOST})\n")
        request = self.opener.open.call_args.args[0]
        self.assertEqual(request.full_url,
                         f"http://127.0.0.1:{DBMDynIP.WEB_PORT}{DBMDynIP.WEB_READY_PATH}")
        self.assertEqual(request.get_method(), "HEAD")

    def test_restart_failure_does_not_report_success(self):
        self.systemctl.side_effect = subprocess.CalledProcessError(1, "systemctl")
        with patch("sys.stdout", new=io.StringIO()) as output:
            with self.assertRaises(subprocess.CalledProcessError):
                installer.restart()
        self.assertEqual(output.getvalue(), "")
        self.opener.open.assert_not_called()

    def test_restart_waits_for_http_and_times_out_without_success(self):
        self.opener.open.side_effect = URLError("connection refused")
        with patch.object(installer.time, "monotonic", side_effect=[0, 11]), \
             patch("sys.stdout", new=io.StringIO()) as output:
            with self.assertRaisesRegex(ValueError, f"port {DBMDynIP.WEB_PORT}"):
                installer.restart()
        self.assertEqual(output.getvalue(), "")

    def test_root_credential_file_is_imported_without_prompting(self):
        source = Path(DBMDynIP.ROOT_CREDENTIALS_FILE)
        token = "gd_pat_test;opaque$()_only"
        for content in (f"GDDY_PAT={token}\n", f"{token}\n"):
            with self.subTest(content=content):
                source.write_text(content)
                source.chmod(0o600)
                destination = self.root / "etc/bmdynip/auto.env"
                with patch.dict(os.environ, {}, clear=True), patch("getpass.getpass") as prompt:
                    Credentials.provision(destination, Credentials.godaddy)
                prompt.assert_not_called()
                self.assertEqual(Credentials.load(destination), token)
                self.assertEqual(source.read_text(), content)
                destination.unlink()

    def test_unsafe_or_malformed_root_credential_file_is_rejected(self):
        source = Path(DBMDynIP.ROOT_CREDENTIALS_FILE)
        source.write_text("GDDY_PAT=gd_pat_test_only\n")
        source.chmod(0o644)
        with patch.dict(os.environ, {}, clear=True), patch("getpass.getpass") as prompt:
            with self.assertRaisesRegex(ValueError, "0600"):
                Credentials.godaddy()
            source.chmod(0o600)
            source.write_text("GDDY_PAT=$(whoami)\n")
            with self.assertRaises(ValueError):
                Credentials.godaddy()
            prompt.assert_not_called()

    def test_install_and_upgrade_preserve_legacy_credentials_without_reading_them(self):
        install_root = self.root / "prod"
        credential = self.credentials()
        original = credential.read_bytes()
        with patch.object(DBMDynIP, "INSTALL_DIR", str(install_root)), \
             patch.object(DBMDynIP, "CRON_FILE", str(self.root / "cron")), \
             patch.object(DBMDynIP, "CREDENTIALS_FILE", str(credential)), \
             patch.object(DBMDynIP, "GODADDY_CLI", "/usr/bin/true"), \
             patch.object(Credentials, "provision", side_effect=AssertionError("Use gddy authentication")), \
             patch("sys.stdout", new=io.StringIO()):
            installer.install()
            installer.install(upgrading=True)
            self.assertEqual(credential.read_bytes(), original)
            self.assertEqual(credential.stat().st_mode & 0o777, 0o600)
            executable = install_root / "bin/bmdynip"
            with zipfile.ZipFile(executable) as archive:
                self.assertFalse(any(name.endswith("auto.env") for name in archive.namelist()))
            installer.uninstall()
            self.assertEqual(credential.read_bytes(), original)

    def test_install_does_not_require_a_separate_pat_file(self):
        credential = self.root / "etc/bmdynip/auto.env"
        (self.root / ".godaddy-cli").unlink()
        with patch.object(DBMDynIP, "INSTALL_DIR", str(self.root / "prod")), \
             patch.object(DBMDynIP, "CRON_FILE", str(self.root / "cron")), \
             patch.object(DBMDynIP, "CREDENTIALS_FILE", str(credential)), \
             patch.object(DBMDynIP, "GODADDY_CLI", "/usr/bin/true"), \
             patch.object(Credentials, "godaddy", side_effect=AssertionError("Use gddy authentication")), \
             patch("sys.stdout", new=io.StringIO()):
            installer.install()
        self.assertFalse(credential.exists())
        self.assertTrue((self.root / "cron").exists())

    def test_missing_home_source_is_rejected_even_with_environment_token(self):
        (self.root / ".godaddy-cli").unlink()
        with patch.dict(os.environ, {}, clear=True), \
             patch("sys.stdin.isatty", return_value=False):
            with self.assertRaises(FileNotFoundError):
                Credentials.godaddy()
        with patch.dict(os.environ, {"GDDY_PAT": "gd_pat_test_only"}), \
             patch("getpass.getpass") as prompt:
            with self.assertRaises(FileNotFoundError):
                Credentials.godaddy()
            prompt.assert_not_called()

    def test_source_rotation_refreshes_installed_copy_without_executing_shell(self):
        source = self.root / ".godaddy-cli"
        destination = self.root / "etc/bmdynip/auto.env"
        Credentials.provision(destination, Credentials.godaddy, refresh=True)
        token = "gd_pat_rotated;opaque$()_only"
        source.write_text(token + "\n")
        with patch.dict(os.environ, {"GDDY_PAT": "gd_pat_stale_environment"}):
            Credentials.provision(destination, Credentials.godaddy, refresh=True)
        self.assertEqual(Credentials.load(destination), token)
        self.assertEqual(source.read_text(), token + "\n")
        self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
        self.assertEqual(destination.parent.stat().st_mode & 0o777, 0o700)

    def test_failed_refresh_preserves_installed_copy(self):
        destination = self.root / "etc/bmdynip/auto.env"
        Credentials.provision(destination, Credentials.godaddy, refresh=True)
        original = destination.read_bytes()
        source = self.root / ".godaddy-cli"
        source.write_text("invalid-source-secret\n")
        with self.assertRaises(ValueError) as caught:
            Credentials.provision(destination, Credentials.godaddy, refresh=True)
        self.assertNotIn("invalid-source-secret", str(caught.exception))
        self.assertEqual(destination.read_bytes(), original)
        source.write_text("gd_pat_rotated\n")
        with patch("bmdynip.interface.Credentials.os.replace", side_effect=OSError("publish failed")):
            with self.assertRaises(OSError):
                Credentials.provision(destination, Credentials.godaddy, refresh=True)
        self.assertEqual(destination.read_bytes(), original)
        self.assertEqual(list(destination.parent.iterdir()), [destination])

    def test_existing_invalid_credentials_are_preserved_and_rejected(self):
        credential = self.credentials()
        credential.chmod(0o644)
        source = Mock(return_value="gd_pat_replacement")
        with self.assertRaises(ValueError):
            Credentials.provision(credential, source)
        source.assert_not_called()
        self.assertEqual(credential.read_text(), "GDDY_PAT=gd_pat_test_only\n")

    def test_concurrent_provisioning_requests_only_one_token(self):
        credential = self.root / "etc/bmdynip/auto.env"
        source = Mock(return_value="gd_pat_test_only")
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: Credentials.provision(credential, source), range(8)))
        self.assertEqual(results, ["gd_pat_test_only"] * 8)
        source.assert_called_once_with()
        self.assertEqual(Credentials.load(credential), "gd_pat_test_only")
        self.assertEqual(list(credential.parent.iterdir()), [credential])

    def test_failed_publication_removes_temporary_secret(self):
        credential = self.root / "etc/bmdynip/auto.env"
        with patch("bmdynip.interface.Credentials.os.link", side_effect=OSError("publish failed")):
            with self.assertRaisesRegex(OSError, "publish failed"):
                Credentials.provision(credential, lambda: "gd_pat_test_only")
        self.assertFalse(credential.exists())
        self.assertEqual(list(credential.parent.iterdir()), [])

    def test_symlink_credentials_and_directory_are_rejected(self):
        credential = self.credentials()
        link = self.root / "link.env"
        link.symlink_to(credential)
        source = Mock()
        with self.assertRaises(ValueError):
            Credentials.provision(link, source)
        with self.assertRaises(OSError):
            Credentials.load(link)
        directory = self.root / "linked"
        directory.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            Credentials.provision(directory / "new.env", source)
        source.assert_not_called()

    def test_install_reinstall_uninstall_preserve_configuration_and_data(self):
        install_root = self.root / "prod"
        cron = self.root / "cron"
        credentials = self.credentials()
        with patch.object(DBMDynIP, "INSTALL_DIR", str(install_root)), \
             patch.object(DBMDynIP, "CRON_FILE", str(cron)), \
             patch.object(DBMDynIP, "CREDENTIALS_FILE", str(credentials)), \
             patch.object(DBMDynIP, "GODADDY_CLI", "/usr/bin/true"), \
             patch("sys.stdout", new=io.StringIO()):
            installer.install()
            executable = install_root / "bin/bmdynip"
            output = subprocess.run([str(executable), "--version"], capture_output=True, text=True, check=True, timeout=10)
            self.assertEqual(output.stdout.strip(), DBMDynIP.VERSION)
            web_executable = install_root / "bin/bmdynip-web"
            self.assertEqual(web_executable.stat().st_mode & 0o777, 0o755)
            self.assertEqual(self.service.stat().st_mode & 0o777, 0o644)
            self.assertIn(f"ExecStart={web_executable} --host {DBMDynIP.WEB_HOST} --port {DBMDynIP.WEB_PORT}",
                          self.service.read_text())
            self.systemctl.assert_any_call("enable", self.service.name)
            self.systemctl.assert_any_call("restart", self.service.name)
            self.check_web_archive(web_executable)
            self.assertIn(f"{DBMDynIP.CRON_SCHEDULE} root {executable}", cron.read_text())
            self.assertNotIn("gd_pat", cron.read_text())
            self.assertEqual(cron.stat().st_mode & 0o777, 0o644)
            config = install_root / "conf/bmdynip.json"
            self.assertEqual(config.stat().st_mode & 0o777, 0o600)
            self.assertEqual(Configuration.domain(config), "osoyalce.com")
            custom_config = '{"domain":"example.com","hostnames":["home","vpn"]}\n'
            config.write_text(custom_config)
            state = install_root / "data/state.json"
            state.write_text('{"ip":"8.8.8.8","records":[]}\n')
            installer.install()
            installer.uninstall()
            installer.uninstall()
            self.assertFalse(executable.exists())
            self.assertFalse(web_executable.exists())
            self.assertFalse(self.service.exists())
            self.systemctl.assert_any_call("disable", "--now", self.service.name)
            self.assertFalse(cron.exists())
            self.assertEqual(config.read_text(), custom_config)
            self.assertEqual(state.read_text(), '{"ip":"8.8.8.8","records":[]}\n')
            self.assertTrue(credentials.exists())
            installer.install()
            self.assertTrue(executable.exists())
            self.assertTrue(cron.exists())
            self.assertEqual(config.read_text(), custom_config)

    def check_web_archive(self, executable):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        process = subprocess.Popen(
            ["/usr/bin/python3", "-B", "-c",
             "import sys; sys.path.insert(0, sys.argv[1]); "
             "from bmdynip.constants.DBMDynIP import DBMDynIP; "
             "DBMDynIP.INSTALL_DIR = sys.argv[2]; "
             "DBMDynIP.DATABASE_ENV = sys.argv[2] + '/missing-database.env'; "
             "from bmdynip.server.__main__ import main; "
             "sys.argv = ['bmdynip-web', '--host', '127.0.0.1', '--port', sys.argv[3]]; main()",
             str(executable), str(executable.parents[1]), str(port)],
            cwd=self.root, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        try:
            opener = build_opener(ProxyHandler({}))
            deadline = time.monotonic() + 10
            while True:
                try:
                    with opener.open(f"http://127.0.0.1:{port}/", timeout=1) as response:
                        body = response.read()
                    break
                except (URLError, TimeoutError):
                    if process.poll() is not None or time.monotonic() >= deadline:
                        self.fail("Installed Web UI failed to start.")
                    time.sleep(0.05)
            self.assertIn(DBMDynIP.VERSION.encode(), body)
            for path in ("/static/ui.js", "/static/api.js", "/static/style.css",
                         "/pages/images/bmdynip-logo.png"):
                with opener.open(f"http://127.0.0.1:{port}{path}", timeout=2) as response:
                    self.assertEqual(response.status, 200)
                    self.assertTrue(response.read())
        finally:
            process.terminate()
            process.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
