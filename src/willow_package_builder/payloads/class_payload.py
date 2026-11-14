import struct
from abc import ABC
from dataclasses import dataclass, field
from enum import IntFlag
from typing import ClassVar, override

from willow_package_builder.bytecode import Bytecode
from willow_package_builder.upackage import (
    NONE_NAME,
    FName,
    ObjectPayload,
    Package,
    ReferencePath,
    serialize_fstring,
)


# fmt: off
class StateFlags(IntFlag):
    """StateFlags."""

    NONE       = 0x0

    EDITABLE   = 0x1
    AUTO       = 0x2
    SIMULATED  = 0x4
    HAS_LOCALS = 0x8


class ClassFlags(IntFlag):
    """ClassFlags."""

    NONE                  = 0x0

    ABSTRACT              = 0x1
    COMPILED              = 0x2
    CONFIG                = 0x4
    TRANSIENT             = 0x8
    PARSED                = 0x10
    LOCALIZED             = 0x20
    SAFE_REPLACE          = 0x40
    NATIVE                = 0x80
    NO_EXPORT             = 0x100
    PLACEABLE             = 0x200
    PER_OBJECT_CONFIG     = 0x400
    NATIVE_REPLICATION    = 0x800
    EDIT_INLINE_NEW       = 0x1000
    COLLAPSE_CATEGORIES   = 0x2000
    INTERFACE             = 0x4000
    IS_U_PROPERTY         = 0x8000
    IS_U_OBJECT_PROPERTY  = 0x10000
    IS_U_BOOL_PROPERTY    = 0x20000
    IS_U_STATE            = 0x40000
    IS_U_FUNCTION         = 0x80000
    IS_U_STRUCT_PROPERTY  = 0x100000
    HAS_INSTANCED_PROPS   = 0x200000
    NEEDS_DEF_PROPS       = 0x400000
    HAS_COMPONENTS        = 0x800000
    HIDDEN                = 0x1000000
    DEPRECATED            = 0x2000000
    HIDE_DROP_DOWN        = 0x4000000
    EXPORTED              = 0x8000000
    INTRINSIC             = 0x10000000
    NATIVE_ONLY           = 0x20000000
    PER_OBJECT_LOCALIZED  = 0x40000000
    HAS_CROSS_LEVEL_REFS  = 0x80000000




class FunctionFlags(IntFlag):
    """FunctionFlags."""

    NONE                = 0x0

    FINAL               = 0x1
    DEFINED             = 0x2
    ITERATOR            = 0x4
    LATENT              = 0x8
    PRE_OPERATOR        = 0x10
    SINGULAR            = 0x20
    NET                 = 0x40
    NET_RELIABLE        = 0x80
    SIMULATED           = 0x100
    EXEC                = 0x200
    NATIVE              = 0x400
    EVENT               = 0x800
    OPERATOR            = 0x1000
    STATIC              = 0x2000
    HAS_OPTIONAL_PARAMS = 0x4000
    CONST               = 0x8000
    PUBLIC              = 0x20000
    PRIVATE             = 0x40000
    PROTECTED           = 0x80000
    DELEGATE            = 0x100000
    NET_SERVER          = 0x200000
    HAS_OUT_PARAMS      = 0x400000
    HAS_DEFAULTS        = 0x800000
    NET_CLIENT          = 0x1000000
    DLL_IMPORT          = 0x2000000
    K2_CALL             = 0x4000000
    K2_OVERRIDE         = 0x8000000
    K2_PURE             = 0x10000000


# fmt: on


@dataclass
class UFieldPayload(ObjectPayload, ABC):
    """Shared payload data for fields."""

    next_field: ReferencePath = field(default_factory=ReferencePath)

    required_fields: ClassVar[tuple[str, ...]] = ()

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)

        own_fields = cls.__dict__.get("required_fields", ())

        inherited_fields = (
            field_name
            for base in cls.__bases__
            for field_name in getattr(base, "required_fields", ())
        )

        cls.required_fields = tuple(dict.fromkeys((*inherited_fields, *own_fields)))

    def serialize_body(self, package: Package) -> bytes:
        """Serialize the UField portion of a payload."""
        cls_name = type(self).__name__
        for field_name in self.required_fields:
            reference = getattr(self, field_name)
            if not isinstance(reference, ReferencePath):
                msg = f"field {field_name} of {cls_name} is not a ReferencePath"
                raise TypeError(msg)
            if reference.is_none():
                msg = f"{cls_name} requires a valid {field_name}"
                raise ValueError(msg)

        return self.next_field.serialize(package)


@dataclass
class UStructPayload(UFieldPayload, ABC):
    """Abstract shared payload data for structs."""

    super_struct: ReferencePath = field(default_factory=ReferencePath)
    script_text: ReferencePath = field(default_factory=ReferencePath)
    children: ReferencePath = field(default_factory=ReferencePath, init=False)
    cpp_text: ReferencePath = field(default_factory=ReferencePath)

    source_line: int = -1
    source_text_position: int = -1

    script: Bytecode = field(default_factory=Bytecode)

    @override
    def serialize_body(self, package: Package) -> bytes:
        """Serialize the inherited data and UStruct portion."""
        script_data = self.script.serialize(package)

        return (
            super().serialize_body(package)
            + self.super_struct.serialize(package)
            + self.script_text.serialize(package)
            + self.children.serialize(package)
            + self.cpp_text.serialize(package)
            + struct.pack(
                "<iiii",
                self.source_line,
                self.source_text_position,
                self.script.memory_size(),
                len(script_data),
            )
            + script_data
        )


@dataclass
class UStatePayload(UStructPayload, ABC):
    """Abstract shared payload data for states."""

    NO_LABEL_TABLE: ClassVar[int] = 0xFFFF

    probe_mask: int = 0
    label_table_offset: int = NO_LABEL_TABLE
    state_flags: StateFlags = StateFlags.NONE

    function_map: dict[FName, ReferencePath] = field(default_factory=dict, init=False)

    @override
    def serialize_body(self, package: Package) -> bytes:
        """Serialize the inherited data and UState portion."""
        functions = b"".join(
            name.serialize(package) + function.serialize(package)
            for name, function in self.function_map.items()
        )

        return (
            super().serialize_body(package)
            + struct.pack(
                "<IHHi",
                self.probe_mask,
                self.label_table_offset,
                int(self.state_flags),
                len(self.function_map),
            )
            + functions
        )


@dataclass
class UScriptStatePayload(UStatePayload):
    """Payload for a state declared inside an UnrealScript class."""

    net_index: int = -1

    @override
    def serialize(self, package: Package) -> bytes:
        return (
            struct.pack("<i", self.net_index)
            + NONE_NAME.serialize(package)
            + self.serialize_body(package)
        )


@dataclass
class UClassPayload(UStatePayload):
    """Class definition payload."""

    net_index: int = -1

    class_flags: ClassFlags = ClassFlags.COMPILED | ClassFlags.PARSED
    within: ReferencePath = field(default_factory=ReferencePath)
    config_name: FName = field(default_factory=lambda: NONE_NAME)

    force_script_order: bool = False
    native_class_name: str = ""
    dll_bind_name: FName = field(default_factory=lambda: NONE_NAME)

    default_object: ReferencePath = field(default_factory=ReferencePath)

    component_defaults: dict[FName, ReferencePath] = field(default_factory=dict, init=False)
    interfaces: dict[ReferencePath, ReferencePath] = field(default_factory=dict, init=False)
    dont_sort_categories: list[FName] = field(default_factory=list, init=False)
    hide_categories: list[FName] = field(default_factory=list, init=False)
    auto_expand_categories: list[FName] = field(default_factory=list, init=False)
    auto_collapse_categories: list[FName] = field(default_factory=list, init=False)
    class_groups: list[FName] = field(default_factory=list, init=False)

    _MEMORY_TAG: ClassVar[int] = 1

    @override
    def serialize_body(self, package: Package) -> bytes:
        """Serialize the inherited data and UClass portion."""

        def serialize_names(names: list[FName]) -> bytes:
            return struct.pack("<i", len(names)) + b"".join(
                name.serialize(package) for name in names
            )

        if self.default_object.is_none():
            msg = "A ClassPayload must have a default object."
            raise ValueError(msg)

        component_defaults = struct.pack("<i", len(self.component_defaults)) + b"".join(
            name.serialize(package) + obj.serialize(package)
            for name, obj in self.component_defaults.items()
        )

        interfaces = struct.pack("<i", len(self.interfaces)) + b"".join(
            interface.serialize(package) + pointer_property.serialize(package)
            for interface, pointer_property in self.interfaces.items()
        )

        return (
            super().serialize_body(package)
            + struct.pack("<I", int(self.class_flags))
            + self.within.serialize(package)
            + self.config_name.serialize(package)
            + component_defaults
            + interfaces
            + serialize_names(self.dont_sort_categories)
            + serialize_names(self.hide_categories)
            + serialize_names(self.auto_expand_categories)
            + serialize_names(self.auto_collapse_categories)
            + struct.pack("<i", int(self.force_script_order))
            + serialize_names(self.class_groups)
            + serialize_fstring(self.native_class_name)
            + self.dll_bind_name.serialize(package)
            + struct.pack("<B", self._MEMORY_TAG)
            + self.default_object.serialize(package)
        )

    @override
    def serialize(self, package: Package) -> bytes:
        """Serialize a complete class payload."""
        if self.default_object is None:
            msg = "Class payload requires a default object"
            raise ValueError(msg)

        return struct.pack("<i", self.net_index) + self.serialize_body(package)


@dataclass
class UFunctionPayload(UStructPayload):
    """Scripted function payload."""

    friendly_name: FName = field(kw_only=True)

    net_index: int = -1
    native_index: int = 0
    operator_precedence: int = 0
    function_flags: FunctionFlags = FunctionFlags.DEFINED

    replication_offset: int = 0xFFFF

    @override
    def serialize_body(self, package: Package) -> bytes:
        """Serialize the inherited data and UFunction portion."""
        data = super().serialize_body(package) + struct.pack(
            "<HBI", self.native_index, self.operator_precedence, int(self.function_flags)
        )

        if self.function_flags & FunctionFlags.NET:
            data += struct.pack("<H", self.replication_offset)

        return data + self.friendly_name.serialize(package)

    @override
    def serialize(self, package: Package) -> bytes:
        """Serialize a complete scripted function payload."""
        if self.function_flags & FunctionFlags.NATIVE:
            msg = "Cannot serialize a native function as a scripted function"
            raise ValueError(msg)

        if self.native_index != 0:
            msg = "Scripted functions must have a zero native index"
            raise ValueError(msg)

        return (
            struct.pack("<Hi", 0, self.net_index)  # Empty simple-locals table.
            + NONE_NAME.serialize(package)  # Empty property list.
            + self.serialize_body(package)
        )
