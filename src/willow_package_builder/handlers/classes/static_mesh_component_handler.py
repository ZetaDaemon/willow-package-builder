import struct
from typing import TYPE_CHECKING, ClassVar, override

from willow_package_builder.handlers.classes.component_handler import ComponentHandler
from willow_package_builder.upackage import ReferencePath

if TYPE_CHECKING:
    from willow_package_builder.handlers import SerializationContext
    from willow_package_builder.payloads.instance_payload import ObjectInstancePayload
    from willow_package_builder.upackage import UObject

ENGINE_STATIC_MESH_COMPONENT_PATH = ReferencePath("Engine.StaticMeshComponent")


class StaticMeshComponentHandler(ComponentHandler):
    """Serialize static mesh components without baked LOD data."""

    CLASS_PATH: ClassVar[ReferencePath] = ENGINE_STATIC_MESH_COMPONENT_PATH

    @override
    def serialize(
        self, obj: UObject, payload: ObjectInstancePayload, context: SerializationContext
    ) -> bytes:
        data = super().serialize(obj, payload, context)
        return data + struct.pack("<i", 0)  # Empty native LODData array.
