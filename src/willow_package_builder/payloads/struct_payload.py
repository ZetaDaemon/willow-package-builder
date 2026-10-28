import struct
from dataclasses import dataclass, field
from enum import IntFlag
from typing import TYPE_CHECKING, override

from willow_package_builder.payloads.class_payload import UStructPayload
from willow_package_builder.upackage import FName, Package

if TYPE_CHECKING:
    from willow_package_builder.payloads.instance_payload import PropertyOverride


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

    net_index: int = -1
    struct_flags: StructFlags = StructFlags.NONE
    defaults: list[PropertyOverride] = field(default_factory=list)

    @override
    def serialize_body(self, package: Package) -> bytes:
        return (
            super().serialize_body(package)
            + struct.pack("<I", int(self.struct_flags))
            + b"".join(prop.serialize(package) for prop in self.defaults)
            + FName("None").serialize(package)
        )

    @override
    def serialize(self, package: Package) -> bytes:
        return (
            struct.pack("<i", self.net_index)
            + FName("None").serialize(package)
            + self.serialize_body(package)
        )
