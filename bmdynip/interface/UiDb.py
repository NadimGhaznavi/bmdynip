"""Read a consistent UI snapshot from application records and CWM history."""

from datetime import timezone

from bmdynip.interface.DnsRecordDb import DnsRecordDb
from bmdynip.interface.TaggedValueDb import TaggedValueDb


class UiDb:
    def __init__(self, db):
        self.db = db

    def snapshot(self, domain: str) -> dict:
        with self.db.transaction(read_only=True):
            tags = TaggedValueDb(self.db)
            connection = tags.role('wan')
            current = tags.get(connection, 'publicIpAddress') if connection else None
            state = {key: tags.get(connection, key) if connection else None
                     for key in ('lastCheckedOn', 'lastAppliedOn', 'lastSubmittedOn', 'lastError')}
            submitted = state['lastSubmittedOn'] and (not state['lastAppliedOn'] or
                                                      state['lastSubmittedOn'] > state['lastAppliedOn'])
            records = []
            for record in DnsRecordDb(self.db).list_records():
                hostname = record.domain if record.name == '@' else record.name + '.' + record.domain
                records.append({'id': record.id, 'name': record.name, 'hostname': hostname,
                                'address': str(record.address) if record.address else None,
                                'status': ('Submitted' if submitted else 'Current')
                                if current and str(record.address) == current else 'Pending'})
            messages = []
            for row in self.db.query(
                    'SELECT cr.requestDate, cr.changeDescription, cr.status, error.value AS error '
                    'FROM ChangeRequest cr LEFT JOIN TaggedValue error '
                    "ON error.modelElement=cr.id AND error.tag='error' ORDER BY cr.id DESC LIMIT 100"):
                messages.append({'timestamp': row['requestDate'].replace(tzinfo=timezone.utc).isoformat(),
                                 'source': 'bmdynip.interface.PublicIpDb',
                                 'message': row['changeDescription'] + ' — ' + row['status'] +
                                 (': ' + row['error'] if row['error'] else '')})
            return {'domain': domain, 'publicIp': current, 'records': records, 'messages': messages,
                    **state}
