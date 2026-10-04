"""Delete and recreate configured A records using gddy."""

import json
import os
import subprocess

from bmdynip.constants.DBMDynIP import DBMDynIP
from bmdynip.entity.DnsRecord import DnsRecord


class GoDaddyCli:
    def __init__(self, token: str):
        self.token = token

    def replace(self, record: DnsRecord) -> None:
        self._run("delete", record)
        self._run("add", record, "--data", str(record.address))

    def _run(self, action: str, record: DnsRecord, *extra: str) -> None:
        command = [DBMDynIP.GODADDY_CLI, "dns", action, record.domain,
                   "--type", "A", "--name", record.name, *extra,
                   "--output", "json", "--timeout", "60s"]
        result = subprocess.run(
            command, env=dict(os.environ, GDDY_PAT=self.token),
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=65,
        )
        context = f"gddy {action} {record.name}.{record.domain}"
        if result.returncode:
            detail = result.stderr.strip().replace(self.token, "[redacted]")
            raise ValueError(f"{context} failed ({result.returncode}): {detail}")
        try:
            data = json.loads(result.stdout)["data"]
            failed = data["failed"]
            count = data["created" if action == "add" else "deleted"]
        except (ValueError, KeyError, TypeError) as error:
            raise ValueError(f"{context} returned an invalid result.") from error
        if type(failed) is not int or type(count) is not int or failed != 0 or count < 0:
            raise ValueError(f"{context} reported a failure; saved IP was not updated.")
        if action == "add" and count != 1:
            raise ValueError(f"{context} did not create exactly one A record.")
