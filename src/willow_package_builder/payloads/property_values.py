import struct
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from willow_package_builder.upackage import FName, ReferencePath, serialize_fstring

if TYPE_CHECKING:
    from willow_package_builder.upackage import Package


class PropertyValue(ABC):
    """Serializable property data."""

    @abstractmethod
    def serialize(self, package: Package) -> bytes:
        """Serialize the value."""


@dataclass
class IntValue(PropertyValue):
    value: int

    @override
    def serialize(self, package: Package) -> bytes:
        return struct.pack("<i", self.value)


@dataclass
class FloatValue(PropertyValue):
    value: float

    @override
    def serialize(self, package: Package) -> bytes:
        return struct.pack("<f", self.value)


@dataclass
class ByteValue(PropertyValue):
    value: int

    @override
    def serialize(self, package: Package) -> bytes:
        return struct.pack("<B", self.value)


@dataclass
class BoolValue(PropertyValue):
    value: bool

    @override
    def serialize(self, package: Package) -> bytes:
        return struct.pack("<?", self.value)


@dataclass
class StringValue(PropertyValue):
    value: str

    @override
    def serialize(self, package: Package) -> bytes:
        return serialize_fstring(self.value)


@dataclass
class NameValue(PropertyValue):
    value: FName

    @override
    def serialize(self, package: Package) -> bytes:
        return self.value.serialize(package)


@dataclass
class ObjectReferenceValue(PropertyValue):
    value: ReferencePath

    @override
    def serialize(self, package: Package) -> bytes:
        return self.value.serialize(package)


@dataclass
class ArrayValue(PropertyValue):
    elements: list[PropertyValue]

    @override
    def serialize(self, package: Package) -> bytes:
        return struct.pack("<i", len(self.elements)) + b"".join(
            element.serialize(package) for element in self.elements
        )


@dataclass
class EnumValue(PropertyValue):
    enum_name: FName
    member_name: FName
    index: int

    @override
    def serialize(self, package: Package) -> bytes:
        return struct.pack("<B", self.index)
