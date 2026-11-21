from abc import ABC
from dataclasses import dataclass, field
from typing import Self

from willow_package_builder.upackage import NONE_NAME, FName, ReferencePath


class Value(ABC):
    """Serializable property data."""


class ImmutableValue(Value):
    """Property value that can be shared safely when copying."""

    def __deepcopy__(self, memo: dict[int, object]) -> Self:
        return self


@dataclass(frozen=True)
class NullValue(ImmutableValue): ...


@dataclass(frozen=True)
class IntValue(ImmutableValue):
    value: int = 0


@dataclass(frozen=True)
class FloatValue(ImmutableValue):
    value: float = 0.0


@dataclass(frozen=True)
class ByteValue(ImmutableValue):
    value: int = 0


@dataclass(frozen=True)
class BoolValue(ImmutableValue):
    value: bool = False


@dataclass(frozen=True)
class StringValue(ImmutableValue):
    value: str = ""


@dataclass(frozen=True)
class NameValue(ImmutableValue):
    value: FName = field(default_factory=lambda: NONE_NAME)


@dataclass(frozen=True)
class IdentifierValue(ImmutableValue):
    name: ReferencePath


@dataclass
class ObjectValue(Value):
    class_name: ReferencePath
    path: ReferencePath

    reference: ReferencePath | None = field(default=None, kw_only=True, repr=False, compare=False)


@dataclass
class ArrayValue(Value):
    elements: list[Value] = field(default_factory=list)


@dataclass(frozen=True)
class EmptyValue(ImmutableValue):
    """Empty parentheses awaiting interpretation for the target property."""


@dataclass
class StructValue(Value):
    values: dict[FName, Value] = field(default_factory=dict)
    struct_path: ReferencePath | None = field(default=None, kw_only=True)


@dataclass(frozen=True)
class EnumValue(ImmutableValue):
    enum_name: FName
    member_name: FName
    index: int


@dataclass(frozen=True)
class DelegateValue(ImmutableValue):
    target: ReferencePath = field(default_factory=ReferencePath)
    function_name: FName = field(default_factory=lambda: NONE_NAME)
