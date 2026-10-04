"""Store observed WAN state and per-record CWM change requests."""

from datetime import datetime, timezone
from ipaddress import IPv4Address

from bmdynip.interface.DbMgr import DbMgr
from bmdynip.interface.TaggedValueDb import TaggedValueDb


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PublicIpDb:
    def __init__(self, db: DbMgr, connection: int):
        self.db = db
        self.connection = connection
        self.tags = TaggedValueDb(db)

    def observe(self, address: IPv4Address) -> None:
        with self.db.transaction():
            self.tags.set(self.connection, 'publicIpAddress', str(address))
            self.tags.set(self.connection, 'lastCheckedOn', utc_now())

    def begin(self, record, address: IPv4Address) -> int:
        hostname = record.domain if record.name == '@' else record.name + '.' + record.domain
        with self.db.transaction():
            self.db.query('SELECT id FROM ModelElement WHERE id=%s FOR UPDATE', (self.connection,))
            pending = self.db.query(
                'SELECT cr.id, ip.value FROM ChangeRequest cr '
                'JOIN ModelElementChangeRequest link ON link.changeRequest=cr.id '
                "JOIN TaggedValue host ON host.modelElement=cr.id AND host.tag='hostname' "
                "JOIN TaggedValue ip ON ip.modelElement=cr.id AND ip.tag='newIpAddress' "
                'WHERE link.modelElement=%s AND host.value=%s AND cr.completed=FALSE ORDER BY cr.id',
                (self.connection, hostname))
            for request in pending:
                if request['value'] == str(address):
                    return request['id']
                self.db.execute("UPDATE ChangeRequest SET completed=TRUE, status='rejected', "
                                'completionDate=UTC_TIMESTAMP(6) WHERE id=%s', (request['id'],))
            identity = self.db.insert('INSERT INTO ModelElement (name) VALUES (%s)', (hostname,))
            self.db.execute('INSERT INTO ChangeRequest '
                            '(id, changeDescription, changeReason, status, requestDate) '
                            "VALUES (%s,%s,%s,'proposed',UTC_TIMESTAMP(6))",
                            (identity, f'Update {hostname} from {record.address or "unknown"} to {address}',
                             'Synchronize DNS with the observed public IPv4 address'))
            self.db.execute('INSERT INTO ModelElementChangeRequest (modelElement, changeRequest, position) '
                            'VALUES (%s,%s,%s)', (self.connection, identity, identity))
            self.tags.set(identity, 'hostname', hostname)
            self.tags.set(identity, 'newIpAddress', str(address))
            if record.address:
                self.tags.set(identity, 'previousIpAddress', str(record.address))
            return identity

    def succeeded(self, identity: int) -> None:
        with self.db.transaction():
            self.db.execute("UPDATE ChangeRequest SET status='implemented', completed=TRUE, "
                            'completionDate=UTC_TIMESTAMP(6) WHERE id=%s', (identity,))
            self.tags.remove(identity, 'error')

    def failed(self, identity: int, error: str) -> None:
        with self.db.transaction():
            self.db.execute("UPDATE ChangeRequest SET status='failed' WHERE id=%s", (identity,))
            self.tags.set(identity, 'error', error)
            self.tags.set(self.connection, 'lastError', error)

    def applied(self, records, address: IPv4Address) -> None:
        with self.db.transaction():
            for record in records:
                self.db.execute('UPDATE DnsRecord SET address=%s WHERE id=%s', (str(address), record.id))
            self.tags.set(self.connection, 'lastAppliedOn', utc_now())
            self.tags.remove(self.connection, 'lastError')
