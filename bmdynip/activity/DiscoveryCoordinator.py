"""Sequence runtime discovery and persist observations in one short transaction."""

from bmdynip.activity.sources.HostSource import HostSource
from bmdynip.activity.sources.NetworkSource import NetworkSource
from bmdynip.interface.DiscoveryDb import DiscoveryDb


class DiscoveryCoordinator:
    def __init__(self, network=None, host=None):
        self.network = network or NetworkSource()
        self.host = host or HostSource()

    def run(self, db) -> int:
        network = self.network.collect()
        host = self.host.collect()
        with db.transaction():
            return DiscoveryDb(db).reconcile(network, host)
