"""Dispatch changed public addresses and remember their submission."""

from dataclasses import replace
import subprocess

from bmdynip.entity.DnsRecord import DnsRecord
from bmdynip.interface.GoDaddyCli import GoDaddyCli
from bmdynip.interface.IpState import IpState
from bmdynip.interface.PublicIpService import PublicIpService


class UpdatePublicIp:
    def __init__(self, public_ip: PublicIpService, dns: GoDaddyCli, state: IpState, audit=None, messages=None):
        self.public_ip = public_ip
        self.dns = dns
        self.state = state
        self.audit = audit
        self.messages = messages

    def run(self, records: tuple[DnsRecord, ...]) -> bool:
        if not records:
            return False
        if self.messages:
            self.messages.append('Checking public IPv4 discovery services.')
        address = self.public_ip.current_address()
        if self.messages:
            self.messages.append(f'Public IPv4 discovery services agree on {address}.')
        if self.audit:
            self.audit.observe(address)
        if self.state.is_current(address, records) and (not self.audit or
                                                       all(r.address == address for r in records)):
            if self.messages:
                self.messages.append('All hostnames have been submitted at this address; no DNS update needed.')
            return False
        for record in records:
            hostname = record.domain if record.name == '@' else record.name + '.' + record.domain
            request = self.audit.begin(record, address) if self.audit else None
            if self.messages:
                self.messages.append(f'Updating {hostname} A record to {address}.')
            try:
                self.dns.replace(replace(record, address=address))
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                if self.audit:
                    self.audit.failed(request, str(error))
                if self.messages:
                    self.messages.append(f'DNS update failed for {hostname}: {error}. '
                                         'saved state is preserved for retry.')
                raise
            if self.audit:
                self.audit.submitted(request)
            if self.messages:
                self.messages.append(f'DNS update submitted for {hostname}.')
        if self.audit:
            self.audit.applied(records, address, submitted=True)
        self.state.save(address, records)
        if self.messages:
            self.messages.append(f'Saved submitted update state for {len(records)} hostname(s) at {address}.')
        print(f"Submitted {len(records)} A record(s) to {address}.")
        return True
