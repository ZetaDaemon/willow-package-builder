import struct
from abc import ABC
from dataclasses import dataclass, field
from enum import IntFlag
from typing import ClassVar, override

from willow_package_builder.bytecode import Bytecode
from willow_package_builder.games import get_game
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

    NONE = 0
    AUTO = 0x2


class ClassFlags(IntFlag):
    """ClassFlags."""

    NONE                 = 0x0

    ABSTRACT             = 0x1
    COMPILED             = 0x2
    CONFIG               = 0x4
    TRANSIENT            = 0x8
    PARSED               = 0x10
    NATIVE               = 0x80
    NO_EXPORT            = 0x100
    PLACEABLE            = 0x200
    PER_OBJECT_CONFIG    = 0x400
    NATIVE_REPLICATION   = 0x800
    EDIT_INLINE_NEW      = 0x1000
    COLLAPSE_CATEGORIES  = 0x2000
    HAS_INSTANCED_PROPS  = 0x200000
    PER_OBJECT_LOCALIZED = 0x40000000




class FunctionFlags(IntFlag):
    """FunctionFlags."""

    NONE = 0x0

    FINAL = 0x1
    DEFINED = 0x2
    ITERATOR = 0x4
    LATENT = 0x8
    SINGULAR = 0x20
    NET = 0x40
    NET_RELIABLE = 0x80
    SIMULATED = 0x100
    EXEC = 0x200
    NATIVE = 0x400
    STATIC = 0x2000
    PUBLIC = 0x20000
    PRIVATE = 0x40000
    PROTECTED = 0x80000
    NET_SERVER = 0x200000
    HAS_OUT_PARAMS = 0x400000
    NET_CLIENT = 0x1000000


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
    children: ReferencePath = field(default_factory=ReferencePath)
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

    function_map: dict[FName, ReferencePath] = field(default_factory=dict)

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
class UClassPayload(UStatePayload):
    """Class definition payload."""

    net_index: int = -1

    class_flags: ClassFlags = ClassFlags.COMPILED | ClassFlags.PARSED
    within: ReferencePath = field(default_factory=ReferencePath)
    config_name: FName = field(default_factory=lambda: NONE_NAME)

    component_defaults: dict[FName, ReferencePath] = field(default_factory=dict)

    dont_sort_categories: list[FName] = field(default_factory=list)
    hide_categories: list[FName] = field(default_factory=list)
    auto_expand_categories: list[FName] = field(default_factory=list)
    auto_collapse_categories: list[FName] = field(default_factory=list)

    force_script_order: bool = False
    class_groups: list[FName] = field(default_factory=list)
    native_class_name: str = ""
    dll_bind_name: FName = field(default_factory=lambda: NONE_NAME)

    default_object: ReferencePath = field(default_factory=ReferencePath)

    memory_tag: int = 1

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

        return (
            super().serialize_body(package)
            + struct.pack("<I", int(self.class_flags))
            + self.within.serialize(package)
            + self.config_name.serialize(package)
            + component_defaults
            + struct.pack("<i", 0)  # No implemented interfaces.
            + serialize_names(self.dont_sort_categories)
            + serialize_names(self.hide_categories)
            + serialize_names(self.auto_expand_categories)
            + serialize_names(self.auto_collapse_categories)
            + struct.pack("<i", int(self.force_script_order))
            + serialize_names(self.class_groups)
            + serialize_fstring(self.native_class_name)
            + self.dll_bind_name.serialize(package)
            + struct.pack("<B", self.memory_tag)
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

    @override
    def serialize_body(self, package: Package) -> bytes:
        """Serialize the inherited data and UFunction portion."""
        return (
            super().serialize_body(package)
            + struct.pack(
                "<HBI", self.native_index, self.operator_precedence, int(self.function_flags)
            )
            + self.friendly_name.serialize(package)
        )

    @override
    def serialize(self, package: Package) -> bytes:
        """Serialize a complete scripted function payload."""
        unsupported = FunctionFlags.NATIVE | FunctionFlags.NET

        if self.function_flags & unsupported:
            msg = "Native and networked functions are not supported yet"
            raise ValueError(msg)

        if self.native_index != 0:
            msg = "Scripted functions must have a zero native index"
            raise ValueError(msg)

        return (
            struct.pack("<Hi", 0, self.net_index)  # Empty simple-locals table.
            + NONE_NAME.serialize(package)  # Empty property list.
            + self.serialize_body(package)
        )
