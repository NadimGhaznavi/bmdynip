"""A connection owned by a deployed DataProvider."""

from dataclasses import dataclass

from bmdynip.entity.ModelElement import ModelElement


@dataclass
class ProviderConnection(ModelElement):
    dataProvider: int
    dataManager: int
    isReadOnly: bool
