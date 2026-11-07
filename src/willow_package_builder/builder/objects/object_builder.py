from copy import deepcopy
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from willow_package_builder.builder.build_component import BuildComponent
from willow_package_builder.compiler.semantics.types import TypeCategory
from willow_package_builder.compiler.syntax.modifiers import VariableModifier
from willow_package_builder.logging import CompilationError, ValueBuildError, info
from willow_package_builder.logging.diagnostics import ObjectDefinitionError
from willow_package_builder.objects.definitions import (
    Definition,
    FolderDefinition,
    ObjectDefinition,
    ObjectDefinitionFlag,
)
from willow_package_builder.objects.reader import walk_objects_directory
from willow_package_builder.package_config import OBJECTS_DIRECTORY_NAME, collect_visible_packages
from willow_package_builder.payloads.instance_payload import ObjectInstancePayload
from willow_package_builder.properties.merge import merge_values
from willow_package_builder.properties.object_references import import_external_object
from willow_package_builder.properties.reference_text import parse_reference_text
from willow_package_builder.properties.values import ArrayValue, ObjectValue, Value
from willow_package_builder.upackage import (
    CORE_PACKAGE_CLASS_PATH,
    DEFAULT_OBJECT_PREFIX,
    ExportFlags,
    ExternalReference,
    FName,
    ObjectFlags,
    ReferencePath,
    UObject,
)

if TYPE_CHECKING:
    from willow_package_builder.builder.classes.struct_builder import StructBuilder
    from willow_package_builder.builder.references import PackageReferences
    from willow_package_builder.builder.value_builder import ValueBuilder


@dataclass
class ObjectBuilder(BuildComponent):
    references: PackageReferences
    struct_builder: StructBuilder
    values: ValueBuilder

    definitions: list[Definition] = field(default_factory=list, init=False)
    exports: dict[Definition, UObject] = field(default_factory=dict, init=False)

    def read_objects(self) -> None:
        directory = self.config.directory / OBJECTS_DIRECTORY_NAME

        if not directory.exists():
            self.definitions = []
            return

        self.definitions = walk_objects_directory(directory)
        for definition in self.definitions:
            if isinstance(definition, ObjectDefinition) and isinstance(
                definition.outer, FolderDefinition
            ):
                definition.flags |= {ObjectDefinitionFlag.PUBLIC, ObjectDefinitionFlag.KEEP_ALIVE}

    def construct_objects(self) -> None:
        visible = collect_visible_packages(self.config, self.context.packages)

        for definition in self.definitions:
            if definition.outer is None:
                outer = ReferencePath()
            else:
                outer = self.exports[definition.outer].reference()

            export_flags = ExportFlags.NONE
            flags = ObjectFlags.DEFAULT_EXPORT

            match definition:
                case FolderDefinition():
                    flags |= ObjectFlags.PUBLIC
                    class_path = CORE_PACKAGE_CLASS_PATH
                    object_class = self.references.class_object_reference(class_path)
                    archetype = ReferencePath()

                    if definition.outer is None:
                        export_flags = ExportFlags.FORCED_EXPORT

                case ObjectDefinition():
                    if ObjectDefinitionFlag.PUBLIC in definition.flags:
                        flags |= ObjectFlags.PUBLIC

                    if definition.outer is None:
                        msg = (
                            f"{definition.source}, document {definition.document}: "
                            "Objects must be placed inside a logical package directory"
                        )
                        raise ObjectDefinitionError(msg)

                    class_path, _ = self.context.references.resolve_class(
                        definition.class_name, self.config.name, visible
                    )

                    object_class = self.references.class_object_reference(class_path)
                    archetype = self.references.class_object_reference(
                        class_path, default_object=True
                    )

                case _:
                    msg = f"Got unknown definition {definition}"
                    raise ValueError(msg)

            obj = self.construct_object(
                class_path, object_class, definition.name, outer, flags, archetype, export_flags
            )
            self.exports[definition] = obj

            if isinstance(definition, ObjectDefinition):
                class_name = str(obj.object_class).rsplit(".", 1)[-1]
                info(f"Building object {self.package.format_object(obj)}")

    def property_default_value(self, class_path: ReferencePath, name: FName) -> Value:
        member = self.context.references.resolve_variable(class_path, name, self.context.parents)
        definition = member.declaration
        if member.owner_class.outer is None:
            msg = f"Expected qualified class, got {member.owner_class}"
            raise ValueError(msg)
        package_name = member.owner_class.outer.name
        config = next(config for config in self.context.packages if config.name == package_name)
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
        self, definition: ObjectDefinition, visible_packages: set[FName]
    ) -> dict[FName, Value]:
        context = f"{definition.source}, document {definition.document}"
        class_path, _ = self.context.references.resolve_class(
            definition.class_name, self.config.name, visible_packages
        )

        defaults: dict[FName, Value] = {}

        # Obtain defaults only for supplied scalar struct properties.
        for supplied_name in definition.properties:
            member = self.context.references.resolve_variable(
                class_path, supplied_name, self.context.parents
            )
            var_declaration = member.declaration
            resolved = self.values.resolve_field_type(var_declaration, member.owner_class)

            if resolved.category is TypeCategory.STRUCT:
                name = var_declaration.name
                defaults[name] = self.archetype_property_value(
                    self.exports[definition], class_path, name
                )

        obj = self.exports[definition]
        values = replace(
            self.values,
            reference_base=obj.reference(),
            external_archetype=self.external_archetype(obj),
            known_archetype_properties=self.known_archetype_properties(obj),
        )
        return values.build_class_values(context, class_path, definition.properties, defaults)

    def build_all_properties(self) -> None:
        """Build properties in archetype dependency order."""
        visible = collect_visible_packages(self.config, self.context.packages)
        definitions = {
            obj.reference(): definition
            for definition, obj in self.exports.items()
            if isinstance(definition, ObjectDefinition)
        }
        completed: set[ReferencePath] = set()

        for start in definitions:
            chain: list[ReferencePath] = []
            active: set[ReferencePath] = set()
            current = start

            while current in definitions and current not in completed:
                if current in active:
                    msg = f"Object archetype cycle at {current}"
                    raise ObjectDefinitionError(msg)

                active.add(current)
                chain.append(current)
                current = self.exports[definitions[current]].archetype

            for reference in reversed(chain):
                declaration = definitions[reference]
                payload = self.exports[declaration].payload

                if not isinstance(payload, ObjectInstancePayload):
                    msg = f"Object has an invalid payload: {declaration.source}"
                    raise ValueError(msg)  # noqa: TRY004

                try:
                    payload.properties = self._build_properties(declaration, visible)
                except ValueBuildError as error:
                    msg = str(error)
                    raise ObjectDefinitionError(msg) from error

                completed.add(reference)

    def construct_object(
        self,
        class_path: ReferencePath,
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

    def class_default_values(self, class_path: ReferencePath) -> dict[FName, Value]:
        values: dict[FName, Value] = {}
        hierarchy = list(
            self.context.references.iter_class_hierarchy(class_path, self.context.parents)
        )

        for owner, declaration in reversed(hierarchy):
            package_name = owner.get_outer().name
            config = next(config for config in self.context.packages if config.name == package_name)
            visible = collect_visible_packages(config, self.context.packages)

            for variable in declaration.variables:
                if VariableModifier.NATIVE in variable.modifiers:
                    continue

                name = variable.name

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

    def construct_cdo(self, class_path: ReferencePath, class_object: UObject) -> UObject:
        parent = self.context.parents[class_path]
        archetype = ReferencePath()

        if parent is not None:
            archetype = self.references.class_object_reference(parent, default_object=True)

        return self.construct_object(
            class_path,
            class_object.reference(),
            FName(f"{DEFAULT_OBJECT_PREFIX}{class_object.name}"),
            class_object.outer,
            ObjectFlags.CDO_EXPORT,
            archetype,
            properties=self.class_default_values(class_path),
        )

    def link_archetypes(self) -> None:
        """Link explicitly supplied local archetypes after reserving all objects."""
        for definition, obj in self.exports.items():
            if not isinstance(definition, ObjectDefinition):
                continue

            if definition.archetype is None:
                continue

            context = f"{definition.source}, document {definition.document}"
            annotation, path = parse_reference_text(
                context, definition.archetype, definition.reference
            )

            try:
                target = self.package.lookup_object_by_path(path)
            except KeyError:
                target = None

            if target is None or isinstance(target, ExternalReference):
                visible = collect_visible_packages(self.config, self.context.packages)
                expected_class, _ = self.context.references.resolve_class(
                    definition.class_name, self.config.name, visible
                )
                external_class = expected_class

                if annotation is not None:
                    try:
                        external_class = self.context.references.resolve_class_path(
                            annotation, self.config.name, visible, include_intrinsics=True
                        )
                    except CompilationError as error:
                        msg = f"{context}: {error}"
                        raise ObjectDefinitionError(msg) from error

                    if external_class != expected_class:
                        msg = (
                            f"{context}: External archetype {path!r} must have "
                            f"the same class as {self.package.format_object(obj)}"
                        )
                        raise ObjectDefinitionError(msg)

                if isinstance(target, ExternalReference):
                    imported_class = ReferencePath(target.class_package) + target.class_name

                    if imported_class != external_class:
                        msg = (
                            f"{context}: Archetype {path!r} is already imported "
                            f"as {imported_class}, expected {external_class}"
                        )
                        raise ObjectDefinitionError(msg)

                obj.archetype = import_external_object(
                    ObjectValue(external_class, path), self.package, self.context
                )
                continue

            if not isinstance(target, UObject) or not isinstance(
                target.payload, ObjectInstancePayload
            ):
                msg = f"{context}: Archetype {path!r} must be an object instance"
                raise ObjectDefinitionError(msg)

            if target is obj:
                msg = f"{context}: Object cannot be its own archetype"
                raise ObjectDefinitionError(msg)

            if obj.object_class != target.object_class:
                msg = (
                    f"{context}: Archetype {path!r} must have the same class as "
                    f"{self.package.format_object(obj)}"
                )
                raise ObjectDefinitionError(msg)

            if annotation is not None:
                visible = collect_visible_packages(self.config, self.context.packages)

                try:
                    annotation_path = self.context.references.resolve_class_path(
                        annotation, self.config.name, visible, include_intrinsics=True
                    )
                except CompilationError as error:
                    msg = f"{context}: {error}"
                    raise ObjectDefinitionError(msg) from error

                if not self.context.references.is_subclass(
                    target.payload.class_path, annotation_path, self.context.parents
                ):
                    msg = (
                        f"{context}: Archetype {path!r} does not match "
                        f"class annotation {annotation!r}"
                    )
                    raise ObjectDefinitionError(msg)

            obj.archetype = target.reference()

    def validate_archetype_cycles(self) -> None:
        """Reject cycles between explicitly linked object archetypes."""
        objects = {
            obj.reference(): obj
            for definition, obj in self.exports.items()
            if isinstance(definition, ObjectDefinition)
        }
        completed: set[ReferencePath] = set()

        for start in objects:
            chain: list[ReferencePath] = []
            positions: dict[ReferencePath, int] = {}
            current = start

            while current in objects and current not in completed:
                if current in positions:
                    cycle = chain[positions[current] :] + [current]
                    paths = " -> ".join(self.package.object_path(objects[path]) for path in cycle)
                    msg = f"Object archetype cycle: {paths}"
                    raise ObjectDefinitionError(msg)

                positions[current] = len(chain)
                chain.append(current)
                current = objects[current].archetype

            completed.update(chain)

    def archetype_property_value(
        self, obj: UObject, class_path: ReferencePath, name: FName
    ) -> Value:
        """Find a property's effective value before this object's overrides."""
        values = {name: self.property_default_value(class_path, name)}
        overrides: list[Value] = []
        visited: set[ReferencePath] = set()
        current = obj.archetype

        while not current.is_none():
            if current in visited:
                msg = f"Object archetype cycle at {current}"
                raise ObjectDefinitionError(msg)

            visited.add(current)
            target = self.package.lookup_object_by_path(current)

            if not isinstance(target, UObject):
                # External archetype values are unavailable.
                break

            payload = target.payload

            if not isinstance(payload, ObjectInstancePayload):
                msg = f"Archetype has an invalid payload: {target.reference()}"
                raise ValueError(msg)  # noqa: TRY004

            if name in payload.properties:
                overrides.append(payload.properties[name])

            current = target.archetype

        for override in reversed(overrides):
            values = merge_values(values, {name: override})

        return values[name]

    def external_archetype(self, obj: UObject) -> ReferencePath | None:
        """Find an external archetype whose property values are unavailable."""
        visited: set[ReferencePath] = set()
        current = obj

        while not current.archetype.is_none():
            reference = current.reference()

            if reference in visited:
                msg = f"Object archetype cycle at {reference}"
                raise ObjectDefinitionError(msg)

            visited.add(reference)
            payload = current.payload

            if not isinstance(payload, ObjectInstancePayload):
                msg = f"Object has an invalid payload: {reference}"
                raise ValueError(msg)  # noqa: TRY004

            class_default = self.references.class_object_reference(
                payload.class_path, default_object=True
            )

            if current.archetype == class_default:
                return None

            target = self.package.lookup_object_by_path(current.archetype)

            if isinstance(target, ExternalReference):
                return target.reference()

            current = target

        return None

    def known_archetype_properties(self, obj: UObject) -> frozenset[FName]:
        """Find properties explicitly serialized by internal archetypes."""
        known: set[FName] = set()
        visited: set[ReferencePath] = set()
        current = obj.archetype

        while not current.is_none():
            if current in visited:
                msg = f"Object archetype cycle at {current}"
                raise ObjectDefinitionError(msg)

            visited.add(current)
            target = self.package.lookup_object_by_path(current)

            if isinstance(target, ExternalReference):
                break

            payload = target.payload

            if not isinstance(payload, ObjectInstancePayload):
                msg = f"Archetype has an invalid payload: {target.reference()}"
                raise ValueError(msg)  # noqa: TRY004

            known.update(payload.properties)
            current = target.archetype

        return frozenset(known)
