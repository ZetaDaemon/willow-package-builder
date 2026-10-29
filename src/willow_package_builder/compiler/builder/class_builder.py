from dataclasses import dataclass
from typing import TYPE_CHECKING

from willow_package_builder.compiler.builder.exports import ClassExports
from willow_package_builder.logging import CompilationError, WarningCode, info, warn
from willow_package_builder.package_config import collect_visible_packages
from willow_package_builder.payloads.class_payload import ClassFlags, StateFlags, UClassPayload
from willow_package_builder.payloads.instance_payload import ObjectInstancePayload
from willow_package_builder.upackage import FName, ObjectFlags, UObject

from .build_component import BuildComponent

if TYPE_CHECKING:
    from .property_builder import PropertyBuilder
    from .references import PackageReferences


@dataclass
class ClassBuilder(BuildComponent):
    references: PackageReferences
    properties: PropertyBuilder

    def reserve_classes(self) -> None:
        package_name = self.config.name.casefold()

        for class_path in self.context.class_order:
            if class_path.partition(".")[0] != package_name:
                continue

            declaration = self.context.references.classes[class_path]

            if declaration.is_interface:
                warn(
                    WarningCode.UNSUPPORTED_INTERFACE_COMPILATION,
                    f"Interface {class_path!r} is available for reference only; "
                    "its export will be omitted because interface compilation "
                    "is not supported yet.",
                )
                continue

            info(f"Compiling class {class_path}")
            class_object = UObject(name=FName(declaration.name), flags=ObjectFlags.CLASS_EXPORT)

            class_reference = self.package.add_export(class_object)

            default_object = UObject(
                name=FName(f"Default__{declaration.name}"),
                object_class=class_reference,
                flags=ObjectFlags.CDO_EXPORT,
                payload=ObjectInstancePayload(),
            )

            self.package.add_export(default_object)

            self.classes[class_path] = ClassExports(
                declaration=declaration, class_object=class_object, default_object=default_object
            )

    def resolve_within_class(self, class_path: str) -> str:
        current: str | None = class_path.casefold()

        while current is not None:
            declaration = self.context.references.classes[current]

            if declaration.within is not None:
                package_key = current.partition(".")[0]
                config = next(
                    config
                    for config in self.context.packages
                    if config.name.casefold() == package_key
                )

                resolved, _ = self.context.references.resolve_class(
                    declaration.within,
                    current_package=config.name,
                    visible_packages=collect_visible_packages(config, self.context.packages),
                )
                return resolved

            current = self.context.parents[current]

        return "core.object"

    def link_classes(self) -> None:
        supported_flags = {
            "abstract": ClassFlags.ABSTRACT,
            "editinlinenew": ClassFlags.EDIT_INLINE_NEW,
            "perobjectlocalized": ClassFlags.PER_OBJECT_LOCALIZED,
        }

        for class_path, exports in self.classes.items():
            parent = self.context.parents[class_path]

            if parent is None:
                msg = "Building root classes is not supported yet"
                raise CompilationError(msg)

            flags = ClassFlags.COMPILED | ClassFlags.PARSED

            for modifier in exports.declaration.modifiers:
                flag = supported_flags.get(modifier.name.casefold())

                if flag is None:
                    msg = (
                        f"Class modifier {modifier.name!r} on {class_path} "
                        "is not supported by the package builder yet"
                    )
                    raise CompilationError(msg)

                flags |= flag

            parent_reference = self.references.class_object_reference(parent)

            exports.class_object.super_object = parent_reference

            exports.default_object.archetype = self.references.class_object_reference(
                parent, default_object=True
            )

            exports.class_object.payload = UClassPayload(
                super_struct=parent_reference,
                within=self.references.class_object_reference(
                    self.resolve_within_class(class_path)
                ),
                default_object=exports.default_object.reference(),
                class_flags=flags,
                state_flags=StateFlags.AUTO,
            )

    def build_class_fields(self) -> None:
        for class_path, exports in self.classes.items():
            payload = exports.class_object.payload

            if not isinstance(payload, UClassPayload):
                msg = f"Class must be linked before building fields: {class_path}"
                raise ValueError(msg)  # noqa: TRY004

            for variable in reversed(exports.declaration.variables):
                obj = self.properties.create_field(
                    exports.class_object, variable, class_path, payload.children
                )
                payload.children = obj.reference()
