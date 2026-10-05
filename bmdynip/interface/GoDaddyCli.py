"""Delete and recreate configured A records using gddy."""

import json
import re
import subprocess

from bmdynip.constants.DBMDynIP import DBMDynIP
from bmdynip.entity.DnsRecord import DnsRecord


class GoDaddyCli:
    def replace(self, record: DnsRecord) -> None:
        self._run("delete", record)
        self._run("add", record, "--data", str(record.address))

    def _run(self, action: str, record: DnsRecord, *extra: str) -> None:
        command = [DBMDynIP.GODADDY_CLI, "dns", action, record.domain,
                   "--type", "A", "--name", record.name, *extra,
                   "--env", "prod", "--output", "json", "--timeout", "60s"]
        result = subprocess.run(
            command,
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=65,
        )
        context = f"gddy {action} {record.name}.{record.domain}"
        if result.returncode:
            detail = result.stderr.strip()
            try:
                failure = json.loads(detail)
            except ValueError:
                failure = None
            if isinstance(failure, dict) and isinstance(failure.get('error'), dict):
                message = failure['error'].get('message')
                if isinstance(message, str):
                    detail = message
            detail = re.sub(r'gd_pat_\S+', '[redacted]', detail)
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
