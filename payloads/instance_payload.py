import struct
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar, override

from upackage import FName, ObjectPayload, Package, ReferencePath, serialize_fstring

INDEX_NONE = -1
PROPERTY_LIST_END = FName("None")


@dataclass
class PropertyOverride(ABC):
    name: FName
    array_index: int = field(default=0, kw_only=True)

    PROPERTY_TYPE: ClassVar[str]

    @abstractmethod
    def serialize_value(self, package: Package) -> bytes:
        """Convert the stored value into bytes."""

    def serialize_metadata(self, package: Package) -> bytes:  # pyright: ignore[reportUnusedParameter]  # noqa: ARG002
        """Convert the metadata into bytes.

        Not all properties have metadata so an 'empty' default function is provided,
        rather than an abstract function like serialize_value.
        """
        return b""

    def serialize(self, package: Package) -> bytes:
        """Convert the property override into bytes."""
        value_data = self.serialize_value(package)

        return (
            self.name.serialize(package)
            + FName(self.PROPERTY_TYPE).serialize(package)
            + struct.pack("<ii", len(value_data), self.array_index)
            + self.serialize_metadata(package)
            + value_data
        )


@dataclass
class IntPropertyOverride(PropertyOverride):
    value: int

    PROPERTY_TYPE: ClassVar[str] = "IntProperty"

    @override
    def serialize_value(self, package: Package) -> bytes:
        return struct.pack("<i", self.value)


@dataclass
class FloatPropertyOverride(PropertyOverride):
    value: float

    PROPERTY_TYPE: ClassVar[str] = "FloatProperty"

    @override
    def serialize_value(self, package: Package) -> bytes:
        return struct.pack("<f", self.value)


@dataclass
class StringPropertyOverride(PropertyOverride):
    value: str

    PROPERTY_TYPE: ClassVar[str] = "StrProperty"

    @override
    def serialize_value(self, package: Package) -> bytes:
        return serialize_fstring(self.value)


@dataclass
class NamePropertyOverride(PropertyOverride):
    value: FName

    PROPERTY_TYPE: ClassVar[str] = "NameProperty"

    @override
    def serialize_value(self, package: Package) -> bytes:
        return self.value.serialize(package)


@dataclass
class BoolPropertyOverride(PropertyOverride):
    value: bool

    PROPERTY_TYPE: ClassVar[str] = "BoolProperty"

    @override
    def serialize_metadata(self, package: Package) -> bytes:
        return struct.pack("<?", self.value)

    @override
    def serialize_value(self, package: Package) -> bytes:
        return b""


@dataclass
class EnumPropertyOverride(PropertyOverride):
    enum_name: FName
    value: FName

    PROPERTY_TYPE: ClassVar[str] = "ByteProperty"

    @override
    def serialize_metadata(self, package: Package) -> bytes:
        return self.enum_name.serialize(package)

    @override
    def serialize_value(self, package: Package) -> bytes:
        return self.value.serialize(package)


@dataclass
class ObjectPropertyOverride(PropertyOverride):
    value: ReferencePath

    PROPERTY_TYPE: ClassVar[str] = "ObjectProperty"

    @override
    def serialize_value(self, package: Package) -> bytes:
        return self.value.serialize(package)


@dataclass
class ObjectArrayPropertyOverride(PropertyOverride):
    values: list[ReferencePath]

    PROPERTY_TYPE: ClassVar[str] = "ArrayProperty"

    @override
    def serialize_value(self, package: Package) -> bytes:
        return struct.pack("<i", len(self.values)) + b"".join(
            value.serialize(package) for value in self.values
        )


@dataclass
class ClassPropertyOverride(ObjectPropertyOverride):
    PROPERTY_TYPE: ClassVar[str] = "ClassProperty"


@dataclass
class ObjectInstancePayload(ObjectPayload):
    net_index: int = INDEX_NONE
    properties: list[PropertyOverride] = field(default_factory=list)

    @override
    def serialize(self, package: Package) -> bytes:
        return (
            struct.pack("<i", self.net_index)
            + b"".join(prop.serialize(package) for prop in self.properties)
            + PROPERTY_LIST_END.serialize(package)
        )
