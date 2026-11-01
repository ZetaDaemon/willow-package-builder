import struct
from dataclasses import dataclass, field
from typing import override

from willow_package_builder.payloads.property_values import EnumValue, PropertyValue
from willow_package_builder.upackage import FName, ObjectPayload, Package

INDEX_NONE = -1
PROPERTY_LIST_END = FName("None")


@dataclass
class PropertyOverride:
    name: FName
    property_type: FName
    value: PropertyValue
    array_index: int = field(default=0, kw_only=True)

    def serialize_value(self, package: Package) -> bytes:
        """Convert the stored value into bytes."""
        return self.value.serialize(package)

    def serialize_metadata(self, package: Package) -> bytes:  # pyright: ignore[reportUnusedParameter]  # noqa: ARG002
        """Convert the metadata into bytes.

        Not all properties have metadata.
        """
        return b""

    def serialize(self, package: Package) -> bytes:
        """Convert the property override into bytes."""
        value_data = self.serialize_value(package)

        return (
            self.name.serialize(package)
            + self.property_type.serialize(package)
            + struct.pack("<ii", len(value_data), self.array_index)
            + self.serialize_metadata(package)
            + value_data
        )


@dataclass
class BoolPropertyOverride(PropertyOverride):
    @override
    def serialize_metadata(self, package: Package) -> bytes:
        return self.value.serialize(package)

    @override
    def serialize_value(self, package: Package) -> bytes:
        return b""


@dataclass
class EnumPropertyOverride(PropertyOverride):
    def _enum_value(self) -> EnumValue:
        if not isinstance(self.value, EnumValue):
            msg = "EnumPropertyOverride requires an EnumValue"
            raise TypeError(msg)

        return self.value

    @override
    def serialize_metadata(self, package: Package) -> bytes:
        return self._enum_value().enum_name.serialize(package)

    @override
    def serialize_value(self, package: Package) -> bytes:
        return self._enum_value().member_name.serialize(package)


@dataclass
class BytePropertyOverride(PropertyOverride):
    @override
    def serialize_metadata(self, package: Package) -> bytes:
        return FName("None").serialize(package)


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


@dataclass
class StructPropertyOverride(PropertyOverride):
    struct_name: FName

    @override
    def serialize_metadata(self, package: Package) -> bytes:
        return self.struct_name.serialize(package)
