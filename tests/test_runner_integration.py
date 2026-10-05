"""Exercise the runner and control API together with real database persistence."""

from contextlib import ExitStack
import importlib
import io
from ipaddress import IPv4Address
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import Mock, patch

from pymysql import OperationalError

from bmdynip.activity.sources.HostSource import HostSource
from bmdynip.activity.sources.NetworkSource import NetworkSource
from bmdynip.constants.DBMDynIP import DBMDynIP
from bmdynip.interface.Credentials import Credentials
from bmdynip.interface.GoDaddyCli import GoDaddyCli
from bmdynip.interface.IpState import IpState
from bmdynip.interface.PublicIpService import PublicIpService
from bmdynip.interface.RunnerProcess import RunnerProcess
from bmdynip.interface.StatusMessages import StatusMessages
from test_control_api import LiveControlFixture


runner = importlib.import_module('bmdynip.app.main')


@unittest.skipUnless(os.environ.get('BMDYNIP_TEST_DB_SOCKET'),
                     'Set BMDYNIP_TEST_DB_SOCKET for database checks')
class LiveRunnerTests(LiveControlFixture):
    def setUp(self):
        super().setUp()
        self.runtime = self.root / 'runtime'
        (self.runtime / 'data').mkdir(parents=True)
        self.server.state_directory = self.runtime / 'data'
        self.state = IpState(self.server.state_directory)
        token = self.root / 'auto.env'
        token.write_text('GDDY_PAT=gd_pat_test_only\n')
        token.chmod(0o600)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name, value in {
            'INSTALL_DIR': str(self.runtime),
            'DATABASE_ENV': str(self.root / 'config/database.env'),
            'CREDENTIALS_FILE': str(token),
        }.items():
            self.stack.enter_context(patch.object(DBMDynIP, name, value))
        self.stack.enter_context(patch.object(runner, 'os', Mock(geteuid=Mock(return_value=0))))
        self.stack.enter_context(patch('sys.argv', ['bmdynip']))
        self.stdout = self.stack.enter_context(patch('sys.stdout', new=io.StringIO()))
        self.stderr = self.stack.enter_context(patch('sys.stderr', new=io.StringIO()))
        self.network = self.stack.enter_context(patch.object(NetworkSource, 'collect', return_value={
            'address': '192.0.2.10', 'gateway': '192.0.2.1', 'interface': 'test0',
            'mac': '02:00:00:00:00:10', 'gateway_mac': '02:00:00:00:00:01'}))
        self.stack.enter_context(patch.object(HostSource, 'collect', return_value={
            'hostname': 'test-host', 'system': {'ID': 'test'}}))
        self.public_ip = self.stack.enter_context(patch.object(
            PublicIpService, 'current_address', return_value=IPv4Address('8.8.8.8')))
        self.dns = self.stack.enter_context(patch.object(GoDaddyCli, 'replace'))

    def add(self, name):
        status, value = self.request('/api/records', 'POST', {'name': name})
        self.assertEqual(status, 201)
        return value['id']

    @staticmethod
    def dns_history(snapshot):
        return [entry for entry in snapshot['messages']
                if entry['source'] == 'bmdynip.interface.PublicIpDb']

    def test_ui_names_run_persist_and_unchanged_run_skips_dns(self):
        home = self.add('home')
        self.assertEqual(runner.main(), 0)
        first = self.request()[1]
        self.assertEqual(first['publicIp'], '8.8.8.8')
        self.assertEqual(first['records'][0]['status'], 'Submitted')
        self.assertTrue(first['lastCheckedOn'] and first['lastSubmittedOn'])
        self.assertEqual(len(self.dns_history(first)), 1)
        self.assertIn('submitted', self.dns_history(first)[0]['message'])
        steps = [entry['message'] for entry in reversed(first['messages'])
                 if entry['source'] != 'bmdynip.interface.PublicIpDb']
        self.assertIn('Added home.example.test; starting the runner.', steps)
        self.assertLess(steps.index('Checking public IPv4 discovery services.'),
                        steps.index('Updating home.example.test A record to 8.8.8.8.'))
        self.assertLess(steps.index('DNS update submitted for home.example.test.'),
                        steps.index('Runner complete.'))
        saved = self.state.path.read_bytes()
        self.assertEqual(runner.main(), 0)
        self.assertEqual(self.dns.call_count, 1)
        self.assertEqual(self.state.path.read_bytes(), saved)
        second = self.request()[1]
        self.assertEqual(self.dns_history(second), self.dns_history(first))
        self.assertTrue(any('no DNS update needed' in entry['message'] for entry in second['messages']))
        self.add('vpn')
        self.assertEqual(runner.main(), 0)
        self.assertEqual(self.dns.call_count, 3)
        before = self.request()[1]
        self.assertTrue(all(row['status'] == 'Submitted' for row in before['records']))
        self.assertEqual(self.request('/api/records/' + str(home), 'DELETE')[0], 200)
        self.assertEqual(self.request()[1]['messages'], before['messages'])

    def test_partial_failure_preserves_state_and_retries_pending_request(self):
        self.add('first')
        self.add('second')
        self.assertEqual(runner.main(), 0)
        saved = self.state.path.read_bytes()
        applied = self.request()[1]['lastSubmittedOn']
        self.public_ip.return_value = IPv4Address('1.1.1.1')
        self.dns.side_effect = [None, ValueError('test provider failure')]
        self.assertEqual(runner.main(), 1)
        failed = self.request()[1]
        self.assertEqual(self.state.path.read_bytes(), saved)
        self.assertEqual(failed['lastSubmittedOn'], applied)
        self.assertIn('test provider failure', failed['lastError'])
        self.assertTrue(any('DNS update failed' in entry['message'] and
                            'test provider failure' in entry['message'] for entry in failed['messages']))
        self.assertIn('test provider failure', failed['messages'][0]['message'])
        self.assertTrue(all(row['address'] == '8.8.8.8' and row['status'] == 'Pending'
                            for row in failed['records']))
        db = self.open_database()
        try:
            pending = db.query("SELECT id FROM ChangeRequest WHERE status='failed'")[0]['id']
        finally:
            db.close()
        self.dns.side_effect = None
        self.assertEqual(runner.main(), 0)
        recovered = self.request()[1]
        self.assertIsNone(recovered['lastError'])
        self.assertTrue(all(row['status'] == 'Submitted' for row in recovered['records']))
        db = self.open_database()
        try:
            self.assertEqual(db.query('SELECT status, completed FROM ChangeRequest WHERE id=%s', (pending,)),
                             [{'status': 'submitted', 'completed': 0}])
        finally:
            db.close()

    def test_invalid_discovery_preserves_dns_history_and_saved_state(self):
        self.add('home')
        self.assertEqual(runner.main(), 0)
        saved = self.state.path.read_bytes()
        history = self.dns_history(self.request()[1])
        self.public_ip.side_effect = ValueError('Public IP services disagree')
        self.assertEqual(runner.main(), 1)
        self.assertEqual(self.dns.call_count, 1)
        self.assertEqual(self.state.path.read_bytes(), saved)
        snapshot = self.request()[1]
        self.assertEqual(self.dns_history(snapshot), history)
        self.assertIn('Runner failed', snapshot['messages'][0]['message'])
        self.assertIn('Public IP services disagree', snapshot['messages'][0]['message'])
        self.network.side_effect = ValueError('Invalid route')
        self.assertEqual(runner.main(), 1)
        self.assertEqual(self.dns.call_count, 1)

    def test_empty_database_observes_ip_without_token_or_dns_changes(self):
        with patch.object(Credentials, 'load') as token:
            self.assertEqual(runner.main(), 0)
        token.assert_not_called()
        self.dns.assert_not_called()
        snapshot = self.request()[1]
        self.assertEqual(snapshot['publicIp'], '8.8.8.8')
        self.assertEqual(snapshot['records'], [])
        self.assertEqual(self.dns_history(snapshot), [])
        self.assertIn('no hostnames to update', snapshot['messages'][0]['message'])
        self.assertIsNone(snapshot['lastAppliedOn'])
        self.assertFalse(self.state.path.exists())

    def test_runner_lock_blocks_ui_changes_but_allows_live_status(self):
        self.add('home')
        def updating(record):
            self.assertEqual(self.request('/api/records', 'POST', {'name': 'blocked'})[0], 409)
            self.assertEqual(self.request()[0], 200)
        self.dns.side_effect = updating
        self.assertEqual(runner.main(), 0)
        with self.state.lock():
            with patch.object(runner, 'open_database') as factory:
                self.assertEqual(runner.main(), 0)
            factory.assert_not_called()
        self.assertEqual(self.request('/api/records', 'POST', {'name': 'after'})[0], 201)

    def test_database_failure_has_clear_exit_and_no_dns_calls(self):
        with patch.object(runner, 'open_database', side_effect=OperationalError(2006, 'private diagnostics')):
            self.assertEqual(runner.main(), 1)
        self.assertIn('Database operation failed', self.stderr.getvalue())
        self.assertNotIn('private diagnostics', self.stderr.getvalue())
        self.dns.assert_not_called()

    def test_add_launches_background_runner_and_updates_live_status(self):
        executable = self.runtime / 'bin/bmdynip'
        executable.parent.mkdir()
        dns_calls = self.root / 'dns-calls'
        source_root = str(Path(__file__).resolve().parents[1])
        executable.write_text(f'''#!{sys.executable}
import importlib
from ipaddress import IPv4Address
from pathlib import Path
import sys
from types import SimpleNamespace
sys.path.insert(0, {source_root!r})
from bmdynip.constants.DBMDynIP import DBMDynIP
DBMDynIP.INSTALL_DIR = {str(self.runtime)!r}
DBMDynIP.DATABASE_ENV = {str(self.root / 'config/database.env')!r}
DBMDynIP.CREDENTIALS_FILE = {str(self.root / 'auto.env')!r}
from bmdynip.activity.sources.NetworkSource import NetworkSource
from bmdynip.activity.sources.HostSource import HostSource
from bmdynip.interface.PublicIpService import PublicIpService
from bmdynip.interface.GoDaddyCli import GoDaddyCli
NetworkSource.collect = lambda self: {{'address': '192.0.2.10', 'gateway': '192.0.2.1', 'interface': 'test0', 'mac': None, 'gateway_mac': None}}
HostSource.collect = lambda self: {{'hostname': 'test-host', 'system': {{'ID': 'test'}}}}
PublicIpService.current_address = lambda self: IPv4Address('8.8.8.8')
GoDaddyCli.replace = lambda self, record: Path({str(dns_calls)!r}).write_text(record.name)
runner = importlib.import_module('bmdynip.app.main')
runner.os = SimpleNamespace(geteuid=lambda: 0, umask=lambda value: None)
raise SystemExit(runner.main())
''')
        executable.chmod(0o755)
        process = RunnerProcess(StatusMessages(self.server.state_directory / DBMDynIP.STATUS_MESSAGES_FILE))
        self.addCleanup(process.close)
        self.server.start_runner = process.start
        status, saved = self.request('/api/records', 'POST', {'name': 'immediate'})
        self.assertEqual(status, 201)
        self.assertTrue(saved['runnerStarted'])
        deadline = time.monotonic() + 10
        while True:
            snapshot = self.request()[1]
            if snapshot['records'][0]['status'] == 'Submitted':
                break
            if time.monotonic() >= deadline:
                self.fail('Immediate runner did not update the saved hostname')
            time.sleep(0.05)
        self.assertEqual(dns_calls.read_text(), 'immediate')
        self.assertIn('submitted', self.dns_history(snapshot)[0]['message'])
        self.assertTrue(any(entry['source'] == 'bmdynip.activity.UpdatePublicIp' and
                            'DNS update submitted' in entry['message'] for entry in snapshot['messages']))
        self.assertTrue(self.state.path.exists())
