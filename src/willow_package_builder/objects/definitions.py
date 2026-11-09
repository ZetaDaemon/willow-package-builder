from abc import ABC
from dataclasses import KW_ONLY, dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from willow_package_builder.upackage import ReferencePath

if TYPE_CHECKING:
    from pathlib import Path

    from willow_package_builder.handlers.classes.class_handler import ClassHandler
    from willow_package_builder.upackage import FName


class ObjectDefinitionFlag(StrEnum):
    """Optional flags supported by object definitions."""

    PUBLIC = "PUBLIC"
    KEEP_ALIVE = "KEEP_ALIVE"


class ObjectField(StrEnum):
    """Reserved fields in an object definition."""

    NAME = "Name"
    CLASS = "Class"
    OUTER = "Outer"
    FLAGS = "Flags"
    ARCHETYPE = "Archetype"


@dataclass(eq=False)
class Definition(ABC):
    name: FName
    outer: Definition | None
    source: Path

    _: KW_ONLY

    children: list[Definition] = field(default_factory=list)

    @property
    def reference(self) -> ReferencePath:
        if self.outer is None:
            return ReferencePath(self.name)
        return self.outer.reference + self.name


@dataclass(eq=False)
class FolderDefinition(Definition):
    """A folder in the package."""


@dataclass(eq=False)
class ObjectDefinition(Definition):
    class_name: ReferencePath
    properties: dict[FName, object]
    source: Path
    document: int
    flags: frozenset[ObjectDefinitionFlag] = field(default_factory=frozenset)
    archetype: str | None = None

    handler: ClassHandler | None = field(default=None)
