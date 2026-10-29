"""Run ordered DNS commands and require successful gddy completion."""

import subprocess

from bmdynip.constants.DBMDynIP import DBMDynIP
from bmdynip.entity.DnsRecord import DnsRecord


class GoDaddyCli:
    def replace(self, record: DnsRecord) -> None:
        common = [record.domain, "--type", "A", "--name", record.name,
                  "--env", "prod", "--timeout", "60s"]
        delete = [DBMDynIP.GODADDY_CLI, "dns", "delete", *common]
        add = [DBMDynIP.GODADDY_CLI, "dns", "add", *common, "--data", str(record.address)]
        # The runner already runs separately from the Web UI. Finish each command
        # before saving submission state; failures must remain eligible for retry.
        for command in (delete, add):
            subprocess.run(command, stdin=subprocess.DEVNULL, check=True, timeout=65)
