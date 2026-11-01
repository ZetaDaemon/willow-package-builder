from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from willow_package_builder.payloads.property_values import PropertyValue
from willow_package_builder.upackage import FName, Package

if TYPE_CHECKING:
    from willow_package_builder.payloads.instance_payload import PropertyOverride


@dataclass
class TaggedStructValue(PropertyValue):
    fields: list[PropertyOverride]

    @override
    def serialize(self, package: Package) -> bytes:
        return b"".join(field.serialize(package) for field in self.fields) + FName(
            "None"
        ).serialize(package)


@dataclass
class BinaryStructValue(PropertyValue):
    fields: list[PropertyValue]

    @override
    def serialize(self, package: Package) -> bytes:
        return b"".join(field.serialize(package) for field in self.fields)
