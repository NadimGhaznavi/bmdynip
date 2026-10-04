"""Reconcile observed runtime objects and explicitly marked ISP placeholders."""

from bmdynip.interface.DbMgr import DbMgr
from bmdynip.interface.NamespaceDb import NamespaceDb
from bmdynip.interface.TaggedValueDb import TaggedValueDb


class DiscoveryDb:
    def __init__(self, db: DbMgr):
        self.db = db
        self.tags = TaggedValueDb(db)
        self.namespaces = NamespaceDb(db)

    def _identity(self, role: str, name: str, *, namespace=None, package=False) -> tuple[int, bool]:
        identity = self.tags.role(role)
        if identity is not None:
            return identity, False
        identity = (self.namespaces.create_package(namespace, name=name) if package
                    else self.namespaces.create(namespace, name=name))
        self.tags.set(identity, 'BMDynIPRole', role)
        return identity, True

    def _machine(self, role, name, address, hostname=None, mac=None, placeholder=False):
        identity, created = self._identity(role, name)
        if created:
            self.db.execute('INSERT INTO Machine (id, ipAddress, hostName, macAddress) VALUES (%s,%s,%s,%s)',
                            (identity, address, hostname, mac))
        else:
            self.db.execute('UPDATE Machine SET ipAddress=%s, hostName=COALESCE(%s,hostName), '
                            'macAddress=COALESCE(%s,macAddress), updatedOn=UTC_TIMESTAMP(6) WHERE id=%s',
                            (address, hostname, mac, identity))
        if placeholder:
            self.tags.set(identity, 'placeholder', 'true')
        return identity

    def _deployment(self, role, name, machine, *, provider=False):
        software, created = self._identity(role + '-software', name, package=True)
        if created:
            self.db.execute('INSERT INTO SoftwareSystem (id) VALUES (%s)', (software,))
        component, created = self._identity(role + '-component', name, namespace=software)
        if created:
            self.db.execute('INSERT INTO Component (id) VALUES (%s)', (component,))
        deployment, created = self._identity(role, name, namespace=machine, package=True)
        if created:
            self.db.execute('INSERT INTO DeployedComponent (id, pathname, machine, component) '
                            'VALUES (%s,%s,%s,%s)', (deployment, 'placeholder', machine, component))
            self.db.execute('INSERT INTO DataManager (id) VALUES (%s)', (deployment,))
            if provider:
                self.db.execute('INSERT INTO DataProvider (id) VALUES (%s)', (deployment,))
        # Firmware and upstream deployments are not observed by LAN routing commands.
        for identity in (software, component, deployment):
            self.tags.set(identity, 'placeholder', 'true')
        return deployment

    def reconcile(self, network: dict, host: dict) -> int:
        """Called inside the coordinator's transaction and process lock."""
        local = self._machine('local-host', host['hostname'], network['address'],
                              host['hostname'], network['mac'])
        for key, value in host['system'].items():
            self.tags.set(local, key, value)
        router = self._machine('router', 'LAN router', network['gateway'],
                               mac=network['gateway_mac']) if network['gateway'] else local
        provider = self._deployment('wan-client', 'WAN client', router, provider=True)
        upstream = self._machine('isp-machine', 'ISP placeholder', '0.0.0.0', placeholder=True)
        manager = self._deployment('isp', 'TekSavvy', upstream)
        self.tags.set(manager, 'type', 'ISP')
        connection = self.tags.role('wan')
        if connection is None:
            connection = self.db.insert('INSERT INTO ModelElement (name, namespace) VALUES (%s,%s)',
                                        ('WAN', provider))
            self.db.execute('INSERT INTO ProviderConnection (id, isReadOnly, dataProvider, dataManager) '
                            'VALUES (%s,FALSE,%s,%s)', (connection, provider, manager))
            self.tags.set(connection, 'BMDynIPRole', 'wan')
        self.tags.set(connection, 'interface', network['interface'])
        return connection
