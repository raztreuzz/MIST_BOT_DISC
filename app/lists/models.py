from dataclasses import dataclass, field


@dataclass
class SavedList:
    name: str
    kind: str
    items: list[str] = field(default_factory=list)
