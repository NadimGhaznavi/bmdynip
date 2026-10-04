"""Discover the public IPv4 address using both configured services."""

from ipaddress import IPv4Address
import subprocess

from bmdynip.constants.DBMDynIP import DBMDynIP


class PublicIpService:
    def current_address(self) -> IPv4Address:
        addresses = []
        for url in DBMDynIP.PUBLIC_IP_URLS:
            result = subprocess.run(
                ["/usr/bin/curl", "-4", "--fail", "--silent", "--show-error",
                 "--connect-timeout", "10", "--max-time", "20", url],
                stdin=subprocess.DEVNULL, capture_output=True, text=True,
                check=True, timeout=25,
            )
            address = IPv4Address(result.stdout.strip())
            if not address.is_global or address.is_multicast:
                raise ValueError(f"{url} did not return a public unicast IPv4 address.")
            addresses.append(address)
        if addresses[0] != addresses[1]:
            raise ValueError("Public IP services disagree; DNS was not changed.")
        return addresses[0]
