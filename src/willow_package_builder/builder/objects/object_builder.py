from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from willow_package_builder.builder.build_component import BuildComponent
from willow_package_builder.compiler.semantics.types import TypeCategory
from willow_package_builder.compiler.syntax.modifiers import VariableModifier
from willow_package_builder.logging import ValueBuildError, info
from willow_package_builder.logging.diagnostics import ObjectDefinitionError
from willow_package_builder.objects.declarations import (
    FolderDeclaration,
    ObjectDeclaration,
    ObjectFlag,
)
from willow_package_builder.objects.reader import walk_objects_directory
from willow_package_builder.package_config import collect_visible_packages
from willow_package_builder.payloads.instance_payload import ObjectInstancePayload
from willow_package_builder.properties.merge import merge_values
from willow_package_builder.properties.values import ArrayValue, Value
from willow_package_builder.upackage import ExportFlags, FName, ObjectFlags, ReferencePath, UObject

if TYPE_CHECKING:
    from willow_package_builder.builder.classes.struct_builder import StructBuilder
    from willow_package_builder.builder.references import PackageReferences
    from willow_package_builder.builder.value_builder import ValueBuilder


@dataclass
class ObjectBuilder(BuildComponent):
    references: PackageReferences
    struct_builder: StructBuilder
    values: ValueBuilder

    declarations: list[FolderDeclaration | ObjectDeclaration] = field(
        default_factory=list, init=False
    )
    exports: dict[FolderDeclaration | ObjectDeclaration, UObject] = field(
        default_factory=dict, init=False
    )

    def read_objects(self) -> None:
        directory = self.config.directory / "Objects"

        if not directory.exists():
            self.declarations = []
            return

        self.declarations = walk_objects_directory(directory)
        for declaration in self.declarations:
            if isinstance(declaration, ObjectDeclaration) and isinstance(
                declaration.outer, FolderDeclaration
            ):
                declaration.flags |= {ObjectFlag.PUBLIC, ObjectFlag.KEEP_ALIVE}

    def construct_objects(self) -> None:
        visible = collect_visible_packages(self.config, self.context.packages)

        for declaration in self.declarations:
            if declaration.outer is None:
                outer = ReferencePath()
            else:
                outer = self.exports[declaration.outer].reference()

            export_flags = ExportFlags.NONE
            flags = ObjectFlags.DEFAULT_EXPORT

            match declaration:
                case FolderDeclaration():
                    flags |= ObjectFlags.PUBLIC
                    class_path = "Core.Package"
                    object_class = self.references.class_object_reference(class_path)
                    archetype = ReferencePath()

                    if declaration.outer is None:
                        export_flags = ExportFlags.FORCED_EXPORT

                case ObjectDeclaration():
                    if ObjectFlag.PUBLIC in declaration.flags:
                        flags |= ObjectFlags.PUBLIC

                    if declaration.outer is None:
                        msg = (
                            f"{declaration.source}, document {declaration.document}: "
                            "Objects must be placed inside a logical package directory"
                        )
                        raise ObjectDefinitionError(msg)

                    class_path, _ = self.context.references.resolve_class(
                        declaration.class_name, self.config.name, visible
                    )

                    object_class = self.references.class_object_reference(class_path)
                    archetype = self.references.class_object_reference(
                        class_path, default_object=True
                    )

            obj = self.construct_object(
                class_path,
                object_class,
                FName(declaration.name),
                outer,
                flags,
                archetype,
                export_flags,
            )
            self.exports[declaration] = obj

            if isinstance(declaration, ObjectDeclaration):
                class_name = str(obj.object_class).rsplit(".", 1)[-1]
                info(f"Building object {class_name}'{obj.reference()}'")

    def property_default_value(self, class_path: str, name: FName) -> Value:
        member = self.context.references.resolve_variable(
            class_path, str(name), self.context.parents
        )
        definition = member.declaration
        package_name = member.owner_class.partition(".")[0]
        config = next(
            config
            for config in self.context.packages
            if config.name.casefold() == package_name.casefold()
        )
        visible = collect_visible_packages(config, self.context.packages)
        resolved = self.context.references.resolve_type(
            definition.type_ref, member.owner_class, visible, self.context.parents
        )

        if definition.array_dimension == 1:
            initial = self.struct_builder.initial_value(resolved)
        else:
            initial = ArrayValue(
                [
                    self.struct_builder.initial_value(resolved)
                    for _ in range(definition.array_dimension)
                ]
            )

        values = {name: initial}
        hierarchy = list(
            self.context.references.iter_class_hierarchy(class_path, self.context.parents)
        )

        for _, declaration in reversed(hierarchy):
            if name in declaration.defaults:
                values = merge_values(values, {name: declaration.defaults[name]})

        return values[name]

    def _build_properties(
        self, declaration: ObjectDeclaration, visible_packages: set[str]
    ) -> dict[FName, Value]:
        context = f"{declaration.source}, document {declaration.document}"
        class_path, _ = self.context.references.resolve_class(
            declaration.class_name, self.config.name, visible_packages
        )

        defaults: dict[FName, Value] = {}

        # Obtain defaults only for supplied scalar struct properties.
        for supplied_name in declaration.properties:
            member = self.context.references.resolve_variable(
                class_path, supplied_name, self.context.parents
            )
            definition = member.declaration
            resolved = self.values.resolve_field_type(definition, member.owner_class)

            if resolved.category is TypeCategory.STRUCT and definition.array_dimension == 1:
                name = FName(definition.name)
                defaults[name] = self.property_default_value(class_path, name)

        return self.values.build_class_values(context, class_path, declaration.properties, defaults)

    def build_all_properties(self) -> None:
        visible = collect_visible_packages(self.config, self.context.packages)

        for declaration in self.declarations:
            if not isinstance(declaration, ObjectDeclaration):
                continue

            payload = self.exports[declaration].payload

            if not isinstance(payload, ObjectInstancePayload):
                msg = f"Object has an invalid payload: {declaration.source}"
                raise ValueError(msg)  # noqa: TRY004

            try:
                payload.properties = self._build_properties(declaration, visible)
            except ValueBuildError as error:
                msg = str(error)
                raise ObjectDefinitionError(msg) from error

    def construct_object(
        self,
        class_path: str,
        object_class: ReferencePath,
        name: FName,
        outer: ReferencePath,
        flags: ObjectFlags = ObjectFlags.DEFAULT_EXPORT,
        archetype: ReferencePath | None = None,
        export_flags: ExportFlags = ExportFlags.NONE,
        properties: dict[FName, Value] | None = None,
    ) -> UObject:
        obj = UObject(
            name,
            flags,
            outer,
            object_class,
            archetype=ReferencePath() if archetype is None else archetype,
            export_flags=export_flags,
            payload=ObjectInstancePayload(
                class_path, self.context, {} if properties is None else deepcopy(properties)
            ),
        )

        self.package.add_export(obj)
        return obj

    def class_default_values(self, class_path: str) -> dict[FName, Value]:
        values: dict[FName, Value] = {}
        hierarchy = list(
            self.context.references.iter_class_hierarchy(class_path, self.context.parents)
        )

        for owner, declaration in reversed(hierarchy):
            package_name = owner.partition(".")[0]
            config = next(
                config
                for config in self.context.packages
                if config.name.casefold() == package_name.casefold()
            )
            visible = collect_visible_packages(config, self.context.packages)

            for variable in declaration.variables:
                if VariableModifier.NATIVE in variable.modifiers:
                    continue

                name = FName(variable.name)

                if name in values:
                    continue

                resolved = self.context.references.resolve_type(
                    variable.type_ref, owner, visible, self.context.parents
                )

                if variable.array_dimension == 1:
                    values[name] = self.struct_builder.initial_value(resolved)
                else:
                    values[name] = ArrayValue(
                        [
                            self.struct_builder.initial_value(resolved)
                            for _ in range(variable.array_dimension)
                        ]
                    )

            values = merge_values(values, declaration.defaults)

        return values

    def construct_cdo(self, class_path: str, class_object: UObject) -> UObject:
        parent = self.context.parents[class_path.casefold()]
        archetype = ReferencePath()

        if parent is not None:
            archetype = self.references.class_object_reference(parent, default_object=True)

        return self.construct_object(
            class_path,
            class_object.reference(),
            FName(f"Default__{class_object.name}"),
            class_object.outer,
            ObjectFlags.CDO_EXPORT,
            archetype,
            properties=self.class_default_values(class_path),
        )
