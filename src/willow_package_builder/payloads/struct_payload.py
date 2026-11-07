import struct
from dataclasses import dataclass, field
from enum import IntFlag
from typing import TYPE_CHECKING, override

from willow_package_builder.properties.value_serializer import ValueSerializer
from willow_package_builder.upackage import NONE_NAME, FName, Package, ReferencePath

from .class_payload import UStructPayload

if TYPE_CHECKING:
    from willow_package_builder.builder.build_context import BuildContext
    from willow_package_builder.properties.values import Value


class StructFlags(IntFlag):
    NONE = 0

    NATIVE = 0x00000001
    EXPORT = 0x00000002
    HAS_COMPONENTS = 0x00000004
    TRANSIENT = 0x00000008
    ATOMIC = 0x00000010
    IMMUTABLE = 0x00000020
    STRICT_CONFIG = 0x00000040
    IMMUTABLE_WHEN_COOKED = 0x00000080
    ATOMIC_WHEN_COOKED = 0x00000100


@dataclass
class UScriptStructPayload(UStructPayload):
    """A script-defined struct and its default values."""

    struct_path: ReferencePath = field(kw_only=True)
    context: BuildContext = field(kw_only=True, repr=False)

    net_index: int = -1
    struct_flags: StructFlags = StructFlags.NONE
    defaults: dict[FName, Value] = field(default_factory=dict)

    @override
    def serialize_body(self, package: Package) -> bytes:
        serializer = ValueSerializer(package, self.context)

        return (
            super().serialize_body(package)
            + struct.pack("<I", int(self.struct_flags))
            + serializer.serialize_struct_fields(self.struct_path, self.defaults)
        )

    @override
    def serialize(self, package: Package) -> bytes:
        return (
            struct.pack("<i", self.net_index)
            + NONE_NAME.serialize(package)
            + self.serialize_body(package)
        )
