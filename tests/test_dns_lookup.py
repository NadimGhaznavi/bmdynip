"""Verify DNS-derived status independently of saved submission state."""

import subprocess
import unittest
from unittest.mock import Mock, patch

from bmdynip.constants.DBMDynIP import DBMDynIP
from bmdynip.interface.DnsLookup import DnsLookup


class DnsLookupTests(unittest.TestCase):
    def test_matching_a_records_ignore_duplicate_socket_types(self):
        output = '8.8.8.8 STREAM home.example.test\n8.8.8.8 DGRAM\n8.8.8.8 RAW\n'
        with patch('bmdynip.interface.DnsLookup.subprocess.run',
                   return_value=Mock(returncode=0, stdout=output)) as run:
            value = DnsLookup().check('home.example.test', '8.8.8.8')
        self.assertEqual(value, {'dnsAddresses': ['8.8.8.8'], 'expectedAddress': '8.8.8.8',
                                 'status': 'Current'})
        self.assertEqual(run.call_args.args[0],
                         [DBMDynIP.GETENT, '-s', 'dns', 'ahostsv4', 'home.example.test'])
        self.assertEqual(run.call_args.kwargs['timeout'], DBMDynIP.DNS_LOOKUP_TIMEOUT)

    def test_different_or_extra_addresses_are_mismatches(self):
        for output in ('1.1.1.1 STREAM home\n', '8.8.8.8 STREAM home\n1.1.1.1 STREAM home\n'):
            with self.subTest(output=output), patch('bmdynip.interface.DnsLookup.subprocess.run',
                    return_value=Mock(returncode=0, stdout=output)):
                self.assertEqual(DnsLookup().check('home.example.test', '8.8.8.8')['status'], 'Mismatch')

    def test_missing_records_and_unknown_expected_address(self):
        for result in (Mock(returncode=2), Mock(returncode=0, stdout='')):
            with patch('bmdynip.interface.DnsLookup.subprocess.run', return_value=result):
                self.assertEqual(DnsLookup().check('home.example.test', '8.8.8.8')['status'], 'Not found')
        with patch('bmdynip.interface.DnsLookup.subprocess.run',
                   return_value=Mock(returncode=0, stdout='8.8.8.8 STREAM home\n')):
            self.assertEqual(DnsLookup().check('home.example.test', None)['status'], 'Resolved')

    def test_timeout_and_resolver_failures_do_not_claim_a_match(self):
        for error in (subprocess.TimeoutExpired('getent', 3), FileNotFoundError('getent missing')):
            with patch('bmdynip.interface.DnsLookup.subprocess.run', side_effect=error):
                self.assertEqual(DnsLookup().check('home.example.test', '8.8.8.8')['status'], 'Lookup failed')
        for result in (Mock(returncode=1), Mock(returncode=0, stdout='not-an-ip STREAM home\n')):
            with patch('bmdynip.interface.DnsLookup.subprocess.run', return_value=result):
                self.assertEqual(DnsLookup().check('home.example.test', '8.8.8.8')['status'], 'Lookup failed')
