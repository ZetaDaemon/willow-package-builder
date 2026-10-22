import struct
from abc import ABC
from dataclasses import dataclass, field
from enum import IntFlag
from typing import override

from payloads.class_payload import UFieldPayload
from upackage import ExternalReference, FName, Package, UObject


class PropertyFlags(IntFlag):
    """PropertyFlags."""

    NONE = 0

    EDIT = 0x00000001
    CONST = 0x00000002
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
    array_enum: UObject | ExternalReference | None = None

    def serialize_body(self, package: Package) -> bytes:
        """Serialize the inherited data and UProperty portion."""
        return b"".join(
            (
                super().serialize_body(package),
                struct.pack("<i", self.array_dimension),
                struct.pack("<Q", int(self.property_flags)),
                self.category.serialize(package),
                struct.pack("<i", package.object_index(self.array_enum)),
            )
        )

    def serialize(self, package: Package) -> bytes:
        """Serialize a complete property definition."""
        if self.property_flags & PropertyFlags.NET:
            msg = "Replicated properties are not supported yet"
            raise ValueError(msg)

        if self.array_dimension < 1:
            msg = "Array dimension must be positive"
            raise ValueError(msg)

        return b"".join(
            (
                struct.pack("<i", self.net_index),
                FName("None").serialize(package),
                self.serialize_body(package),
            )
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

    enum: UObject | ExternalReference | None = None

    @override
    def serialize_body(self, package: Package) -> bytes:
        return super().serialize_body(package) + struct.pack("<i", package.object_index(self.enum))


@dataclass
class UObjectPropertyPayload(UPropertyPayload):
    """Object reference property."""

    property_class: UObject | ExternalReference = field(kw_only=True)

    @override
    def serialize_body(self, package: Package) -> bytes:
        return super().serialize_body(package) + struct.pack(
            "<i", package.object_index(self.property_class)
        )


@dataclass
class UComponentPropertyPayload(UObjectPropertyPayload):
    """Component reference property."""


@dataclass
class UClassPropertyPayload(UObjectPropertyPayload):
    """UnrealScript class<T> property."""

    meta_class: UObject | ExternalReference = field(kw_only=True)

    @override
    def serialize_body(self, package: Package) -> bytes:
        return super().serialize_body(package) + struct.pack(
            "<i", package.object_index(self.meta_class)
        )
