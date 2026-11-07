import struct
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, override

from willow_package_builder.properties.value_serializer import ValueSerializer
from willow_package_builder.upackage import FName, ObjectPayload, Package, ReferencePath

if TYPE_CHECKING:
    from willow_package_builder.builder.build_context import BuildContext
    from willow_package_builder.properties.values import Value

INDEX_NONE = -1
PROPERTY_LIST_END = FName("None")


@dataclass
class ObjectInstancePayload(ObjectPayload):
    class_path: ReferencePath
    context: BuildContext

    properties: dict[FName, Value] = field(default_factory=dict)
    net_index: int = INDEX_NONE

    @override
    def serialize(self, package: Package) -> bytes:
        serializer = ValueSerializer(package, self.context)

        return struct.pack("<i", self.net_index) + serializer.serialize_properties(
            self.class_path, self.properties
        )
