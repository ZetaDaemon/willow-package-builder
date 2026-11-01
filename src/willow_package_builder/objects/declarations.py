from dataclasses import dataclass, field
from pathlib import Path


@dataclass(eq=False)
class FolderDeclaration:
    name: str
    outer: FolderDeclaration | ObjectDeclaration | None
    source: Path
    children: list[FolderDeclaration | ObjectDeclaration] = field(default_factory=list)


@dataclass(eq=False)
class ObjectDeclaration:
    name: str
    class_name: str
    outer: FolderDeclaration | ObjectDeclaration | None
    properties: dict[str, object]
    source: Path
    document: int
    children: list[FolderDeclaration | ObjectDeclaration] = field(default_factory=list)
