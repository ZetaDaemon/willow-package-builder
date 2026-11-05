from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class ObjectFlag(StrEnum):
    """Optional flags supported by object definitions."""

    PUBLIC = "PUBLIC"
    KEEP_ALIVE = "KEEP_ALIVE"


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
    flags: frozenset[ObjectFlag] = field(default_factory=frozenset)
