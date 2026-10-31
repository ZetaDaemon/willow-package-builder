from dataclasses import dataclass

from willow_package_builder.compiler.semantics.intrinsics import IntrinsicDefinition
from willow_package_builder.logging import CompilationError
from willow_package_builder.upackage import ExternalReference, FName, ReferencePath

from .build_component import BuildComponent


@dataclass
class PackageReferences(BuildComponent):
    def ensure_import(
        self, name: str, outer: ReferencePath, class_package: str, class_name: str
    ) -> ReferencePath:
        obj = ExternalReference(FName(name), FName(class_package), FName(class_name), outer)
        reference = obj.reference()

        try:
            existing = self.package.lookup_object_by_path(reference)
        except KeyError:
            return self.package.add_import(obj)

        if (
            not isinstance(existing, ExternalReference)
            or existing.class_package != obj.class_package
            or existing.class_name != obj.class_name
        ):
            msg = f"Conflicting import definition for {reference}"
            raise ValueError(msg)

        return reference

    def class_object_reference(
        self, class_path: str, *, default_object: bool = False
    ) -> ReferencePath:
        class_path = class_path.casefold()
        definition = self.context.references.lookup_class(class_path)

        if isinstance(definition, IntrinsicDefinition):
            if default_object:
                msg = (
                    f"Default-object references for intrinsic "
                    f"{definition.path!r} are not supported yet"
                )
                raise NotImplementedError(msg)

            package_name, _, name = definition.path.partition(".")

            package_reference = self.ensure_import(package_name, ReferencePath(), "Core", "Package")

            return self.ensure_import(
                name, package_reference, definition.class_package, definition.class_name
            )

        if definition.is_interface:
            msg = (
                f"Cannot reference interface {class_path!r} as a local export: "
                "interface compilation is not supported yet"
            )
            raise CompilationError(msg)

        package_key = class_path.partition(".")[0]

        if package_key == self.config.name.casefold():
            exports = self.classes[class_path]
            obj = exports.default_object if default_object else exports.class_object
            return obj.reference()

        config = next(
            config for config in self.context.packages if config.name.casefold() == package_key
        )

        package_reference = self.ensure_import(config.name, ReferencePath(), "Core", "Package")

        if default_object:
            return self.ensure_import(
                f"Default__{definition.name}", package_reference, config.name, definition.name
            )

        return self.ensure_import(definition.name, package_reference, "Core", "Class")

    def enum_reference(self, enum_path: str) -> ReferencePath:
        owner_path, separator, name = enum_path.rpartition(".")

        if not separator:
            msg = f"Expected a qualified enum path: {enum_path}"
            raise ValueError(msg)

        member = self.context.references.resolve_enum(owner_path, name, self.context.parents)

        outer = self.class_object_reference(member.owner_class)
        package_name = member.owner_class.partition(".")[0]

        if package_name.casefold() == self.config.name.casefold():
            reference = outer + FName(member.declaration.name)

            # Local enum exports must already have been built.
            return self.package.lookup_object_by_path(reference).reference()

        return self.ensure_import(member.declaration.name, outer, "Core", "Enum")

    def struct_reference(self, struct_path: str) -> ReferencePath:
        owner_path, separator, name = struct_path.rpartition(".")

        if not separator:
            msg = f"Expected a qualified struct path: {struct_path}"
            raise ValueError(msg)

        member = self.context.references.resolve_struct(owner_path, name, self.context.parents)

        path = f"{member.owner_class}.{member.declaration.name}".casefold()
        package_name = member.owner_class.partition(".")[0]

        if package_name.casefold() == self.config.name.casefold():
            return self.structs[path].struct_object.reference()

        outer = self.class_object_reference(member.owner_class)

        return self.ensure_import(member.declaration.name, outer, "Core", "ScriptStruct")

    def function_reference(self, function_path: str) -> ReferencePath:
        owner_path, separator, name = function_path.rpartition(".")

        if not separator:
            msg = f"Expected a qualified function path: {function_path}"
            raise ValueError(msg)

        member = self.context.references.resolve_function(owner_path, name, self.context.parents)

        outer = self.class_object_reference(member.owner_class)
        package_name = member.owner_class.partition(".")[0]

        if package_name.casefold() == self.config.name.casefold():
            reference = outer + FName(member.declaration.name)
            return self.package.lookup_object_by_path(reference).reference()

        return self.ensure_import(member.declaration.name, outer, "Core", "Function")
