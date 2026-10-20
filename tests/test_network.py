"""Verify CMDB declarations drive runtime settings and deployment checks."""

import ast
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bmdynip.constants.DBMDynIP import DBMDynIP
from bmdynip.interface.Configuration import Configuration
from bmdynip.interface.Network import Network
from bmdynip.server import __main__ as server


class NetworkTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / 'conf/bmdynip.json'
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(DBMDynIP, 'INSTALL_DIR', str(self.root)))
        self.stack.enter_context(patch.object(DBMDynIP, 'CMDB_NETWORK', (
            ('backend', '127.0.0.2', 19081), ('http', '0.0.0.0', 19080))))

    def write(self, network):
        self.path.parent.mkdir(exist_ok=True)
        self.path.write_text(json.dumps({'domain': 'example.com', 'network': network}))

    def test_missing_file_and_partial_overrides_and_snapshot(self):
        self.assertEqual(Network().binding('http'), ('0.0.0.0', 19080))
        self.assertEqual(Network().destination('http'), ('127.0.0.1', 19080))
        self.write({'http': {'port': 19090}})
        network = Network()
        self.assertEqual(network.binding('http'), ('0.0.0.0', 19090))
        self.assertEqual(network.destination('backend'), ('127.0.0.2', 19081))
        self.write({'http': {'interface': '127.0.0.3'}})
        self.assertEqual(Network().binding('http'), ('127.0.0.3', 19080))
        self.assertEqual(network.binding('http'), ('0.0.0.0', 19090))
        self.assertEqual(Configuration.domain(self.path), 'example.com')

    def test_invalid_overrides_identify_file(self):
        invalid = [None, [], {'unknown': {}}, {'http': []}, {'http': {'host': '127.0.0.1'}}]
        invalid += [{'http': {'port': value}} for value in (True, '19080', 0, 65536, 1.5)]
        invalid += [{'http': {'interface': value}} for value in (None, 123, 'localhost', '::1', '999.0.0.1')]
        for values in invalid:
            with self.subTest(values=values):
                self.write(values)
                with self.assertRaisesRegex(ValueError, str(self.path)):
                    Network()
        self.path.write_text('{')
        with self.assertRaisesRegex(ValueError, str(self.path)):
            Network()

    def test_server_defaults_and_cli_precedence(self):
        self.write({'http': {'port': 19090}})
        for arguments, expected in (([], ('0.0.0.0', 19090)),
                                    (['--host', '127.0.0.4', '--port', '19091'], ('127.0.0.4', 19091))):
            with self.subTest(arguments=arguments), \
                    patch('sys.argv', ['bmdynip-web', *arguments]), \
                    patch.object(server, 'RunnerProcess'), \
                    patch.object(server, 'ThreadingHTTPServer') as listener, \
                    patch('builtins.print'):
                server.main()
                self.assertEqual(listener.call_args.args[0], expected)

    def test_discovery_constants_are_literal_and_components_drive_paths(self):
        path = Path(__file__).resolve().parents[1] / 'bmdynip/constants/DBMDynIP.py'
        declaration = ast.parse(path.read_text()).body[-1]
        values = {node.target.id: ast.literal_eval(node.value)
                  for node in declaration.body if isinstance(node, ast.AnnAssign)}
        for name in ('VERSION', 'CMDB_TYPE', 'CMDB_SUBTYPE', 'CMDB_SUPPLIER', 'CMDB_CODENAME',
                     'CMDB_COMPONENTS', 'CMDB_DATABASES', 'CMDB_NETWORK'):
            self.assertTrue(values[name])
        with patch.object(DBMDynIP, 'CMDB_COMPONENTS', (('Configuration', 'settings'),
                                                     ('Saved state', 'saved'))):
            self.assertEqual(Configuration.path(), self.root / 'settings/bmdynip.json')
            self.assertEqual(Configuration.component('Saved state'), self.root / 'saved')
