"""Read application configuration and resolve declared component paths."""

import json
from pathlib import Path
import re

from bmdynip.constants.DBMDynIP import DBMDynIP


class Configuration:
    @staticmethod
    def component(name: str) -> Path:
        return Path(DBMDynIP.INSTALL_DIR) / dict(DBMDynIP.CMDB_COMPONENTS)[name]

    @staticmethod
    def path() -> Path:
        return Configuration.component("Configuration") / "bmdynip.json"

    @staticmethod
    def read(path: Path) -> dict:
        try:
            data = json.loads(path.read_text())
        except (ValueError, UnicodeError) as error:
            raise ValueError(f"Invalid configuration {path}: {error}") from None
        if not isinstance(data, dict) or set(data) - {'domain', 'hostnames', 'network'}:
            raise ValueError(f"Invalid configuration fields in {path}.")
        return data

    @staticmethod
    def domain(path: Path) -> str:
        data = Configuration.read(path)
        if 'domain' not in data:
            raise ValueError("Configuration must contain a domain.")
        # Existing installations may retain the obsolete hostnames field.
        label = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
        hostname = rf"{label}(?:\.{label})*"
        domain = data['domain']
        if not isinstance(domain, str) or not re.fullmatch(hostname, domain) or "." not in domain or len(domain) > 253:
            raise ValueError("Configuration domain must be a lowercase DNS domain.")
        return domain
