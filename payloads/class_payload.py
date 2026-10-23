import struct
from abc import ABC
from dataclasses import dataclass, field
from enum import IntFlag
from typing import ClassVar, override

from upackage import FName, ObjectPayload, Package, ReferencePath, serialize_fstring


@dataclass
class UFieldPayload(ObjectPayload, ABC):
    """Shared payload data for fields."""

    next_field: ReferencePath = field(default_factory=ReferencePath)

    def serialize_body(self, package: Package) -> bytes:
        """Serialize the UField portion of a payload."""
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

    script: bytes = b""
    script_memory_size: int = 0

    @override
    def serialize_body(self, package: Package) -> bytes:
        """Serialize the inherited data and UStruct portion."""
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
                self.script_memory_size,
                len(self.script),
            )
            + self.script
        )


class StateFlags(IntFlag):
    """StateFlags."""

    NONE = 0
    AUTO = 0x0002


@dataclass
class UStatePayload(UStructPayload, ABC):
    """Abstract shared payload data for states."""

    NO_LABEL_TABLE: ClassVar[int] = 0xFFFF

    probe_mask: int = 0
    label_table_offset: int = NO_LABEL_TABLE
    state_flags: StateFlags = StateFlags.NONE

    function_map: dict[str, ReferencePath] = field(default_factory=dict)

    @override
    def serialize_body(self, package: Package) -> bytes:
        """Serialize the inherited data and UState portion."""
        functions = b"".join(
            FName(name).serialize(package) + function.serialize(package)
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


class ClassFlags(IntFlag):
    """ClassFlags."""

    NONE = 0

    ABSTRACT = 0x00000001
    COMPILED = 0x00000002
    PARSED = 0x00000010
    EDIT_INLINE_NEW = 0x00001000
    PER_OBJECT_LOCALIZED = 0x40000000


@dataclass
class UClassPayload(UStatePayload):
    """BL2 class definition payload."""

    UNKNOWN_BL2_BYTE: ClassVar[int] = 45

    net_index: int = -1

    class_flags: ClassFlags = ClassFlags.COMPILED | ClassFlags.PARSED
    within: ReferencePath = field(default_factory=ReferencePath)
    config_name: FName = field(default_factory=lambda: FName("None"))

    component_defaults: dict[str, ReferencePath] = field(default_factory=dict)

    dont_sort_categories: list[str] = field(default_factory=list)
    hide_categories: list[str] = field(default_factory=list)
    auto_expand_categories: list[str] = field(default_factory=list)
    auto_collapse_categories: list[str] = field(default_factory=list)

    force_script_order: bool = False
    class_groups: list[str] = field(default_factory=list)
    native_class_name: str = ""
    dll_bind_name: FName = field(default_factory=lambda: FName("None"))

    default_object: ReferencePath = field(default_factory=ReferencePath)

    @override
    def serialize_body(self, package: Package) -> bytes:
        """Serialize the inherited data and UClass portion."""

        def serialize_names(names: list[str]) -> bytes:
            return struct.pack("<i", len(names)) + b"".join(
                FName(name).serialize(package) for name in names
            )

        component_defaults = struct.pack("<i", len(self.component_defaults)) + b"".join(
            FName(name).serialize(package) + obj.serialize(package)
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
            + struct.pack("<B", self.UNKNOWN_BL2_BYTE)
            + self.default_object.serialize(package)
        )

    @override
    def serialize(self, package: Package) -> bytes:
        """Serialize a complete class payload."""
        if self.default_object is None:
            msg = "Class payload requires a default object"
            raise ValueError(msg)

        return struct.pack("<i", self.net_index) + self.serialize_body(package)


class FunctionFlags(IntFlag):
    """FunctionFlags."""

    NONE = 0

    DEFINED = 0x00000002
    NET = 0x00000040
    NATIVE = 0x00000400
    STATIC = 0x00002000
    PROTECTED = 0x00080000
    HAS_OUT_PARAMS = 0x00400000


@dataclass
class UFunctionPayload(UStructPayload):
    """BL2 scripted function payload."""

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
            struct.pack("<Hi", 0, self.net_index)  # Empty BL2 simple-locals table.
            + FName("None").serialize(package)  # Empty property list.
            + self.serialize_body(package)
        )
