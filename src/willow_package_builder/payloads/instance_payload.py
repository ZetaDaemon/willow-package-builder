import struct
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, override

from willow_package_builder.handlers import SerializationContext
from willow_package_builder.properties.value_serializer import ValueSerializer
from willow_package_builder.upackage import FName, ObjectPayload, Package, ReferencePath, UObject

if TYPE_CHECKING:
    from willow_package_builder.builder.build_context import BuildContext
    from willow_package_builder.handlers.classes.class_handler import ClassHandler
    from willow_package_builder.properties.values import Value

INDEX_NONE = -1


@dataclass
class ObjectInstancePayload(ObjectPayload):
    class_path: ReferencePath
    context: BuildContext

    properties: dict[FName, Value] = field(default_factory=dict)
    net_index: int = INDEX_NONE

    handler: ClassHandler | None = field(default=None, init=False, repr=False, compare=False)
    owner: UObject | None = field(default=None, init=False, repr=False, compare=False)

    def serialize_regular(self, package: Package) -> bytes:
        """Serialize the ordinary instance data without handler dispatch."""
        serializer = ValueSerializer(package, self.context)

        return struct.pack("<i", self.net_index) + serializer.serialize_properties(
            self.class_path, self.properties
        )

    @override
    def serialize(self, package: Package) -> bytes:
        """Serialize without final layout information."""
        return self.serialize_at(package, None)

    @override
    def serialize_at(self, package: Package, payload_offset: int | None) -> bytes:
        """Serialize using final layout information when available."""
        if self.handler is None:
            return self.serialize_regular(package)

        if self.owner is None:
            msg = "A handler-controlled payload requires its owning object"
            raise RuntimeError(msg)

        return self.handler.serialize(
            self.owner, self, SerializationContext(package, payload_offset)
        )
