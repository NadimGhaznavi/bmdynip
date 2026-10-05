"""Verify one-time JSON import and recovery against a disposable database."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import json
import os
import unittest
from unittest.mock import Mock, patch

from pymysql import OperationalError

from bmdynip.constants.DBMDynIP import DBMDynIP
from bmdynip.interface.Configuration import Configuration
from bmdynip.interface.DatabaseProvisioning import DatabaseProvisioning
from bmdynip.interface.DnsRecordDb import DnsRecordDb
from bmdynip.interface.RunnerSchedule import RunnerSchedule
from test_control_api import LiveControlFixture
import test_upgrade as upgrade_tests

installer = upgrade_tests.installer


class MigrationBoundaryTests(unittest.TestCase):
    def test_invalid_configuration_does_not_open_database(self):
        with patch.object(Configuration, 'load', side_effect=ValueError('Invalid configuration')), \
                patch('bmdynip.app.database.open_database') as factory:
            with self.assertRaisesRegex(ValueError, 'Invalid configuration'):
                installer.migrate_configuration(None)
        factory.assert_not_called()

    def test_database_error_closes_connection_and_keeps_diagnostics_private(self):
        db = Mock()
        with patch.object(Configuration, 'load', return_value=()), \
                patch('bmdynip.app.database.open_database', return_value=db), \
                patch.object(DnsRecordDb, 'import_configuration',
                             side_effect=OperationalError(2006, 'private driver diagnostics')):
            with self.assertRaisesRegex(ValueError, 'Could not migrate') as caught:
                installer.migrate_configuration(None)
        db.close.assert_called_once()
        self.assertNotIn('private', str(caught.exception))


@unittest.skipUnless(os.environ.get('BMDYNIP_TEST_DB_SOCKET'),
                     'Set BMDYNIP_TEST_DB_SOCKET for database checks')
class LiveMigrationTests(LiveControlFixture):
    def configuration(self, names):
        path = self.root / 'legacy.json'
        path.write_text(json.dumps({'domain': 'example.test', 'hostnames': names}) + '\n')
        path.chmod(0o600)
        return path

    def migrate(self, path):
        with patch.object(DBMDynIP, 'DATABASE_ENV', str(self.root / 'config/database.env')):
            installer.migrate_configuration(path)

    def names(self):
        return {row['name'] for row in self.request()[1]['records']}

    def test_import_preserves_legacy_apex_nested_names_and_source(self):
        path = self.configuration(['home', '@', 'nested.name'])
        original = path.read_bytes()
        self.migrate(path)
        self.assertEqual(self.names(), {'home', '@', 'nested.name'})
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_existing_addresses_history_and_ui_edits_survive_repeat_import(self):
        self.seed_history()
        before = self.request()[1]
        path = self.configuration(['existing', 'home'])
        self.migrate(path)
        snapshot = self.request()[1]
        existing = next(row for row in snapshot['records'] if row['name'] == 'existing')
        self.assertEqual(existing, before['records'][0])
        self.assertEqual(snapshot['messages'], before['messages'])
        home = next(row for row in snapshot['records'] if row['name'] == 'home')
        self.assertEqual(self.request('/api/records/' + str(home['id']), method='DELETE')[0], 200)
        self.assertEqual(self.request('/api/records', method='POST', value={'name': 'ui-added'})[0], 201)
        self.migrate(path)
        self.assertEqual(self.names(), {'existing', 'ui-added'})

    def test_empty_import_is_completed_and_later_json_edits_do_not_override_ui(self):
        path = self.configuration([])
        self.migrate(path)
        self.configuration(['later'])
        self.migrate(path)
        self.assertEqual(self.names(), set())

    def test_partial_import_rolls_back_marker_and_names_then_retries(self):
        path = self.configuration(['first', 'second'])
        records = Configuration.load(path)
        db = self.open_database()
        try:
            execute = db.execute
            def fail_second(sql, params=()):
                if params == ('example.test', 'second'):
                    raise OperationalError(2013, 'test-only interrupted migration')
                return execute(sql, params)
            with patch.object(db, 'execute', side_effect=fail_second):
                with self.assertRaises(OperationalError):
                    DnsRecordDb(db).import_configuration(records)
            self.assertEqual(db.query('SELECT name FROM ApplicationMigration'), [])
            self.assertEqual(db.query('SELECT name FROM DnsRecord'), [])
        finally:
            db.close()
        self.migrate(path)
        self.assertEqual(self.names(), {'first', 'second'})

    def test_concurrent_imports_commit_only_once(self):
        records = Configuration.load(self.configuration(['home', '@']))
        def migrate():
            db = self.open_database()
            try:
                return DnsRecordDb(db).import_configuration(records)
            finally:
                db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: migrate(), range(2)))
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(self.names(), {'home', '@'})

    def test_upgrade_imports_before_stop_and_preserves_ui_deletion_on_repeat(self):
        root = self.root / 'prod'
        (root / 'conf').mkdir(parents=True)
        config = root / 'conf/bmdynip.json'
        config.write_bytes(self.configuration(['home', '@']).read_bytes())
        original = config.read_bytes()
        cron = self.root / 'installed-cron'
        with ExitStack() as stack:
            for name, value in {
                'INSTALL_DIR': str(root),
                'DATABASE_ENV': str(self.root / 'config/database.env'),
                'WEB_SERVICE_FILE': str(self.root / 'bmdynip-web.service'),
                'CRON_FILE': str(cron),
                'GODADDY_CLI': '/usr/bin/true',
            }.items():
                stack.enter_context(patch.object(DBMDynIP, name, value))
            stack.enter_context(patch.object(installer.Credentials, 'provision'))
            stack.enter_context(patch.object(DatabaseProvisioning, '_require_root'))
            stack.enter_context(patch.object(RunnerSchedule, '_require_root'))
            stack.enter_context(patch.object(installer, 'install_dependencies',
                                             side_effect=upgrade_tests.UpgradeDeploymentTests.stage_dependency))
            opener = stack.enter_context(patch.object(installer, 'build_opener')).return_value
            opener.open.return_value.__enter__.return_value.status = 200
            control = stack.enter_context(patch.object(installer, 'systemctl'))
            def before_stop(action, *arguments):
                if action == 'stop':
                    self.assertEqual(self.names(), {'home', '@'})
            control.side_effect = before_stop
            installer.upgrade()
            self.assertEqual(config.read_bytes(), original)
            home = next(row for row in self.request()[1]['records'] if row['name'] == 'home')
            self.request('/api/records/' + str(home['id']), method='DELETE')
            control.side_effect = None
            installer.upgrade()
            self.assertEqual(self.names(), {'@'})
            self.assertEqual(config.read_bytes(), original)
            self.assertEqual(config.stat().st_mode & 0o777, 0o600)
            self.assertEqual(cron.stat().st_mode & 0o777, 0o644)
