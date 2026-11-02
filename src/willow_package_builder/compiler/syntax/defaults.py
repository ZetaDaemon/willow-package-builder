from abc import ABC
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from willow_package_builder.logging import SourceLocation


class DefaultValue(ABC):
    """Base for values written in default property blocks."""


@dataclass
class LiteralDefaultValue(DefaultValue):
    value: bool | int | float | str | None


@dataclass
class DefaultAssignment:
    name: str
    value: DefaultValue
    location: SourceLocation
    array_index: int | None = None


@dataclass
class StructDefaultValue(DefaultValue):
    fields: list[DefaultAssignment]


@dataclass
class NameDefaultValue(DefaultValue):
    value: str


@dataclass
class IdentifierDefaultValue(DefaultValue):
    name: str


@dataclass
class ObjectDefaultValue(DefaultValue):
    class_name: str
    path: str


@dataclass
class ArrayDefaultValue(DefaultValue):
    elements: list[DefaultValue]


@dataclass
class EmptyDefaultValue(DefaultValue):
    """Empty parentheses; the property's type determines their meaning."""
