import importlib.util
import io
from ipaddress import IPv4Address
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from bmdynip.activity.UpdatePublicIp import UpdatePublicIp
from bmdynip.app.main import main
from bmdynip.constants.DBMDynIP import DBMDynIP
from bmdynip.entity.DnsRecord import DnsRecord
from bmdynip.interface.Configuration import Configuration
from bmdynip.interface.Credentials import Credentials
from bmdynip.interface.GoDaddyCli import GoDaddyCli
from bmdynip.interface.IpState import IpState
from bmdynip.interface.PublicIpService import PublicIpService


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
        self.activity = UpdatePublicIp(self.public_ip, self.dns, self.state)

    def test_first_update_then_unchanged(self):
        with patch("sys.stdout", new=io.StringIO()):
            self.assertTrue(self.activity.run(RECORDS))
            self.assertFalse(self.activity.run(RECORDS))
        self.dns.replace.assert_called_once_with(DnsRecord("example.com", "api", IP))
        self.assertTrue(self.state.is_current(IP, RECORDS))

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
    def test_configuration_resolves_domain_and_names(self):
        path = self.root / "config.json"
        path.write_text(json.dumps({"domain": "example.com", "hostnames": ["@", "home", "vpn"]}))
        self.assertEqual(Configuration.load(path), tuple(DnsRecord("example.com", name) for name in ("@", "home", "vpn")))

    def test_bad_configuration_is_rejected(self):
        path = self.root / "config.json"
        for data in ({}, {"domain": "example.com", "hostnames": "api"},
                     {"domain": "--help", "hostnames": ["api"]},
                     {"domain": "example.com", "hostnames": ["bad name"]},
                     {"domain": "example.com", "hostnames": ["api", "api"]}):
            with self.subTest(data=data):
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    Configuration.load(path)

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

    def test_godaddy_delete_add_contract_and_token_environment(self):
        results = [Mock(returncode=0, stdout=json.dumps({"data": {"failed": 0, "deleted": 0}})),
                   Mock(returncode=0, stdout=json.dumps({"data": {"failed": 0, "created": 1}}))]
        with patch("subprocess.run", side_effect=results) as run:
            GoDaddyCli("gd_pat_test_only").replace(DnsRecord("example.com", "api", IP))
        self.assertEqual([c.args[0][2] for c in run.call_args_list], ["delete", "add"])
        for call in run.call_args_list:
            self.assertEqual(call.kwargs["env"]["GDDY_PAT"], "gd_pat_test_only")
            self.assertNotIn("gd_pat_test_only", " ".join(call.args[0]))
            self.assertEqual(call.kwargs["stdin"], subprocess.DEVNULL)
        self.assertIn("8.8.8.8", run.call_args.args[0])

    def test_reported_partial_failure_stops_before_add(self):
        with patch("subprocess.run", return_value=Mock(returncode=0, stdout='{"data":{"failed":1,"deleted":0}}')) as run:
            with self.assertRaises(ValueError):
                GoDaddyCli("gd_pat_test_only").replace(DnsRecord("example.com", "api", IP))
            self.assertEqual(run.call_count, 1)

    def test_error_redacts_token(self):
        with patch("subprocess.run", return_value=Mock(returncode=1, stderr="failed gd_pat_test_only")):
            with self.assertRaises(ValueError) as caught:
                GoDaddyCli("gd_pat_test_only").replace(DnsRecord("example.com", "api", IP))
        self.assertNotIn("gd_pat_test_only", str(caught.exception))

    def test_invalid_success_result_is_rejected(self):
        for output in ("not json", '{"data":{"failed":0}}', '{"data":{"failed":false,"deleted":0}}'):
            with self.subTest(output=output), patch("subprocess.run", return_value=Mock(returncode=0, stdout=output)):
                with self.assertRaises(ValueError):
                    GoDaddyCli("gd_pat_test_only").replace(DnsRecord("example.com", "api", IP))

    def test_cli_end_to_end_and_failure_exit(self):
        (self.root / "conf").mkdir()
        (self.root / "data").mkdir()
        (self.root / "conf/bmdynip.json").write_text('{"domain":"example.com","hostnames":["api"]}')
        credential = self.credentials()
        outputs = [Mock(stdout="8.8.8.8"), Mock(stdout="8.8.8.8"),
                   Mock(returncode=0, stdout='{"data":{"failed":0,"deleted":1}}'),
                   Mock(returncode=0, stdout='{"data":{"failed":0,"created":1}}')]
        with patch.object(DBMDynIP, "INSTALL_DIR", str(self.root)), \
             patch.object(DBMDynIP, "CREDENTIALS_FILE", str(credential)), \
             patch("bmdynip.app.main.os", Mock(geteuid=Mock(return_value=0))), \
             patch("sys.argv", ["bmdynip"]), patch("sys.stdout", new=io.StringIO()), \
             patch("sys.stderr", new=io.StringIO()):
            with patch("subprocess.run", side_effect=outputs):
                self.assertEqual(main(), 0)
            saved = (self.root / "data/state.json").read_bytes()
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("curl", 25)):
                self.assertEqual(main(), 1)
            self.assertEqual((self.root / "data/state.json").read_bytes(), saved)


class InstallationTests(TemporaryFiles):
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
            output = subprocess.run([str(executable), "--version"], capture_output=True, text=True, check=True)
            self.assertEqual(output.stdout.strip(), DBMDynIP.VERSION)
            self.assertIn(f"{DBMDynIP.CRON_SCHEDULE} root {executable}", cron.read_text())
            self.assertNotIn("gd_pat", cron.read_text())
            self.assertEqual(cron.stat().st_mode & 0o777, 0o644)
            config = install_root / "conf/bmdynip.json"
            self.assertEqual(config.stat().st_mode & 0o777, 0o600)
            self.assertEqual(Configuration.load(config), ())
            custom_config = '{"domain":"example.com","hostnames":["home","vpn"]}\n'
            config.write_text(custom_config)
            state = install_root / "data/state.json"
            state.write_text('{"ip":"8.8.8.8","records":[]}\n')
            installer.install()
            installer.uninstall()
            installer.uninstall()
            self.assertFalse(executable.exists())
            self.assertFalse(cron.exists())
            self.assertEqual(config.read_text(), custom_config)
            self.assertEqual(state.read_text(), '{"ip":"8.8.8.8","records":[]}\n')
            self.assertTrue(credentials.exists())
            installer.install()
            self.assertTrue(executable.exists())
            self.assertTrue(cron.exists())
            self.assertEqual(config.read_text(), custom_config)


if __name__ == "__main__":
    unittest.main()
