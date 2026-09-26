"""Read and validate the configured DNS names."""

import json
from pathlib import Path
import re

from mydynip.entity.DnsRecord import DnsRecord


class Configuration:
    @staticmethod
    def load(path: Path) -> tuple[DnsRecord, ...]:
        data = json.loads(path.read_text())
        if not isinstance(data, dict) or set(data) != {"domain", "hostnames"}:
            raise ValueError("Configuration must contain domain and hostnames.")
        if not isinstance(data["hostnames"], list):
            raise ValueError("Configuration hostnames must be a list.")
        records = []
        label = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
        hostname = rf"{label}(?:\.{label})*"
        domain = data["domain"]
        if not isinstance(domain, str) or not re.fullmatch(hostname, domain) or "." not in domain or len(domain) > 253:
            raise ValueError("Configuration domain must be a lowercase DNS domain.")
        for index, name in enumerate(data["hostnames"]):
            if not isinstance(name, str) or (name != "@" and not re.fullmatch(hostname, name)):
                raise ValueError(f"hostnames[{index}] must be @ or a relative DNS name.")
            full_name = domain if name == "@" else f"{name}.{domain}"
            if len(full_name) > 253:
                raise ValueError(f"hostnames[{index}] exceeds the DNS name length limit.")
            record = DnsRecord(domain, name)
            if record in records:
                raise ValueError(f"hostnames[{index}] duplicates an earlier name.")
            records.append(record)
        return tuple(records)
