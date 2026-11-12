import struct
from abc import ABC
from dataclasses import KW_ONLY, dataclass, field
from enum import IntFlag
from typing import ClassVar, override

from willow_package_builder.upackage import NONE_NAME, FName, Package, ReferencePath

from .class_payload import UFieldPayload


class PropertyFlags(IntFlag):
    """PropertyFlags."""

    # fmt: off
    NONE                 = 0x0

    EDIT                 = 0x1
    CONST                = 0x2
    INPUT                = 0x4
    EXPORT_OBJECT        = 0x8
    OPTIONAL_PARAM       = 0x10
    NET                  = 0x20
    EDIT_FIXED_SIZE      = 0x40
    PARAM                = 0x80
    OUT_PARAM            = 0x100
    SKIP_PARAM           = 0x200
    RETURN_PARAM         = 0x400
    COERCE_PARAM         = 0x800
    NATIVE               = 0x1000
    TRANSIENT            = 0x2000
    CONFIG               = 0x4000
    LOCALIZED            = 0x8000
    EDIT_CONST           = 0x20000
    GLOBAL_CONFIG        = 0x40000
    COMPONENT            = 0x80000
    ALWAYS_INIT          = 0x100000
    DUPLICATE_TRANSIENT  = 0x200000
    NEED_CTOR_LINK       = 0x400000
    NO_EXPORT            = 0x800000
    NO_IMPORT            = 0x1000000
    NO_CLEAR             = 0x2000000
    EDIT_INLINE          = 0x4000000
    ED_FINDABLE          = 0x8000000
    EDIT_INLINE_USE      = 0x10000000
    DEPRECATED           = 0x20000000
    DATA_BINDING         = 0x40000000
    SERIALIZE_TEXT       = 0x80000000
    REP_NOTIFY           = 0x100000000
    INTERP               = 0x200000000
    NON_TRANSACTIONAL    = 0x400000000
    EDITOR_ONLY          = 0x800000000
    NOT_FOR_CONSOLE      = 0x1000000000
    REP_RETRY            = 0x2000000000
    PRIVATE_WRITE        = 0x4000000000
    PROTECTED_WRITE      = 0x8000000000
    ARCHETYPE_PROPERTY   = 0x10000000000
    EDIT_HIDE            = 0x20000000000
    EDIT_TEXT_BOX        = 0x40000000000
    CROSS_LEVEL_PASSIVE  = 0x100000000000
    CROSS_LEVEL_ACTIVE   = 0x200000000000

    # Gearbox attribute properties.
    ATTRIBUTE_BASE_VALUE = 0x4000000000000000
    ATTRIBUTE_VALUE      = 0x8000000000000000

    CROSS_LEVEL          = CROSS_LEVEL_PASSIVE | CROSS_LEVEL_ACTIVE
    DEVELOPMENT_ASSETS   = EDITOR_ONLY | NOT_FOR_CONSOLE


# fmt: on


@dataclass
class UPropertyPayload(UFieldPayload, ABC):
    """Shared payload for property definitions."""

    net_index: int = -1
    array_dimension: int = 1
    property_flags: PropertyFlags = PropertyFlags.NONE
    category: FName = field(default_factory=lambda: NONE_NAME)
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
            + NONE_NAME.serialize(package)
            + self.serialize_body(package)
        )


@dataclass
class UIntPropertyPayload(UPropertyPayload):
    """Signed UnrealScript int."""


@dataclass
class UBytePropertyPayload(UPropertyPayload):
    """Byte or enum property."""

    enum: ReferencePath = field(default_factory=ReferencePath)

    @override
    def serialize_body(self, package: Package) -> bytes:
        return super().serialize_body(package) + self.enum.serialize(package)


@dataclass
class UFloatPropertyPayload(UPropertyPayload):
    """UnrealScript float."""


@dataclass
class UBoolPropertyPayload(UPropertyPayload):
    """UnrealScript bool."""


@dataclass
class UNumericAttributePropertyPayload(UPropertyPayload):
    """Serialized property definition shared by float and int attributes."""

    modifier_stack: ReferencePath = field(default_factory=ReferencePath)
    related_property: ReferencePath = field(default_factory=ReferencePath)

    required_fields: ClassVar[tuple[str, ...]] = ("related_property",)

    @override
    def serialize_body(self, package: Package) -> bytes:
        return (
            super().serialize_body(package)
            + self.modifier_stack.serialize(package)
            + self.related_property.serialize(package)
        )


@dataclass
class UByteAttributePropertyPayload(UNumericAttributePropertyPayload, UBytePropertyPayload):
    """Byte property followed by its attribute links."""


@dataclass
class UNamePropertyPayload(UPropertyPayload):
    """UnrealScript name."""


@dataclass
class UStrPropertyPayload(UPropertyPayload):
    """UnrealScript string."""


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
