"""A software component, identified through its deployments for now."""

from dataclasses import dataclass, field

from bmdynip.entity.Namespace import Namespace


@dataclass
class Component(Namespace):
    deployment: list[int] = field(default_factory=list)
