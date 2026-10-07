"""Read and validate the configured DNS domain."""

import json
from pathlib import Path
import re


class Configuration:
    @staticmethod
    def domain(path: Path) -> str:
        data = json.loads(path.read_text())
        if not isinstance(data, dict) or 'domain' not in data or set(data) - {'domain', 'hostnames'}:
            raise ValueError("Configuration must contain a domain.")
        # Existing installations may retain the obsolete hostnames field.
        label = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
        hostname = rf"{label}(?:\.{label})*"
        domain = data['domain']
        if not isinstance(domain, str) or not re.fullmatch(hostname, domain) or "." not in domain or len(domain) > 253:
            raise ValueError("Configuration domain must be a lowercase DNS domain.")
        return domain
