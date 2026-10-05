"""Check a registered hostname through the host's DNS resolver."""

from ipaddress import IPv4Address
import subprocess

from bmdynip.constants.DBMDynIP import DBMDynIP


class DnsLookup:
    def check(self, hostname: str, expected: str | None) -> dict:
        value = {'dnsAddresses': [], 'expectedAddress': expected, 'status': 'Lookup failed'}
        try:
            result = subprocess.run([DBMDynIP.GETENT, '-s', 'dns', 'ahostsv4', hostname],
                                    stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                    timeout=DBMDynIP.DNS_LOOKUP_TIMEOUT)
            if result.returncode == 2:
                return {**value, 'status': 'Not found'}
            if result.returncode:
                return value
            addresses = sorted({str(IPv4Address(line.split()[0]))
                                for line in result.stdout.splitlines() if line.strip()})
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return value
        status = ('Current' if addresses == [expected] else 'Mismatch') if expected else 'Resolved'
        return {**value, 'dnsAddresses': addresses, 'status': status if addresses else 'Not found'}
