"""Observe the active IPv4 route and available neighbor identities."""

from ipaddress import IPv4Address
import json
import re
import subprocess

from bmdynip.constants.DBMDynIP import DBMDynIP


class NetworkSource:
    def collect(self) -> dict:
        routes = self._read('-4', 'route', 'get', DBMDynIP.ROUTE_TARGET)
        if len(routes) != 1 or routes[0].get('type') in ('unreachable', 'blackhole', 'prohibit'):
            raise ValueError('Unable to determine the active IPv4 route.')
        route = routes[0]
        source = str(IPv4Address(route['prefsrc']))
        gateway = str(IPv4Address(route['gateway'])) if route.get('gateway') else None
        interface = route['dev']
        addresses = self._read('address', 'show', 'dev', interface)
        local_mac = self._mac(addresses[0].get('address')) if addresses else None
        gateway_mac = None
        if gateway:
            neighbors = self._read('neigh', 'show', 'to', gateway, 'dev', interface)
            gateway_mac = next((self._mac(item.get('lladdr')) for item in neighbors
                                if self._mac(item.get('lladdr'))), None)
        return {'address': source, 'gateway': gateway, 'interface': interface,
                'mac': local_mac, 'gateway_mac': gateway_mac}

    @staticmethod
    def _mac(value: str | None) -> str | None:
        if value and re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', value):
            return value.upper() if value != '00:00:00:00:00:00' else None
        return None

    @staticmethod
    def _read(*arguments: str) -> list[dict]:
        result = subprocess.run([DBMDynIP.IP_COMMAND, '-j', *arguments],
                                text=True, capture_output=True, check=True,
                                timeout=DBMDynIP.DISCOVERY_TIMEOUT)
        data = json.loads(result.stdout)
        if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
            raise ValueError('Invalid network discovery response.')
        return data
