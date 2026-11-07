from dataclasses import dataclass
from typing import TYPE_CHECKING

from willow_package_builder.builder.build_component import BuildComponent
from willow_package_builder.compiler.syntax.modifiers import ClassModifierName
from willow_package_builder.logging import CompilationError, WarningCode, info, warn
from willow_package_builder.payloads.class_payload import ClassFlags, StateFlags, UClassPayload
from willow_package_builder.upackage import ObjectFlags, ReferencePath, UObject

from .exports import ClassExport

if TYPE_CHECKING:
    from willow_package_builder.builder.objects.object_builder import ObjectBuilder
    from willow_package_builder.builder.references import PackageReferences

    from .property_builder import PropertyBuilder

CLASS_MODIFIER_FLAGS: dict[ClassModifierName, ClassFlags] = {
    # Implementation
    ClassModifierName.ABSTRACT: ClassFlags.ABSTRACT,
    ClassModifierName.NATIVE: ClassFlags.NATIVE,
    ClassModifierName.NATIVE_REPLICATION: ClassFlags.NATIVE_REPLICATION,
    ClassModifierName.NO_EXPORT: ClassFlags.NO_EXPORT,
    # Persistence and configuration
    ClassModifierName.TRANSIENT: ClassFlags.TRANSIENT,
    ClassModifierName.CONFIG: ClassFlags.CONFIG,
    ClassModifierName.PER_OBJECT_CONFIG: ClassFlags.PER_OBJECT_CONFIG,
    ClassModifierName.PER_OBJECT_LOCALIZED: ClassFlags.PER_OBJECT_LOCALIZED,
    # Construction and placement
    ClassModifierName.EDIT_INLINE_NEW: ClassFlags.EDIT_INLINE_NEW,
    ClassModifierName.PLACEABLE: ClassFlags.PLACEABLE,
    # Editor organisation
    ClassModifierName.COLLAPSE_CATEGORIES: ClassFlags.COLLAPSE_CATEGORIES,
}
CLASS_MODIFIER_CLEAR_FLAGS: dict[ClassModifierName, ClassFlags] = {
    ClassModifierName.NO_TRANSIENT: ClassFlags.TRANSIENT,
    ClassModifierName.NOT_EDIT_INLINE_NEW: ClassFlags.EDIT_INLINE_NEW,
    ClassModifierName.NOT_PLACEABLE: ClassFlags.PLACEABLE,
    ClassModifierName.DONT_COLLAPSE_CATEGORIES: ClassFlags.COLLAPSE_CATEGORIES,
}


@dataclass
class ClassBuilder(BuildComponent):
    references: PackageReferences
    properties: PropertyBuilder
    objects: ObjectBuilder

    def reserve_classes(self) -> None:
        package_name = self.config.name

        for class_path in self.context.class_order:
            if class_path.get_outer().name != package_name:
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
            class_object = UObject(declaration.name, ObjectFlags.CLASS_EXPORT)
            self.package.add_export(class_object)

            default_object = self.objects.construct_cdo(class_path, class_object)

            self.classes[class_path] = ClassExport(declaration, class_object, default_object)

    def resolve_within_class(self, class_path: ReferencePath) -> ReferencePath:
        return self.context.references.resolve_within_class(
            class_path, self.context.parents, self.context.packages
        )

    def link_classes(self) -> None:
        supported_modifiers = {
            ClassModifierName.ABSTRACT,
            ClassModifierName.EDIT_INLINE_NEW,
            ClassModifierName.PER_OBJECT_LOCALIZED,
        }

        for class_path, exports in self.classes.items():
            parent = self.context.parents[class_path]

            if parent is None:
                msg = "Building root classes is not supported yet"
                raise NotImplementedError(msg)

            flags = ClassFlags.COMPILED | ClassFlags.PARSED

            for modifier in exports.declaration.modifiers:
                modifier_name = modifier.name

                if modifier_name == ClassModifierName.NATIVE:
                    msg = f"Cannot compile native class {class_path}"
                    raise CompilationError(msg)

                if modifier_name not in supported_modifiers:
                    msg = (
                        f"Class modifier {modifier_name!r} on {class_path} "
                        "is not supported by the package builder yet"
                    )
                    raise NotImplementedError(msg)

                if modifier_name in CLASS_MODIFIER_FLAGS:
                    flags |= CLASS_MODIFIER_FLAGS[modifier_name]
                elif modifier_name in CLASS_MODIFIER_CLEAR_FLAGS:
                    flags &= ~CLASS_MODIFIER_CLEAR_FLAGS[modifier_name]
                else:
                    msg = f"Class modifier {modifier_name!r} on {class_path} has no implementation."
                    raise NotImplementedError(msg)

            parent_reference = self.references.class_object_reference(parent)

            exports.class_object.super_object = parent_reference

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
