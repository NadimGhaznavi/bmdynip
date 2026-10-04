"""A CWM request describing one DNS record change."""

from dataclasses import dataclass, field
from datetime import datetime

from bmdynip.entity.ModelElement import ModelElement


@dataclass
class ChangeRequest(ModelElement):
    changeDescription: str
    changeReason: str
    status: str
    completed: bool
    requestDate: datetime
    completionDate: datetime | None = None
    modelElement: list[int] = field(default_factory=list)
