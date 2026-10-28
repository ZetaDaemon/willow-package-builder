import struct
from dataclasses import dataclass, field
from typing import override

from willow_package_builder import logging
from willow_package_builder.payloads.class_payload import UFieldPayload
from willow_package_builder.upackage import FName, Package


@dataclass
class UEnumPayload(UFieldPayload):
    """An enum definition with members stored in value order."""

    net_index: int = -1
    names: list[FName] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.names = list(self.names)

        if not self.names:
            msg = "An enum must contain at least one member"
            raise ValueError(msg)

        prefix = str(self.names[0]).split("_", 1)[0]
        sentinel = FName(f"{prefix}_MAX")

        if self.names[-1] == sentinel:
            logging.warn(
                logging.WarningCode.EXPLICIT_ENUM_SENTINEL,
                f"Enum payload already contains sentinel {sentinel}.",
            )
        else:
            self.names.append(sentinel)

    @override
    def serialize_body(self, package: Package) -> bytes:
        return (
            super().serialize_body(package)
            + struct.pack("<i", len(self.names))
            + b"".join(name.serialize(package) for name in self.names)
        )

    @override
    def serialize(self, package: Package) -> bytes:
        return (
            struct.pack("<i", self.net_index)
            + FName("None").serialize(package)
            + self.serialize_body(package)
        )
