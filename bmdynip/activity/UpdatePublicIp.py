"""Apply a changed public address and remember it only after success."""

from dataclasses import replace
import subprocess

from bmdynip.entity.DnsRecord import DnsRecord
from bmdynip.interface.GoDaddyCli import GoDaddyCli
from bmdynip.interface.IpState import IpState
from bmdynip.interface.PublicIpService import PublicIpService


class UpdatePublicIp:
    def __init__(self, public_ip: PublicIpService, dns: GoDaddyCli, state: IpState, audit=None):
        self.public_ip = public_ip
        self.dns = dns
        self.state = state
        self.audit = audit

    def run(self, records: tuple[DnsRecord, ...]) -> bool:
        if not records:
            return False
        address = self.public_ip.current_address()
        if self.audit:
            self.audit.observe(address)
        if self.state.is_current(address, records) and (not self.audit or
                                                       all(r.address == address for r in records)):
            return False
        for record in records:
            request = self.audit.begin(record, address) if self.audit else None
            try:
                self.dns.replace(replace(record, address=address))
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                if self.audit:
                    self.audit.failed(request, str(error))
                raise
            if self.audit:
                self.audit.succeeded(request)
        if self.audit:
            self.audit.applied(records, address)
        self.state.save(address, records)
        print(f"Updated {len(records)} A record(s) to {address}.")
        return True
