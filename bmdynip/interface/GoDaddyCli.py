"""Dispatch ordered DNS commands without waiting for gddy completion."""

import shlex
import subprocess

from bmdynip.constants.DBMDynIP import DBMDynIP
from bmdynip.entity.DnsRecord import DnsRecord


class GoDaddyCli:
    def replace(self, record: DnsRecord) -> None:
        common = [record.domain, "--type", "A", "--name", record.name,
                  "--env", "prod", "--timeout", "60s"]
        delete = [DBMDynIP.GODADDY_CLI, "dns", "delete", *common]
        add = [DBMDynIP.GODADDY_CLI, "dns", "add", *common, "--data", str(record.address)]
        # One detached shell preserves delete-before-add ordering. Output stays
        # with the service log; the parent records submission, not DNS confirmation.
        subprocess.Popen([DBMDynIP.DNS_SHELL, "-c", shlex.join(delete) + " && " + shlex.join(add)],
                         stdin=subprocess.DEVNULL, start_new_session=True)
