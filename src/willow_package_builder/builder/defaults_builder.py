from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, cast

from willow_package_builder.builder.build_component import BuildComponent
from willow_package_builder.builder.classes.default_objects import DefaultObjectTemplate
from willow_package_builder.compiler.semantics.types import ResolvedType, TypeCategory
from willow_package_builder.compiler.syntax.declarations import DefaultObjectDeclaration
from willow_package_builder.compiler.syntax.modifiers import VariableModifier
from willow_package_builder.compiler.syntax.parser.defaults_parser import ArrayDefaults
from willow_package_builder.logging import (
    CompilationError,
    UnknownPropertyError,
    ValueBuildError,
    WarningCode,
    warn,
)
from willow_package_builder.package_config import collect_visible_packages
from willow_package_builder.properties.merge import merge_values
from willow_package_builder.properties.values import Value
from willow_package_builder.upackage import (
    CORE_COMPONENT_PATH,
    DEFAULT_OBJECT_PREFIX,
    FName,
    ReferencePath,
)

if TYPE_CHECKING:
    from willow_package_builder.builder.classes.struct_builder import StructBuilder
    from willow_package_builder.builder.objects.object_builder import ObjectBuilder
    from willow_package_builder.builder.value_builder import ValueBuilder
    from willow_package_builder.compiler.syntax.declarations import VariableDeclaration


@dataclass
class DefaultsBuilder(BuildComponent):
    values: ValueBuilder
    struct: StructBuilder
    objects: ObjectBuilder

    _completed: set[ReferencePath] = field(default_factory=set, init=False, repr=False)
    _active: list[ReferencePath] = field(default_factory=list, init=False, repr=False)

    def _begin(self, path: ReferencePath) -> None:
        if path in self._active:
            cycle = " -> ".join(str(c) for c in (*self._active, path))
            msg = f"Cyclic default dependencies are not implemented: {cycle}"
            raise NotImplementedError(msg)
        self._active.append(path)

    def reference_component_templates(
        self, class_path: ReferencePath
    ) -> dict[FName, tuple[ReferencePath, ReferencePath]]:
        """Map each template name to its class and stock object path."""
        references = self.context.references
        parents = self.context.parents
        hierarchy = list(references.iter_class_hierarchy(class_path, parents))
        templates: dict[FName, tuple[ReferencePath, ReferencePath]] = {}

        for owner, declaration in reversed(hierarchy):
            if not declaration.reference_default_objects:
                continue

            package = owner.get_outer()
            config = next(config for config in self.context.packages if config.name == package.name)
            visible = collect_visible_packages(config, self.context.packages)
            cdo_path = package + FName(f"{DEFAULT_OBJECT_PREFIX}{declaration.name}")

            for template in declaration.reference_default_objects:
                if template.class_name is None:
                    inherited = templates.get(template.name)
                    if inherited is not None:
                        component_class, _ = inherited
                        templates[template.name] = (component_class, cdo_path + template.name)
                    continue

                component_class = references.resolve_class_path(
                    template.class_name, package.name, visible
                )
                if references.is_subclass(component_class, CORE_COMPONENT_PATH, parents):
                    templates[template.name] = (component_class, cdo_path + template.name)
                else:
                    templates.pop(template.name, None)

        return templates

    def _default_object_scope(self, class_path: ReferencePath) -> dict[FName, ReferencePath]:
        """Resolve root template names beneath the current class's CDO."""
        declaration = self.context.references.classes[class_path]
        cdo_path = ReferencePath(
            FName(f"{DEFAULT_OBJECT_PREFIX}{declaration.name}"), class_path.get_outer()
        )
        scope = {
            name: path for name, (_, path) in self.reference_component_templates(class_path).items()
        }

        for _, ancestor in self.context.references.iter_class_hierarchy(
            class_path, self.context.parents
        ):
            for child in ancestor.default_objects:
                scope[child.name] = cdo_path + child.name

        return scope

    def _values_for(self, owner_class: ReferencePath) -> ValueBuilder:
        """Resolve defaults in the declaring package's scope."""
        if owner_class.outer is None:
            msg = f"Expected a qualified class, got {owner_class}"
            raise ValueError(msg)

        package_name = owner_class.outer.name
        config = next(config for config in self.context.packages if config.name == package_name)
        state = replace(self.state, config=config)
        declaration = self.context.references.classes[owner_class]
        cdo_path = ReferencePath(
            FName(f"{DEFAULT_OBJECT_PREFIX}{declaration.name}"), owner_class.get_outer()
        )

        return replace(
            self.values,
            state=state,
            implicit_fixed_index=True,
            allow_dump_fixups=config.directory not in self.context.build_packages,
            reference_base=cdo_path,
            reference_scope=self._default_object_scope(owner_class),
        )

    def _prepare_type(self, resolved: ResolvedType, data: object = None) -> None:
        match resolved.category:
            case TypeCategory.STRUCT:
                path = resolved.declaration_path
                if path is None:
                    msg = "Resolved struct has no declaration path"
                    raise ValueError(msg)

                self.build_struct_defaults(path)

                # Overrides can supply arrays of structs absent from declaration defaults.
                if isinstance(data, dict):
                    owner = path.outer
                    if owner is None:
                        msg = f"Expected qualified struct, got {path}"
                        raise ValueError(msg)
                    values = self._values_for(owner)
                    visible = collect_visible_packages(values.config, self.context.packages)

                    data = cast("dict[object, object]", data)
                    fields: dict[FName, object] = {}

                    for raw_name, raw_value in data.items():
                        if isinstance(raw_name, FName):
                            name = raw_name
                        elif isinstance(raw_name, str):
                            name = FName(raw_name)
                        else:
                            msg = "Struct field names must be names or strings"
                            raise ValueBuildError(msg)

                        if name in fields:
                            msg = f"Duplicate struct field {name}"
                            raise ValueBuildError(msg)

                        fields[name] = raw_value

                    for name, value in fields.items():
                        member = self.context.references.resolve_struct_variable(
                            path, name, self.context.parents, visible
                        )
                        field_type = values.resolve_field_type(
                            member.declaration, member.owner_class
                        )
                        self._prepare_field_type(member.declaration, field_type, value)

            case TypeCategory.ARRAY:
                # An empty dynamic array does not instantiate its element type.
                if isinstance(data, list):
                    for element in cast("list[object]", data):
                        inner_type, *_ = resolved.arguments
                        self._prepare_type(inner_type, element)

            case _:
                pass

    def build_struct_defaults(self, struct_path: ReferencePath) -> None:
        owner, name = struct_path.split()
        if owner is None:
            msg = f"Expected a qualified struct, gort {struct_path}"
            raise ValueError(msg)
        member = self.context.references.resolve_struct(owner, name, self.context.parents)
        declaration = member.declaration
        path = member.owner_class + declaration.name

        if path in self._completed:
            return

        self._begin(path)
        try:
            values = self._values_for(member.owner_class)

            for parent_owner, parent in self.struct.struct_hierarchy(path)[:-1]:
                self.build_struct_defaults(parent_owner + parent.name)

            # Inline fields need their type defaults even when not explicitly assigned.
            for variable in declaration.variables:
                resolved = values.resolve_field_type(variable, member.owner_class)
                self._prepare_type(resolved)

            declaration.defaults = {}

            if declaration.parsed_defaults:
                existing = self.struct.make_struct(path)
                declaration.defaults = self._build_default_assignments(
                    path, declaration.parsed_defaults, values, existing.values, is_struct=True
                )

            self._completed.add(path)
        except ValueBuildError as error:
            msg = str(error)
            raise CompilationError(msg) from error
        finally:
            self._active.pop()

    def build_class_defaults(self, class_path: ReferencePath) -> None:
        path = class_path
        if path in self._completed:
            return

        declaration = self.context.references.classes[path]
        self._begin(path)
        try:
            parent = self.context.parents[path]
            if parent is not None:
                self.build_class_defaults(parent)

            values = self._values_for(path)

            # Exported struct definitions need their records even if unused by fields.
            for struct in declaration.structs:
                self.build_struct_defaults(path + struct.name)

            for variable in declaration.variables:
                if VariableModifier.NATIVE in variable.modifiers:
                    continue
                resolved = values.resolve_field_type(variable, path)
                self._prepare_type(resolved)

            declaration.defaults = {}

            if declaration.parsed_defaults:
                existing = self.objects.class_default_values(path)
                declaration.defaults = self._build_default_assignments(
                    path, declaration.parsed_defaults, values, existing, is_struct=False
                )

            self._completed.add(path)
        except ValueBuildError as error:
            msg = str(error)
            raise CompilationError(msg) from error
        finally:
            self._active.pop()

    def _prepare_field_type(
        self, definition: VariableDeclaration, resolved: ResolvedType, raw_value: object
    ) -> None:
        if isinstance(raw_value, ArrayDefaults):
            if raw_value.has_initial:
                self._prepare_field_type(definition, resolved, raw_value.initial)

            if definition.array_dimension == 1:
                if resolved.category is not TypeCategory.ARRAY:
                    return
                element_type = resolved.arguments[0]
            else:
                element_type = resolved

            for update in raw_value.updates:
                for element in update.values:
                    self._prepare_type(element_type, element)
            return

        if definition.array_dimension == 1:
            self._prepare_type(resolved, raw_value)
        elif isinstance(raw_value, list):
            for element in cast("list[object]", raw_value):
                self._prepare_type(resolved, element)
        else:
            self._prepare_type(resolved, raw_value)

    def _build_default_assignments(
        self,
        path: ReferencePath,
        properties: dict[FName, object],
        values: ValueBuilder,
        existing: dict[FName, Value],
        *,
        is_struct: bool,
    ) -> dict[FName, Value]:
        result: dict[FName, Value] = {}
        visible = collect_visible_packages(values.config, self.context.packages)
        reference_only = values.config.directory not in self.context.build_packages

        for supplied_name, raw_value in properties.items():
            try:
                if is_struct:
                    member = self.context.references.resolve_struct_variable(
                        path, supplied_name, self.context.parents, visible
                    )
                else:
                    member = self.context.references.resolve_variable(
                        path, supplied_name, self.context.parents
                    )

                resolved = values.resolve_field_type(member.declaration, member.owner_class)
                self._prepare_field_type(member.declaration, resolved, raw_value)

                supplied = {supplied_name: raw_value}

                if is_struct:
                    built = values.build_struct_values(
                        f"Struct defaults {path}", path, supplied, existing
                    )
                else:
                    built = values.build_class_values(
                        f"Class defaults {path}", path, supplied, existing
                    )

            except (ValueBuildError, UnknownPropertyError) as error:
                if not reference_only:
                    raise

                msg = f"{path}: Skipped default for {supplied_name!r}: {error}"
                warn(WarningCode.INVALID_REFERENCE_DEFAULT, msg)
                continue

            result.update(built)
            existing = merge_values(existing, built)

        return result

    def prepare_default_objects(
        self, class_path: ReferencePath
    ) -> dict[FName, DefaultObjectTemplate]:
        """Prepare the types used by an effective default object tree."""
        templates = self.collect_default_object_templates(class_path)
        pending = list(templates.values())

        while pending:
            template = pending.pop()
            self.build_class_defaults(template.class_path)
            values = self._values_for(template.class_path)

            for owner, declaration in template.layers:
                if owner.get_outer() != class_path.get_outer():
                    msg = (
                        f"Inherited default objects from another package are not supported: {owner}"
                    )
                    raise NotImplementedError(msg)

                for name, raw_value in declaration.properties.items():
                    member = self.context.references.resolve_variable(
                        template.class_path, name, self.context.parents
                    )
                    resolved = values.resolve_field_type(member.declaration, member.owner_class)
                    self._prepare_field_type(member.declaration, resolved, raw_value)

            pending.extend(template.children.values())

        return templates

    def find_reference_component_fields(
        self, class_path: ReferencePath
    ) -> dict[FName, tuple[FName, ReferencePath]]:
        """Find CDO fields that reference component templates declared by this class."""
        references = self.context.references
        parents = self.context.parents
        declaration = references.classes[class_path]

        package_name = class_path.get_outer().name
        config = next(config for config in self.context.packages if config.name == package_name)
        visible = collect_visible_packages(config, self.context.packages)

        components: dict[FName, ReferencePath] = {}

        for template in declaration.reference_default_objects:
            if template.class_name is None:
                continue

            component_class = references.resolve_class_path(
                template.class_name, package_name, visible
            )
            if references.is_subclass(component_class, CORE_COMPONENT_PATH, parents):
                components[template.name] = component_class

        fields: dict[FName, tuple[FName, ReferencePath]] = {}

        for field_name, raw_value in declaration.parsed_defaults.items():
            if not isinstance(raw_value, str) or any(char in raw_value for char in ".:'"):
                continue

            template_name = FName(raw_value)
            component_class = components.get(template_name)
            if component_class is not None:
                fields[field_name] = (template_name, component_class)

        return fields

    def collect_default_object_templates(
        self, class_path: ReferencePath
    ) -> dict[FName, DefaultObjectTemplate]:
        """Collect inherited templates without modifying parsed declarations."""
        result: dict[FName, DefaultObjectTemplate] = {}
        hierarchy = list(
            self.context.references.iter_class_hierarchy(class_path, self.context.parents)
        )

        for owner, declaration in reversed(hierarchy):
            self._apply_default_object_declarations(owner, declaration.default_objects, result)

        return result

    def _apply_default_object_declarations(
        self,
        owner_class: ReferencePath,
        declarations: list[DefaultObjectDeclaration],
        templates: dict[FName, DefaultObjectTemplate],
    ) -> None:
        """Apply one declaration layer to its enclosing template collection."""
        package_name = owner_class.get_outer().name
        config = next(config for config in self.context.packages if config.name == package_name)
        visible = collect_visible_packages(config, self.context.packages)
        seen: set[FName] = set()

        for declaration in declarations:
            name = declaration.name

            if name in seen:
                msg = f"Duplicate default object {name} on {owner_class}"
                raise CompilationError(msg, declaration.location)

            seen.add(name)
            template = templates.get(name)

            if declaration.class_name is None:
                if template is None:
                    msg = (
                        f"Default object {name} on {owner_class} has no Class "
                        "and does not override an inherited template"
                    )
                    raise CompilationError(msg, declaration.location)
            else:
                class_path, class_declaration = self.context.references.resolve_class(
                    declaration.class_name, config.name, visible
                )

                if class_declaration.is_abstract:
                    msg = f"Default object {name} cannot construct abstract class {class_path}"
                    raise CompilationError(msg, declaration.location)

                if template is None:
                    template = DefaultObjectTemplate(class_path)
                    templates[name] = template
                elif class_path != template.class_path:
                    msg = (
                        f"Changing the class of inherited default object {name} "
                        f"from {template.class_path} to {class_path} is not implemented yet"
                    )
                    raise NotImplementedError(msg)

            template.layers.append((owner_class, declaration))
            self._apply_default_object_declarations(
                owner_class, declaration.children, template.children
            )
