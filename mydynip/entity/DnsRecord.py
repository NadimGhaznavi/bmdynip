"""An A record managed by MyDynIP."""

from dataclasses import dataclass
from ipaddress import IPv4Address


@dataclass(frozen=True)
class DnsRecord:
    domain: str
    name: str
    address: IPv4Address | None = None
