"""A deployed data provider."""

from dataclasses import dataclass, field

from bmdynip.entity.DataManager import DataManager
from bmdynip.entity.ProviderConnection import ProviderConnection


@dataclass
class DataProvider(DataManager):
    resourceConnection: list[ProviderConnection] = field(default_factory=list)
