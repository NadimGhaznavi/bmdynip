"""Persist application DNS records independently of CWM metadata."""

from ipaddress import IPv4Address
import re

from bmdynip.entity.DnsRecord import DnsRecord
from bmdynip.interface.DbMgr import DbMgr


class DnsRecordDb:
    def __init__(self, db: DbMgr):
        self.db = db

    def list_records(self) -> tuple[DnsRecord, ...]:
        return tuple(DnsRecord(row['domain'], row['name'],
                               IPv4Address(row['address']) if row['address'] else None,
                               id=row['id']) for row in self.db.query(
                                   'SELECT id, domain, name, address FROM DnsRecord ORDER BY domain, name'))

    def add(self, domain: str, name: str) -> int:
        name = name.strip().lower()
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', name):
            raise ValueError('Enter one hostname label, up to 63 characters.')
        if len(name + '.' + domain) > 253:
            raise ValueError('Hostname exceeds the DNS name length limit.')
        return self.db.insert('INSERT INTO DnsRecord (domain, name) VALUES (%s, %s)', (domain, name))

    def remove(self, identity: int) -> bool:
        return bool(self.db.execute('DELETE FROM DnsRecord WHERE id=%s', (identity,)))
