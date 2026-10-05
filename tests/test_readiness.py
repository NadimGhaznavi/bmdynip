"""Verify database readiness and bounded startup checks without production services."""

import http.client
import io
import json
import os
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from pymysql import OperationalError

from bmdynip.constants.DBMDynIP import DBMDynIP
from bmdynip.interface.DatabaseEnvironment import DatabaseEnvironment
from bmdynip.interface.DbMgr import DbMgr
from bmdynip.interface.UiDb import UiDb
from test_control_api import LiveControlFixture
import test_control_api as control_tests
import test_upgrade as upgrade_tests


class ReadinessRequestTests(unittest.TestCase):
    def test_snapshot_is_checked_and_connection_closed(self):
        fixture = control_tests.ApiRequestTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        with patch.object(UiDb, 'snapshot', return_value={}) as snapshot:
            self.assertEqual(fixture.request(DBMDynIP.WEB_READY_PATH, 'HEAD'), (200, {'ready': True}))
        snapshot.assert_called_once_with('example.test')
        fixture.db.close.assert_called_once()

    def test_failed_snapshot_is_not_ready_and_connection_closed(self):
        fixture = control_tests.ApiRequestTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        with patch.object(UiDb, 'snapshot', side_effect=OperationalError(1146, 'private table diagnostic')):
            self.assertEqual(fixture.request(DBMDynIP.WEB_READY_PATH, 'GET'),
                             (503, {'error': 'Database unavailable.'}))
        fixture.db.close.assert_called_once()


class StartupReadinessTests(unittest.TestCase):
    def setUp(self):
        self.installer = upgrade_tests.installer
        self.control = Mock()
        self.opener = Mock()
        self.response = self.opener.open.return_value
        self.response.__enter__ = Mock(return_value=Mock(status=200))
        self.response.__exit__ = Mock(return_value=False)

    def start(self):
        with patch.object(self.installer, 'systemctl', self.control), \
                patch.object(self.installer, 'build_opener', return_value=self.opener):
            self.installer.start_web('start')

    def test_temporary_database_failure_retries_before_success(self):
        error = HTTPError('http://localhost/ready', 503, 'Unavailable', {}, io.BytesIO(b'private diagnostics'))
        self.opener.open.side_effect = [error, self.response]
        with patch.object(self.installer.time, 'sleep'), patch('sys.stdout', new=io.StringIO()) as output:
            self.start()
        self.assertEqual(self.opener.open.call_count, 2)
        self.assertTrue(error.fp.closed)
        self.assertIn('active on port', output.getvalue())
        for call in self.opener.open.call_args_list:
            self.assertTrue(call.args[0].full_url.endswith(DBMDynIP.WEB_READY_PATH))
            self.assertEqual(call.args[0].get_method(), 'HEAD')

    def test_database_timeout_does_not_report_success(self):
        self.opener.open.side_effect = HTTPError('http://localhost/ready', 503, 'Unavailable', {}, None)
        with patch.object(self.installer.time, 'monotonic', side_effect=[0, 11]), \
                patch('sys.stdout', new=io.StringIO()) as output:
            with self.assertRaisesRegex(ValueError, 'database availability, credentials, and schema'):
                self.start()
        self.assertEqual(output.getvalue(), '')

    def test_missing_endpoint_fails_with_no_false_success(self):
        self.opener.open.side_effect = HTTPError('http://localhost/ready', 404, 'Not found', {}, None)
        with patch('sys.stdout', new=io.StringIO()) as output:
            with self.assertRaisesRegex(ValueError, 'readiness returned HTTP 404'):
                self.start()
        self.assertEqual(output.getvalue(), '')
        self.opener.open.assert_called_once()


@unittest.skipUnless(os.environ.get('BMDYNIP_TEST_DB_SOCKET'),
                     'Set BMDYNIP_TEST_DB_SOCKET for database checks')
class LiveReadinessTests(LiveControlFixture):
    def ready(self, method='HEAD'):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            connection.request(method, DBMDynIP.WEB_READY_PATH)
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def test_empty_database_and_failed_updater_are_ready(self):
        self.assertEqual(self.ready(), (200, b''))
        self.assertEqual(json.loads(self.ready('GET')[1]), {'ready': True})
        self.seed_history(failed=True)
        self.assertEqual(self.ready(), (200, b''))

    def test_database_outage_is_not_ready_while_static_page_still_loads(self):
        self.server.db_failure = True
        self.assertEqual(self.request('/')[0], 200)
        self.assertEqual(self.ready(), (503, b''))
        self.server.db_failure = False
        self.assertEqual(self.ready(), (200, b''))

    def test_missing_history_table_is_not_ready(self):
        self.admin(f'RENAME TABLE `{self.database}`.ChangeRequest TO `{self.database}`.UnavailableHistory;')
        try:
            self.assertEqual(self.ready(), (503, b''))
        finally:
            self.admin(f'RENAME TABLE `{self.database}`.UnavailableHistory TO `{self.database}`.ChangeRequest;')
        self.assertEqual(self.ready(), (200, b''))

    def test_unsafe_credentials_are_not_ready(self):
        credentials = self.root / 'config/database.env'
        self.server.db_factory = lambda: DbMgr(DatabaseEnvironment.read(credentials))
        credentials.chmod(0o644)
        self.assertEqual(self.ready(), (503, b''))
        credentials.chmod(0o600)
        self.assertEqual(self.ready(), (200, b''))

    def test_startup_uses_live_readiness_and_waits_for_recovery(self):
        installer = upgrade_tests.installer
        self.server.db_failure = True
        checks = 0
        def systemctl(action, *arguments):
            nonlocal checks
            if action == 'is-active':
                checks += 1
                if checks == 2:
                    self.server.db_failure = False
        with patch.object(DBMDynIP, 'WEB_PORT', self.server.server_port), \
                patch.object(installer, 'systemctl', side_effect=systemctl), \
                patch('sys.stdout', new=io.StringIO()) as output:
            installer.start_web('start')
        self.assertEqual(checks, 2)
        self.assertIn('active on port', output.getvalue())
