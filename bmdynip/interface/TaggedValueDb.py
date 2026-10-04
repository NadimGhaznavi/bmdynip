"""Access CWM tags using bound parameters."""

from bmdynip.interface.DbMgr import DbMgr


class TaggedValueDb:
    def __init__(self, db: DbMgr):
        self.db = db

    def get(self, identity: int, tag: str) -> str | None:
        rows = self.db.query('SELECT value FROM TaggedValue WHERE modelElement=%s AND tag=%s',
                             (identity, tag))
        return rows[0]['value'] if rows else None

    def set(self, identity: int, tag: str, value: str) -> None:
        self.db.execute('INSERT INTO TaggedValue (modelElement, tag, value) VALUES (%s,%s,%s) '
                        'ON DUPLICATE KEY UPDATE value=VALUES(value)', (identity, tag, value))

    def remove(self, identity: int, tag: str) -> None:
        self.db.execute('DELETE FROM TaggedValue WHERE modelElement=%s AND tag=%s', (identity, tag))

    def role(self, role: str) -> int | None:
        rows = self.db.query("SELECT modelElement FROM TaggedValue WHERE tag='BMDynIPRole' AND value=%s",
                             (role,))
        if len(rows) > 1:
            raise ValueError('Duplicate discovery role: ' + role)
        return rows[0]['modelElement'] if rows else None
