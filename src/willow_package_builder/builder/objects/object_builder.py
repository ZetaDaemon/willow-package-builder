from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field, replace
from functools import partial
from typing import TYPE_CHECKING, cast

from willow_package_builder.builder.build_component import BuildComponent
from willow_package_builder.compiler.semantics.types import TypeCategory
from willow_package_builder.compiler.syntax.modifiers import VariableModifier
from willow_package_builder.handlers.registry import get_class_handler
from willow_package_builder.logging import (
    CompilationError,
    UnknownPropertyError,
    ValueBuildError,
    info,
)
from willow_package_builder.logging.diagnostics import ObjectDefinitionError
from willow_package_builder.objects.definitions import (
    Definition,
    FolderDefinition,
    ObjectDefinition,
    ObjectDefinitionFlag,
)
from willow_package_builder.objects.reader import walk_objects_directory
from willow_package_builder.package_config import OBJECTS_DIRECTORY_NAME, collect_visible_packages
from willow_package_builder.payloads.class_payload import ClassFlags, UClassPayload
from willow_package_builder.payloads.instance_payload import (
    ComponentTemplatePayload,
    ObjectInstancePayload,
)
from willow_package_builder.properties.conversion import value_to_python
from willow_package_builder.properties.merge import merge_values
from willow_package_builder.properties.object_references import import_external_object
from willow_package_builder.properties.reference_text import parse_reference_text
from willow_package_builder.properties.values import (
    ArrayValue,
    DelegateValue,
    ObjectValue,
    StructValue,
    Value,
)
from willow_package_builder.upackage import (
    CORE_COMPONENT_PATH,
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
    from willow_package_builder.builder.classes.default_objects import DefaultObjectTemplate
    from willow_package_builder.builder.classes.struct_builder import StructBuilder
    from willow_package_builder.builder.references import PackageReferences
    from willow_package_builder.builder.value_builder import ValueBuilder
    from willow_package_builder.compiler.syntax.declarations import (
        TypeReference,
        VariableDeclaration,
    )
    from willow_package_builder.handlers.classes.class_handler import ClassHandler


@dataclass
class _InstancingState:
    generated: dict[tuple[ReferencePath, ReferencePath], ObjectValue] = field(default_factory=dict)
    owners: list[UObject] = field(default_factory=list)


@dataclass
class ObjectBuilder(BuildComponent):
    references: PackageReferences
    struct_builder: StructBuilder
    values: ValueBuilder

    definitions: list[Definition] = field(default_factory=list, init=False)
    exports: dict[Definition, UObject] = field(default_factory=dict, init=False)

    def _register_generated_object(
        self, definition: ObjectDefinition, registered: dict[ReferencePath, Definition]
    ) -> None:
        """Register a generated definition before object construction."""
        outer = definition.outer

        if outer is None or registered.get(outer.reference) is not outer:
            msg = (
                f"Generated object {definition.name} requires "
                "an already registered outer definition"
            )
            raise ValueError(msg)

        path = definition.reference

        if path in registered:
            msg = f"Generated object duplicates an existing definition: {path}"
            raise ValueError(msg)

        registered[path] = definition
        self.definitions.append(definition)

        if definition not in outer.children:
            outer.children.append(definition)

    def prepare_definitions(self) -> None:
        """Attach handlers and discover additional object definitions."""
        visible = collect_visible_packages(self.config, self.context.packages)
        pending = deque(self.definitions)
        registered = {definition.reference: definition for definition in self.definitions}

        while pending:
            definition = pending.popleft()

            if not isinstance(definition, ObjectDefinition):
                continue

            if isinstance(definition.outer, FolderDefinition):
                definition.flags |= {ObjectDefinitionFlag.PUBLIC, ObjectDefinitionFlag.KEEP_ALIVE}

            class_path, _ = self.context.references.resolve_class(
                definition.class_name, self.config.name, visible
            )
            handler_type = get_class_handler(
                class_path, self.context.references, self.context.parents
            )

            if handler_type is None:
                definition.handler = None
                continue

            self._validate_handler_fields(class_path, handler_type)
            handler = handler_type(definition, self.state)
            definition.handler = handler

            for generated in handler.discover():
                self._register_generated_object(generated, registered)
                pending.append(generated)

    def read_objects(self) -> None:
        directory = self.config.directory / OBJECTS_DIRECTORY_NAME

        if not directory.exists():
            self.definitions = []
            return

        self.definitions = walk_objects_directory(directory)

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

                    class_path, class_declaration = self.context.references.resolve_class(
                        definition.class_name, self.config.name, visible
                    )

                    if class_declaration.is_abstract:
                        msg = (
                            f"{definition.source}, document {definition.document}: "
                            f"Cannot construct abstract class {class_path}"
                        )
                        raise ObjectDefinitionError(msg)

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

        properties = definition.properties

        if definition.handler is not None:
            handler = definition.handler
            handled = handler.EXTRA_FIELDS.keys() | handler.HANDLED_PROPERTIES
            properties = {name: value for name, value in properties.items() if name not in handled}

        defaults: dict[FName, Value] = {}

        # Obtain defaults only for supplied scalar struct properties.
        for supplied_name in properties:
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
        return values.build_class_values(context, class_path, properties, defaults)

    def _build_handler_extras(self, handler: ClassHandler, obj: UObject) -> dict[FName, Value]:
        """Convert typed handler inputs without adding them to object properties."""
        definition = handler.definition
        values = replace(
            self.values,
            reference_base=obj.reference(),
            external_archetype=None,
            known_archetype_properties=frozenset(),
        )
        result: dict[FName, Value] = {}

        for name, resolved_type in handler.EXTRA_FIELDS.items():
            if resolved_type is None or name not in definition.properties:
                continue

            context = f"{definition.source}, document {definition.document}, extra field {name}"
            result[name] = values.build_value(context, definition.properties[name], resolved_type)

        return result

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
                definition = definitions[reference]
                obj = self.exports[definition]
                payload = obj.payload

                if not isinstance(payload, ObjectInstancePayload):
                    msg = f"Object has an invalid payload: {definition.source}"
                    raise ValueError(msg)  # noqa: TRY004

                try:
                    payload.properties = self._build_properties(definition, visible)

                    if definition.handler is not None:
                        handler = definition.handler
                        handler.extra_values = self._build_handler_extras(handler, obj)
                        payload.handler = handler
                        payload.owner = obj
                        handler.object_reference.bind(
                            partial(self._read_handler_field, handler, obj),
                            partial(self._write_handler_field, handler, obj),
                        )
                        handler.initialize(obj)

                except ValueBuildError as error:
                    msg = str(error)
                    raise ObjectDefinitionError(msg) from error

                completed.add(reference)
                self.construct_instanced_properties(obj, definition.properties)

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

    def _cdo_properties(self, class_path: ReferencePath) -> dict[FName, Value]:
        declaration = self.context.references.classes[class_path]
        properties = deepcopy(declaration.defaults)
        visible = collect_visible_packages(self.config, self.context.packages)

        for variable in declaration.variables:
            if variable.name in properties or VariableModifier.NATIVE in variable.modifiers:
                continue

            resolved = self.context.references.resolve_type(
                variable.type_ref, class_path, visible, self.context.parents
            )
            if resolved.category is not TypeCategory.STRUCT:
                continue

            if variable.array_dimension == 1:
                properties[variable.name] = self.struct_builder.initial_value(resolved)
            else:
                properties[variable.name] = ArrayValue(
                    [
                        self.struct_builder.initial_value(resolved)
                        for _ in range(variable.array_dimension)
                    ]
                )

        return properties

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
            properties=self._cdo_properties(class_path),
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

    def _validate_handler_fields(
        self, class_path: ReferencePath, handler: type[ClassHandler]
    ) -> None:
        """Validate the handler's extra fields and claimed class properties."""
        references = self.context.references
        parents = self.context.parents

        for name in handler.HANDLED_PROPERTIES:
            try:
                references.resolve_variable(class_path, name, parents)
            except UnknownPropertyError as error:
                msg = (
                    f"{handler.__name__} claims property {name}, "
                    f"but it does not exist on {class_path}"
                )
                raise ValueError(msg) from error

        for name in handler.EXTRA_FIELDS:
            try:
                references.resolve_variable(class_path, name, parents)
            except UnknownPropertyError:
                continue

            msg = (
                f"{handler.__name__} declares extra field {name}, "
                f"but it is already a property of {class_path}"
            )
            raise ValueError(msg)

    def prepare_handlers(self) -> None:
        """Prepare handler data after all objects have been initialized."""
        for definition in self.definitions:
            if not isinstance(definition, ObjectDefinition):
                continue

            if definition.handler is None:
                continue

            obj = self.exports[definition]
            definition.handler.prepare(obj)

    @staticmethod
    def _handler_payload(obj: UObject) -> ObjectInstancePayload:
        """Get the instance payload used by handler property access."""
        payload = obj.payload

        if not isinstance(payload, ObjectInstancePayload):
            msg = f"Object has no instance payload: {obj.reference()}"
            raise TypeError(msg)

        return payload

    def _read_handler_field(self, handler: ClassHandler, obj: UObject, name: FName) -> object:
        """Read handler input or an effective constructed property."""
        definition = handler.definition

        if name in handler.EXTRA_FIELDS:
            try:
                if handler.EXTRA_FIELDS[name] is None:
                    return deepcopy(definition.properties[name])

                return value_to_python(handler.extra_values[name])
            except KeyError:
                msg = f"Object {definition.reference} has no extra field {name}"
                raise AttributeError(msg) from None

        payload = self._handler_payload(obj)
        member = self.context.references.resolve_variable(
            payload.class_path, name, self.context.parents
        )
        name = member.declaration.name

        if name in payload.properties:
            return value_to_python(payload.properties[name])

        if name in handler.HANDLED_PROPERTIES and name in definition.properties:
            return deepcopy(definition.properties[name])

        external = self.external_archetype(obj)

        if external is not None and name not in self.known_archetype_properties(obj):
            msg = (
                f"Cannot determine {obj.reference()}.{name}: "
                f"external archetype values are unavailable for {external}"
            )
            raise NotImplementedError(msg)

        value = self.archetype_property_value(obj, payload.class_path, name)
        return value_to_python(value)

    def _write_handler_field(
        self, handler: ClassHandler, obj: UObject, name: FName, value: object
    ) -> None:
        """Update handler input or construct an explicit property override."""
        definition = handler.definition

        if name in handler.EXTRA_FIELDS:
            resolved = handler.EXTRA_FIELDS[name]

            if resolved is not None:
                values = replace(
                    self.values,
                    reference_base=obj.reference(),
                    external_archetype=None,
                    known_archetype_properties=frozenset(),
                )
                context = f"{definition.source}, document {definition.document}, extra field {name}"
                handler.extra_values[name] = values.build_value(context, value, resolved)

            definition.properties[name] = deepcopy(value)
            return

        payload = self._handler_payload(obj)
        member = self.context.references.resolve_variable(
            payload.class_path, name, self.context.parents
        )
        variable = member.declaration
        name = variable.name
        resolved = self.values.resolve_field_type(variable, member.owner_class)

        existing = payload.properties.get(name)

        if existing is None and resolved.category is TypeCategory.STRUCT:
            existing = self.archetype_property_value(obj, payload.class_path, name)

        known = self.known_archetype_properties(obj)
        external = self.external_archetype(obj)

        if name in payload.properties or name in known:
            external = None

        values = replace(
            self.values,
            reference_base=obj.reference(),
            external_archetype=external,
            known_archetype_properties=known,
        )
        context = f"{definition.source}, document {definition.document}, property {name}"

        payload.properties[name] = values.build_field_value(
            context, variable, value, resolved, existing
        )

    @staticmethod
    def properties_are_instanced(modifiers: tuple[VariableModifier, ...]) -> bool:
        """Recognize the equivalent instanced property modifier forms."""
        return VariableModifier.INSTANCED in modifiers or (
            VariableModifier.EXPORT in modifiers and VariableModifier.EDIT_INLINE in modifiers
        )

    def _construct_instanced_reference(
        self, obj: UObject, property_name: FName, value: ObjectValue, instancing: _InstancingState
    ) -> ObjectValue | None:
        """Construct or reuse a child from an available local template."""
        candidates = [value.path]
        parts = value.path.full_split()

        if parts and parts[0] == self.package.name:
            candidates.append(ReferencePath(".".join(str(part) for part in parts[1:])))

        template = None

        for path in candidates:
            try:
                template = self.package.lookup_object_by_path(path)
            except KeyError:
                continue
            break

        if template is None or isinstance(template, ExternalReference):
            return None

        template_path = template.reference()

        destination = obj

        for ancestor in reversed(instancing.owners):
            if template_path == ancestor.archetype:
                ancestor_payload = ancestor.payload
                if not isinstance(ancestor_payload, ObjectInstancePayload):
                    msg = f"Instancing owner has no instance payload: {ancestor.reference()}"
                    raise TypeError(msg)
                return ObjectValue(ancestor_payload.class_path, ancestor.reference())

            if template.outer == ancestor.archetype:
                destination = ancestor
                break

        outer = destination.reference()
        key = (outer, template_path)

        if key in instancing.generated:
            return deepcopy(instancing.generated[key])

        template_payload = template.payload

        if not isinstance(template_payload, ObjectInstancePayload):
            msg = f"Instanced template has no instance payload: {value.path}"
            raise TypeError(msg)

        if template_payload.handler is not None:
            msg = (
                f"Instancing objects with custom payload handlers "
                f"is not implemented yet: {value.path}"
            )
            raise NotImplementedError(msg)

        child_path = outer + template.name

        try:
            self.package.lookup_object_by_path(child_path)
        except KeyError:
            pass
        else:
            msg = (
                f"{obj.reference()}: Cannot generate {child_path}; "
                f"assign property {property_name} explicitly to use the existing child"
            )
            raise ObjectDefinitionError(msg)

        flags = ObjectFlags.DEFAULT_EXPORT

        if destination.flags & ObjectFlags.ARCHETYPE_OBJECT:
            flags |= ObjectFlags.ARCHETYPE_OBJECT

        child = self.construct_object(
            template_payload.class_path,
            template.object_class,
            template.name,
            outer,
            flags,
            template_path,
        )
        reference = ObjectValue(template_payload.class_path, child.reference())
        instancing.generated[key] = reference
        self.construct_instanced_properties(child, {}, instancing)
        return deepcopy(reference)

    def _construct_instanced_field_value(
        self,
        obj: UObject,
        property_name: FName,
        value: Value,
        variable: VariableDeclaration,
        owner_class: ReferencePath,
        instancing: _InstancingState,
        *,
        supplied: bool = False,
        raw_value: object = None,
    ) -> Value | None:
        """Instance references in a scalar or fixed-array field."""
        overrides: dict[FName, object] | None = None

        if supplied:
            resolved = self.values.resolve_field_type(variable, owner_class)

            if variable.array_dimension != 1 or resolved.category is not TypeCategory.STRUCT:
                return None

            if not isinstance(raw_value, dict):
                msg = f"Expected struct overrides for {obj.reference()}.{property_name}"
                raise TypeError(msg)

            overrides = {}

            for key, item in cast("dict[object, object]", raw_value).items():
                if isinstance(key, FName):
                    name = key
                elif isinstance(key, str):
                    name = FName(key)
                else:
                    msg = f"Expected a struct field name, got {key!r}"
                    raise TypeError(msg)

                overrides[name] = item

        if variable.array_dimension == 1:
            return self._construct_instanced_value(
                obj,
                property_name,
                value,
                variable.type_ref,
                owner_class,
                variable.modifiers,
                instancing,
                overrides,
            )

        if not isinstance(value, ArrayValue):
            msg = f"Expected a fixed-array value for {obj.reference()}.{property_name}"
            raise TypeError(msg)

        elements: list[Value] = []
        changed = False

        for element in value.elements:
            replacement = self._construct_instanced_value(
                obj,
                property_name,
                element,
                variable.type_ref,
                owner_class,
                variable.modifiers,
                instancing,
            )
            if replacement is None:
                elements.append(deepcopy(element))
            else:
                elements.append(replacement)
                changed = True

        return ArrayValue(elements) if changed else None

    def _construct_instanced_value(
        self,
        obj: UObject,
        property_name: FName,
        value: Value,
        type_ref: TypeReference,
        owner_class: ReferencePath,
        modifiers: tuple[VariableModifier, ...],
        instancing: _InstancingState,
        overrides: dict[FName, object] | None = None,
    ) -> Value | None:
        """Instance object references within a scalar or dynamic array value."""
        modifiers = (*modifiers, *type_ref.modifiers)
        package_name = owner_class.get_outer().name
        config = next(config for config in self.context.packages if config.name == package_name)
        visible = collect_visible_packages(config, self.context.packages)
        resolved = self.context.references.resolve_type(
            type_ref, owner_class, visible, self.context.parents
        )

        match resolved.category:
            case TypeCategory.OBJECT:
                if isinstance(value, ObjectValue) and self.properties_are_instanced(modifiers):
                    return self._construct_instanced_reference(
                        obj, property_name, value, instancing
                    )

            case TypeCategory.ARRAY:
                if not isinstance(value, ArrayValue):
                    msg = f"Expected an array value for {obj.reference()}.{property_name}"
                    raise TypeError(msg)

                if len(type_ref.arguments) != 1:
                    msg = f"Array type requires one element type: {type_ref}"
                    raise ValueError(msg)

                elements: list[Value] = []
                changed = False

                for element in value.elements:
                    replacement = self._construct_instanced_value(
                        obj,
                        property_name,
                        element,
                        type_ref.arguments[0],
                        owner_class,
                        modifiers,
                        instancing,
                    )
                    if replacement is None:
                        elements.append(deepcopy(element))
                    else:
                        elements.append(replacement)
                        changed = True

                if changed:
                    return ArrayValue(elements)

            case TypeCategory.STRUCT:
                if not isinstance(value, StructValue):
                    msg = f"Expected a struct value for {obj.reference()}.{property_name}"
                    raise TypeError(msg)

                path = resolved.declaration_path

                if path is None:
                    msg = "Resolved struct has no declaration path"
                    raise ValueError(msg)

                result = deepcopy(value)
                changed = False

                for name, field_value in value.values.items():
                    member = self.context.references.resolve_struct_variable(
                        path, name, self.context.parents, visible
                    )
                    replacement = self._construct_instanced_field_value(
                        obj,
                        property_name,
                        field_value,
                        member.declaration,
                        member.owner_class,
                        instancing,
                        supplied=overrides is not None and name in overrides,
                        raw_value=None if overrides is None else overrides.get(name),
                    )

                    if replacement is not None:
                        result.values[name] = replacement
                        changed = True

                if changed:
                    return result

            case _:
                pass

        return None

    def construct_instanced_properties(
        self,
        obj: UObject,
        supplied_properties: dict[FName, object],
        instancing: _InstancingState | None = None,
    ) -> None:
        """Instance omitted references, including fields of partial struct overrides."""
        payload = obj.payload

        if not isinstance(payload, ObjectInstancePayload):
            msg = f"Object has no instance payload: {obj.reference()}"
            raise TypeError(msg)

        processed: set[FName] = set()

        if instancing is None:
            instancing = _InstancingState()

        instancing.owners.append(obj)
        try:
            for owner, declaration in self.context.references.iter_class_hierarchy(
                payload.class_path, self.context.parents
            ):
                for variable in declaration.variables:
                    name = variable.name

                    if name in processed:
                        continue

                    processed.add(name)

                    # Handler-written properties without raw YAML stay untouched.
                    if name in payload.properties and name not in supplied_properties:
                        continue

                    resolved = self.values.resolve_field_type(variable, owner)

                    if resolved.category not in (
                        TypeCategory.OBJECT,
                        TypeCategory.ARRAY,
                        TypeCategory.STRUCT,
                    ):
                        continue

                    if name in payload.properties:
                        value = payload.properties[name]
                    else:
                        value = self.archetype_property_value(obj, payload.class_path, name)

                    replacement = self._construct_instanced_field_value(
                        obj,
                        name,
                        value,
                        variable,
                        owner,
                        instancing,
                        supplied=name in supplied_properties,
                        raw_value=supplied_properties.get(name),
                    )

                    if replacement is not None:
                        payload.properties[name] = replacement
        finally:
            instancing.owners.pop()

    def build_reference_components(
        self, class_path: ReferencePath, templates: dict[FName, tuple[ReferencePath, ReferencePath]]
    ) -> None:
        """Export component templates inherited from the direct reference parent."""
        if not templates:
            return

        export = self.classes[class_path]
        cdo = export.default_object
        cdo_payload = cdo.payload
        class_payload = export.class_object.payload

        if not isinstance(cdo_payload, ObjectInstancePayload) or not isinstance(
            class_payload, UClassPayload
        ):
            msg = f"Class and CDO must be linked before building components: {class_path}"
            raise ValueError(msg)  # noqa: TRY004

        remap: dict[ReferencePath, ReferencePath] = {}

        for template_name, (component_class, stock_path) in templates.items():
            stock_cdo, _ = stock_path.split(require_outer=True)
            stock_package, stock_cdo_name = stock_cdo.split(require_outer=True)
            stock_class_name = FName(str(stock_cdo_name).removeprefix(DEFAULT_OBJECT_PREFIX))
            stock_class = stock_package + stock_class_name
            stock_outer = self.references.class_object_reference(stock_class, default_object=True)
            archetype = self.references.ensure_import(
                template_name, stock_outer, *component_class.full_split()
            )

            component = UObject(
                template_name,
                ObjectFlags.PUBLIC_EXPORT,
                cdo.reference(),
                self.references.class_object_reference(component_class),
                archetype=archetype,
                payload=ComponentTemplatePayload(
                    component_class, self.context, template_name=template_name
                ),
            )
            reference = self.package.add_export(component)
            class_payload.component_defaults[template_name] = reference
            remap[stock_path] = reference

        effective = self.class_default_values(class_path)
        effective.update(cdo_payload.properties)
        remapped = self._remap_default_properties(effective, remap)

        for name, value in remapped.items():
            if name in cdo_payload.properties or value != effective[name]:
                cdo_payload.properties[name] = value

        if class_payload.component_defaults:
            class_payload.class_flags |= ClassFlags.HAS_COMPONENTS

    def build_default_objects(
        self, templates_by_class: dict[ReferencePath, dict[FName, DefaultObjectTemplate]]
    ) -> None:
        """Build effective template trees in base-to-derived class order."""
        trees: dict[ReferencePath, dict[tuple[FName, ...], UObject]] = {}

        for class_path, export in self.classes.items():
            parent = self.context.parents[class_path]
            inherited = {} if parent is None else trees.get(parent, {})
            tree: dict[tuple[FName, ...], UObject] = {}
            templates = templates_by_class[class_path]
            self._reserve_default_object_tree(
                templates, export.default_object.reference(), (), inherited, tree
            )
            trees[class_path] = tree

            if not tree:
                continue

            class_payload = export.class_object.payload
            if not isinstance(class_payload, UClassPayload):
                msg = f"Class must be linked before registering components: {class_path}"
                raise TypeError(msg)

            for key, obj in tree.items():
                if len(key) != 1:
                    continue

                component_class = templates[key[0]].class_path
                if not self.context.references.is_subclass(
                    component_class, CORE_COMPONENT_PATH, self.context.parents
                ):
                    continue

                obj.payload = ComponentTemplatePayload(
                    component_class, self.context, template_name=obj.name
                )
                class_payload.component_defaults[obj.name] = obj.reference()
                class_payload.class_flags |= ClassFlags.HAS_COMPONENTS

            remap: dict[ReferencePath, ReferencePath] = {}
            ancestor = parent

            while ancestor is not None:
                for key, original in trees.get(ancestor, {}).items():
                    source_path = original.reference()
                    target_path = tree[key].reference()
                    remap[source_path] = target_path
                    remap[ReferencePath(self.package.name) + source_path] = target_path

                ancestor = self.context.parents[ancestor]

            scopes: dict[tuple[FName, ...], dict[FName, ReferencePath]] = {}

            for key, obj in tree.items():
                scopes.setdefault(key[:-1], {})[key[-1]] = obj.reference()

            self._build_default_object_tree_properties(
                class_path, templates, tree, inherited, scopes, remap
            )

            payload = export.default_object.payload
            if not isinstance(payload, ObjectInstancePayload):
                msg = f"CDO has an invalid payload: {class_path}"
                raise TypeError(msg)

            effective = self.class_default_values(class_path)
            remapped = self._remap_default_properties(effective, remap)

            for name, value in remapped.items():
                if name in payload.properties or value != effective[name]:
                    payload.properties[name] = value

    def _reserve_default_object_tree(
        self,
        templates: dict[FName, DefaultObjectTemplate],
        outer: ReferencePath,
        prefix: tuple[FName, ...],
        inherited: dict[tuple[FName, ...], UObject],
        tree: dict[tuple[FName, ...], UObject],
    ) -> None:
        """Reserve all exports before resolving references between them."""
        for name, template in templates.items():
            key = (*prefix, name)
            original = inherited.get(key)
            class_path = template.class_path
            archetype = (
                self.references.class_object_reference(class_path, default_object=True)
                if original is None
                else original.reference()
            )
            obj = self.construct_object(
                class_path,
                self.references.class_object_reference(class_path),
                name,
                outer,
                ObjectFlags.DEFAULT_EXPORT | ObjectFlags.ARCHETYPE_OBJECT,
                archetype,
            )
            tree[key] = obj
            self._reserve_default_object_tree(
                template.children, obj.reference(), key, inherited, tree
            )

    def _build_default_object_tree_properties(
        self,
        class_path: ReferencePath,
        templates: dict[FName, DefaultObjectTemplate],
        tree: dict[tuple[FName, ...], UObject],
        inherited: dict[tuple[FName, ...], UObject],
        scopes: dict[tuple[FName, ...], dict[FName, ReferencePath]],
        remap: dict[ReferencePath, ReferencePath],
    ) -> None:
        for key, obj in tree.items():
            template = templates[key[0]]
            for name in key[1:]:
                template = template.children[name]

            payload = obj.payload
            if not isinstance(payload, ObjectInstancePayload):
                msg = f"Default object has an invalid payload: {obj.reference()}"
                raise TypeError(msg)

            original = inherited.get(key)
            properties: dict[FName, Value] = {}

            if original is not None:
                original_payload = original.payload
                if not isinstance(original_payload, ObjectInstancePayload):
                    msg = f"Default object has an invalid payload: {original.reference()}"
                    raise TypeError(msg)

                properties = self._remap_default_properties(original_payload.properties, remap)

            scope: dict[FName, ReferencePath] = {}
            for depth in range(len(key) + 1):
                scope.update(scopes.get(key[:depth], {}))

            values = replace(
                self.values,
                implicit_fixed_index=True,
                reference_base=obj.reference(),
                reference_scope=scope,
            )

            for owner, declaration in template.layers:
                if owner != class_path:
                    continue

                defaults = merge_values(self.class_default_values(template.class_path), properties)
                try:
                    overrides = values.build_class_values(
                        f"Default object {obj.reference()}",
                        template.class_path,
                        declaration.properties,
                        defaults,
                    )
                except ValueBuildError as error:
                    msg = str(error)
                    raise CompilationError(msg, declaration.location) from error

                properties = merge_values(properties, overrides)

            payload.properties = properties

    def _remap_default_properties(
        self, properties: dict[FName, Value], remap: dict[ReferencePath, ReferencePath]
    ) -> dict[FName, Value]:
        """Copy inherited values and redirect references to the derived CDO tree."""

        def remap_value(value: Value) -> Value:
            match value:
                case ObjectValue():
                    path = remap.get(value.path, value.path)
                    reference = (
                        None
                        if value.reference is None
                        else remap.get(value.reference, value.reference)
                    )
                    return replace(value, path=path, reference=reference)
                case DelegateValue():
                    return replace(value, target=remap.get(value.target, value.target))
                case ArrayValue():
                    return ArrayValue([remap_value(element) for element in value.elements])
                case StructValue():
                    return replace(
                        value,
                        values={name: remap_value(item) for name, item in value.values.items()},
                    )
                case _:
                    return deepcopy(value)

        return {name: remap_value(value) for name, value in properties.items()}
