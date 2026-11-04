from abc import ABC
from dataclasses import dataclass, field

from willow_package_builder.upackage import FName, ReferencePath


class Value(ABC):
    """Serializable property data."""


@dataclass
class NullValue(Value): ...


@dataclass
class IntValue(Value):
    value: int = 0


@dataclass
class FloatValue(Value):
    value: float = 0.0


@dataclass
class ByteValue(Value):
    value: int = 0


@dataclass
class BoolValue(Value):
    value: bool = False


@dataclass
class StringValue(Value):
    value: str = ""


@dataclass
class NameValue(Value):
    value: FName = field(default_factory=lambda: FName("None"))


@dataclass
class IdentifierValue(Value):
    name: str


@dataclass
class ObjectValue(Value):
    class_name: str
    path: str

    reference: ReferencePath | None = field(default=None, kw_only=True, repr=False, compare=False)


@dataclass
class ArrayValue(Value):
    elements: list[Value] = field(default_factory=list)


@dataclass
class EmptyValue(Value):
    """Empty parentheses awaiting interpretation for the target property."""


@dataclass
class StructValue(Value):
    values: dict[FName, Value] = field(default_factory=dict)
    struct_path: str | None = field(default=None, kw_only=True)


@dataclass
class EnumValue(Value):
    enum_name: FName
    member_name: FName
    index: int
