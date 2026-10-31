import struct
from abc import ABC
from dataclasses import KW_ONLY, dataclass, field
from enum import IntFlag
from typing import ClassVar, override

from willow_package_builder.upackage import FName, Package, ReferencePath

from .class_payload import UFieldPayload


class PropertyFlags(IntFlag):
    """PropertyFlags."""

    NONE = 0

    EDIT = 0x00000001
    CONST = 0x00000002
    OPTIONAL_PARAM = 0x00000010
    NET = 0x00000020
    PARAM = 0x00000080
    OUT_PARAM = 0x00000100
    RETURN_PARAM = 0x00000400
    NEED_CTOR_LINK = 0x00400000


@dataclass
class UPropertyPayload(UFieldPayload, ABC):
    """Shared payload for property definitions."""

    net_index: int = -1
    array_dimension: int = 1
    property_flags: PropertyFlags = PropertyFlags.NONE
    category: FName = field(default_factory=lambda: FName("None"))
    array_enum: ReferencePath = field(default_factory=ReferencePath)

    @override
    def serialize_body(self, package: Package) -> bytes:
        """Serialize the inherited data and UProperty portion."""
        return (
            super().serialize_body(package)
            + struct.pack("<i", self.array_dimension)
            + struct.pack("<Q", int(self.property_flags))
            + self.category.serialize(package)
            + self.array_enum.serialize(package)
        )

    @override
    def serialize(self, package: Package) -> bytes:
        """Serialize a complete property definition."""
        if self.property_flags & PropertyFlags.NET:
            msg = "Replicated properties are not supported yet"
            raise ValueError(msg)

        if self.array_dimension < 1:
            msg = "Array dimension must be positive"
            raise ValueError(msg)

        return (
            struct.pack("<i", self.net_index)
            + FName("None").serialize(package)
            + self.serialize_body(package)
        )


@dataclass
class UIntPropertyPayload(UPropertyPayload):
    """Signed UnrealScript int."""


@dataclass
class UFloatPropertyPayload(UPropertyPayload):
    """UnrealScript float."""


@dataclass
class UBoolPropertyPayload(UPropertyPayload):
    """UnrealScript bool."""


@dataclass
class UNamePropertyPayload(UPropertyPayload):
    """UnrealScript name."""


@dataclass
class UStrPropertyPayload(UPropertyPayload):
    """UnrealScript string."""


@dataclass
class UBytePropertyPayload(UPropertyPayload):
    """Byte or enum property."""

    enum: ReferencePath = field(default_factory=ReferencePath)

    @override
    def serialize_body(self, package: Package) -> bytes:
        return super().serialize_body(package) + self.enum.serialize(package)


@dataclass
class UObjectPropertyPayload(UPropertyPayload):
    """Object reference property."""

    _: KW_ONLY
    property_class: ReferencePath

    required_fields: ClassVar[tuple[str, ...]] = ("property_class",)

    @override
    def serialize_body(self, package: Package) -> bytes:
        return super().serialize_body(package) + self.property_class.serialize(package)


@dataclass
class UComponentPropertyPayload(UObjectPropertyPayload):
    """Component reference property."""


@dataclass
class UClassPropertyPayload(UObjectPropertyPayload):
    """UnrealScript class<T> property."""

    _: KW_ONLY
    meta_class: ReferencePath

    required_fields: ClassVar[tuple[str, ...]] = ("meta_class",)

    @override
    def serialize_body(self, package: Package) -> bytes:
        return super().serialize_body(package) + self.meta_class.serialize(package)


@dataclass
class UInterfacePropertyPayload(UPropertyPayload):
    """Interface reference property."""

    _: KW_ONLY
    interface_class: ReferencePath

    required_fields: ClassVar[tuple[str, ...]] = ("interface_class",)

    @override
    def serialize_body(self, package: Package) -> bytes:
        return super().serialize_body(package) + self.interface_class.serialize(package)


@dataclass
class UArrayPropertyPayload(UPropertyPayload):
    """Dynamic array property."""

    _: KW_ONLY
    inner: ReferencePath

    required_fields: ClassVar[tuple[str, ...]] = ("inner",)

    @override
    def serialize_body(self, package: Package) -> bytes:
        return super().serialize_body(package) + self.inner.serialize(package)


@dataclass
class UMapPropertyPayload(UPropertyPayload):
    """Map property definition."""

    _: KW_ONLY
    key: ReferencePath = field(default_factory=ReferencePath)
    value: ReferencePath = field(default_factory=ReferencePath)

    required_fields: ClassVar[tuple[str, ...]] = ("key", "value")

    @override
    def serialize_body(self, package: Package) -> bytes:
        return (
            super().serialize_body(package)
            + self.key.serialize(package)
            + self.value.serialize(package)
        )


@dataclass
class UStructPropertyPayload(UPropertyPayload):
    """Struct property definition."""

    _: KW_ONLY
    struct: ReferencePath

    required_fields: ClassVar[tuple[str, ...]] = ("struct",)

    @override
    def serialize_body(self, package: Package) -> bytes:
        return super().serialize_body(package) + self.struct.serialize(package)


@dataclass
class UDelegatePropertyPayload(UPropertyPayload):
    """Delegate property definition."""

    source_delegate: ReferencePath = field(default_factory=ReferencePath)

    _: KW_ONLY

    function: ReferencePath = field(default_factory=ReferencePath)

    required_fields: ClassVar[tuple[str, ...]] = ("function",)

    @override
    def serialize_body(self, package: Package) -> bytes:
        return (
            super().serialize_body(package)
            + self.function.serialize(package)
            + self.source_delegate.serialize(package)
        )
