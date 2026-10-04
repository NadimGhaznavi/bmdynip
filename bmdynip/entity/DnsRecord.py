"""An A record managed by BMDynIP."""

from dataclasses import dataclass, field
from ipaddress import IPv4Address


@dataclass(frozen=True)
class DnsRecord:
    domain: str
    name: str
    address: IPv4Address | None = None
    id: int | None = field(default=None, kw_only=True)
