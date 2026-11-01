from dataclasses import dataclass
from typing import TYPE_CHECKING

from willow_package_builder.payloads.class_payload import UClassPayload
from willow_package_builder.payloads.enum_payload import UEnumPayload
from willow_package_builder.upackage import FName, ObjectFlags, UObject

from .build_component import BuildComponent

if TYPE_CHECKING:
    from .references import PackageReferences


@dataclass
class EnumBuilder(BuildComponent):
    references: PackageReferences

    def build_class_enums(self) -> None:
        enum_class = self.references.class_object_reference("Core.Enum")

        for class_path, exports in self.classes.items():
            class_payload = exports.class_object.payload

            if not isinstance(class_payload, UClassPayload):
                msg = f"Class must be linked before building enums: {class_path}"
                raise ValueError(msg)  # noqa: TRY004

            for declaration in reversed(exports.declaration.enums):
                payload = UEnumPayload(
                    next_field=class_payload.children,
                    names=[FName(member) for member in declaration.members],
                )

                obj = UObject(
                    FName(declaration.name),
                    ObjectFlags.DEFAULT_EXPORT,
                    exports.class_object.reference(),
                    enum_class,
                    payload=payload,
                )

                class_payload.children = self.package.add_export(obj)
