from dataclasses import dataclass

from willow_package_builder.compiler.semantics.intrinsics import IntrinsicDefinition
from willow_package_builder.logging import CompilationError
from willow_package_builder.upackage import (
    CORE_CLASS_PATH,
    CORE_ENUM_PATH,
    CORE_FUNCTION_PATH,
    CORE_PACKAGE_CLASS_PATH,
    CORE_SCRIPT_STRUCT_PATH,
    DEFAULT_OBJECT_PREFIX,
    FName,
    ReferencePath,
)

from .build_component import BuildComponent


@dataclass
class PackageReferences(BuildComponent):
    def ensure_import(
        self, name: FName, outer: ReferencePath, class_package: FName, class_name: FName
    ) -> ReferencePath:
        return self.package.ensure_import(name, outer, class_package, class_name)

    def class_object_reference(
        self, class_path: ReferencePath, *, default_object: bool = False
    ) -> ReferencePath:
        definition = self.context.references.lookup_class(class_path)

        if isinstance(definition, IntrinsicDefinition):
            if default_object:
                msg = (
                    f"Default-object references for intrinsic "
                    f"{definition.path!r} are not supported yet"
                )
                raise NotImplementedError(msg)

            package, name = definition.path.split()
            if package is None:
                msg = f"Expected fully qualified path, got {definition.path}"
                raise ValueError(msg)

            package_reference = self.ensure_import(
                package.name, ReferencePath(), *CORE_PACKAGE_CLASS_PATH.full_split()
            )

            return self.ensure_import(
                name, package_reference, definition.class_package, definition.class_name
            )

        if class_path.outer is None:
            msg = f"Expected fully qualified class, got {class_path}"
            raise ValueError(msg)
        package_key = class_path.outer.name

        if package_key == self.config.name:
            if definition.is_interface:
                msg = (
                    f"Cannot reference interface {class_path!r} as a local export: "
                    "interface compilation is not supported yet"
                )
                raise CompilationError(msg)

            exports = self.classes[class_path]
            obj = exports.default_object if default_object else exports.class_object
            return obj.reference()

        config = next(config for config in self.context.packages if config.name == package_key)

        package_reference = self.ensure_import(
            config.name, ReferencePath(), *CORE_PACKAGE_CLASS_PATH.full_split()
        )

        if default_object:
            return self.ensure_import(
                FName(f"{DEFAULT_OBJECT_PREFIX}{definition.name}"),
                package_reference,
                config.name,
                definition.name,
            )

        return self.ensure_import(definition.name, package_reference, *CORE_CLASS_PATH.full_split())

    def enum_reference(self, enum_path: ReferencePath) -> ReferencePath:
        owner_path, name = enum_path.split()

        if not owner_path:
            msg = f"Expected a qualified enum path: {enum_path}"
            raise ValueError(msg)

        member = self.context.references.resolve_enum(owner_path, name, self.context.parents)

        outer = self.class_object_reference(member.owner_class)
        if member.owner_class.outer is None:
            msg = f"Expected fully qualified class, got {member.owner_class.outer}"
            raise ValueError(msg)
        package_name = member.owner_class.outer.name

        if package_name == self.config.name:
            reference = outer + member.declaration.name

            # Local enum exports must already have been built.
            return self.package.lookup_object_by_path(reference).reference()

        return self.ensure_import(member.declaration.name, outer, *CORE_ENUM_PATH.full_split())

    def struct_reference(self, struct_path: ReferencePath) -> ReferencePath:
        owner_path, name = struct_path.split()
        if not owner_path:
            msg = f"Expected a qualified struct path: {struct_path}"
            raise ValueError(msg)

        member = self.context.references.resolve_struct(owner_path, name, self.context.parents)

        path = member.owner_class + member.declaration.name
        if member.owner_class.outer is None:
            msg = f"Expected a qualified class, got {member.owner_class}"
            raise ValueError(msg)
        package_name = member.owner_class.outer.name

        if package_name == self.config.name:
            return self.structs[path].struct_object.reference()

        outer = self.class_object_reference(member.owner_class)

        return self.ensure_import(
            member.declaration.name, outer, *CORE_SCRIPT_STRUCT_PATH.full_split()
        )

    def function_reference(self, function_path: ReferencePath) -> ReferencePath:
        owner_path, name = function_path.split()

        if not owner_path:
            msg = f"Expected a qualified function path: {function_path}"
            raise ValueError(msg)

        member = self.context.references.resolve_function(owner_path, name, self.context.parents)

        outer = self.class_object_reference(member.owner_class)
        if member.owner_class.outer is None:
            msg = f"Expected a qualified class, got {member.owner_class}"
            raise ValueError(msg)
        package_name = member.owner_class.outer.name

        if package_name == self.config.name:
            reference = outer + member.declaration.name
            return self.package.lookup_object_by_path(reference).reference()

        return self.ensure_import(member.declaration.name, outer, *CORE_FUNCTION_PATH.full_split())
