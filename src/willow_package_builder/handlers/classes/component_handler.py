from typing import TYPE_CHECKING, ClassVar, override

from willow_package_builder.handlers.classes.class_handler import ClassHandler
from willow_package_builder.payloads.instance_payload import (
    ComponentTemplatePayload,
    ObjectInstancePayload,
)
from willow_package_builder.upackage import CORE_COMPONENT_PATH, ReferencePath, UObject

if TYPE_CHECKING:
    from willow_package_builder.handlers import SerializationContext


class ComponentHandler(ClassHandler):
    """Write the native header for ordinary component instances."""

    CLASS_PATH: ClassVar[ReferencePath] = CORE_COMPONENT_PATH

    @override
    def serialize(
        self, obj: UObject, payload: ObjectInstancePayload, context: SerializationContext
    ) -> bytes:
        if isinstance(payload, ComponentTemplatePayload):
            return super().serialize(obj, payload, context)

        template_owner_class = ReferencePath()
        return template_owner_class.serialize(context.package) + super().serialize(
            obj, payload, context
        )
