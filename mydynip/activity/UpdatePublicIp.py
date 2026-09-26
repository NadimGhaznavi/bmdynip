"""Apply a changed public address and remember it only after success."""

from dataclasses import replace

from mydynip.entity.DnsRecord import DnsRecord
from mydynip.interface.GoDaddyCli import GoDaddyCli
from mydynip.interface.IpState import IpState
from mydynip.interface.PublicIpService import PublicIpService


class UpdatePublicIp:
    def __init__(self, public_ip: PublicIpService, dns: GoDaddyCli, state: IpState):
        self.public_ip = public_ip
        self.dns = dns
        self.state = state

    def run(self, records: tuple[DnsRecord, ...]) -> bool:
        if not records:
            return False
        address = self.public_ip.current_address()
        if self.state.is_current(address, records):
            return False
        for record in records:
            self.dns.replace(replace(record, address=address))
        self.state.save(address, records)
        print(f"Updated {len(records)} A record(s) to {address}.")
        return True
