from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING

from willow_package_builder.builder.build_component import BuildComponent
from willow_package_builder.compiler.syntax.declarations import FunctionDeclaration
from willow_package_builder.compiler.syntax.keyword import ScriptKeywords
from willow_package_builder.compiler.syntax.lexer import Token, TokenCategory
from willow_package_builder.compiler.syntax.modifiers import (
    ClassModifierName,
    FunctionModifier,
    ParameterModifier,
    StateModifier,
    VariableModifier,
)
from willow_package_builder.compiler.syntax.parser.token_parser import TokenParser
from willow_package_builder.compiler.syntax.punctuation import Punctuation
from willow_package_builder.games import get_game
from willow_package_builder.logging import (
    CompilationError,
    WarningCode,
    declaration_context,
    info,
    warn,
)
from willow_package_builder.package_config import collect_visible_packages
from willow_package_builder.payloads.class_payload import (
    ClassFlags,
    StateFlags,
    UClassPayload,
    UScriptStatePayload,
)
from willow_package_builder.upackage import (
    CORE_STATE_PATH,
    NONE_NAME,
    FName,
    ObjectFlags,
    ReferencePath,
    UObject,
)

from .exports import ClassExport

if TYPE_CHECKING:
    from willow_package_builder.builder.objects.object_builder import ObjectBuilder
    from willow_package_builder.builder.references import PackageReferences
    from willow_package_builder.compiler.syntax.declarations import ClassModifier

    from .property_builder import PropertyBuilder

INHERIT_CONFIG_NAME = FName("inherit")

CLASS_EDITOR_MODIFIERS = frozenset(
    {
        ClassModifierName.CLASS_GROUP,
        ClassModifierName.HIDE_CATEGORIES,
        ClassModifierName.SHOW_CATEGORIES,
        ClassModifierName.AUTO_EXPAND_CATEGORIES,
        ClassModifierName.AUTO_COLLAPSE_CATEGORIES,
        ClassModifierName.DONT_AUTO_COLLAPSE_CATEGORIES,
        ClassModifierName.DONT_SORT_CATEGORIES,
        ClassModifierName.FORCE_SCRIPT_ORDER,
    }
)

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
    ClassModifierName.NON_TRANSIENT: ClassFlags.TRANSIENT,
    ClassModifierName.NOT_EDIT_INLINE_NEW: ClassFlags.EDIT_INLINE_NEW,
    ClassModifierName.NOT_PLACEABLE: ClassFlags.PLACEABLE,
    ClassModifierName.DONT_COLLAPSE_CATEGORIES: ClassFlags.COLLAPSE_CATEGORIES,
}

INHERITED_CLASS_MODIFIER_FLAGS = (
    ClassFlags.TRANSIENT
    | ClassFlags.EDIT_INLINE_NEW
    | ClassFlags.PLACEABLE
    | ClassFlags.COLLAPSE_CATEGORIES
)


@dataclass
class ClassBuilder(BuildComponent):
    references: PackageReferences
    properties: PropertyBuilder
    objects: ObjectBuilder

    def reserve_classes(self) -> None:
        package_name = self.config.name
        class_order = self.context.class_order

        info(f"Selecting classes for {package_name} from {len(class_order)} declarations")
        start = perf_counter()
        package_classes = [path for path in class_order if path.get_outer().name == package_name]
        info(
            f"Selected {len(package_classes)} classes for {package_name} "
            f"in {perf_counter() - start:.3f}s"
        )

        for class_path in package_classes:
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

            info(f"Reserving class exports for {class_path}")
            class_object = UObject(declaration.name, ObjectFlags.CLASS_EXPORT)
            self.package.add_export(class_object)

            default_object = self.objects.construct_cdo(class_path, class_object)

            self.classes[class_path] = ClassExport(declaration, class_object, default_object)

    def resolve_within_class(self, class_path: ReferencePath) -> ReferencePath:
        return self.context.references.resolve_within_class(
            class_path, self.context.parents, self.context.packages
        )

    @staticmethod
    def _read_modifier_names(modifier: ClassModifier, class_path: ReferencePath) -> list[FName]:
        """Read a nonempty, comma-separated list of modifier names."""
        arguments = modifier.arguments
        if not arguments or len(arguments) % 2 == 0:
            msg = f"{class_path}: {modifier.name} expects a comma-separated list of names"
            raise CompilationError(msg)

        names: list[FName] = []
        for index, token in enumerate(arguments):
            if index % 2 == 0 and token.category is TokenCategory.IDENTIFIER:
                names.append(token.fname)
            elif index % 2 == 1 and token == Punctuation.COMMA:
                continue
            else:
                msg = f"{class_path}: Unexpected token {token} in {modifier.name}"
                raise CompilationError(msg)

        return names

    def resolve_config_name(self, class_path: ReferencePath) -> FName:
        """Return the nearest explicit config name in the class hierarchy."""
        inherit_owner: ReferencePath | None = None

        for owner, declaration in self.context.references.iter_class_hierarchy(
            class_path, self.context.parents
        ):
            for modifier in declaration.modifiers:
                if modifier.name is not ClassModifierName.CONFIG:
                    continue

                arguments = modifier.arguments
                if (
                    arguments is None
                    or len(arguments) != 1
                    or arguments[0].category is not TokenCategory.IDENTIFIER
                ):
                    msg = f"Expected one config name in config(...) on {owner}"
                    raise CompilationError(msg)

                name = arguments[0].fname
                if name != INHERIT_CONFIG_NAME:
                    return name

                inherit_owner = owner
                break

        if inherit_owner is not None:
            msg = f"Class {inherit_owner} uses config(inherit) but has no inherited config name"
            raise CompilationError(msg)

        return NONE_NAME

    def resolve_inherited_modifier_flags(self, class_path: ReferencePath) -> ClassFlags:
        """Apply inherited class flags and explicit overrides in hierarchy order."""
        hierarchy = list(
            self.context.references.iter_class_hierarchy(class_path, self.context.parents)
        )
        flags = ClassFlags.NONE

        for _, declaration in reversed(hierarchy):
            for modifier in declaration.modifiers:
                set_flags = CLASS_MODIFIER_FLAGS.get(modifier.name, ClassFlags.NONE)
                clear_flags = CLASS_MODIFIER_CLEAR_FLAGS.get(modifier.name, ClassFlags.NONE)
                flags |= set_flags & INHERITED_CLASS_MODIFIER_FLAGS
                flags &= ~(clear_flags & INHERITED_CLASS_MODIFIER_FLAGS)

        return flags

    def _interface_method_signature(
        self, owner: ReferencePath, function: FunctionDeclaration
    ) -> tuple[object, ...]:
        package_name = owner.get_outer().name
        config = next(config for config in self.context.packages if config.name == package_name)
        visible = collect_visible_packages(config, self.context.packages)
        references = self.context.references
        parents = self.context.parents

        return_type = references.resolve_type(function.return_type, owner, visible, parents)
        parameters = tuple(
            (
                references.resolve_type(parameter.type_ref, owner, visible, parents),
                parameter.array_dimension,
                ParameterModifier.OUT in parameter.modifiers,
            )
            for parameter in function.parameters
        )
        return return_type, parameters

    def _validate_interface_methods(
        self, class_path: ReferencePath, interface: ReferencePath
    ) -> None:
        references = self.context.references
        parents = self.context.parents

        for owner, declaration in references.iter_class_hierarchy(interface, parents):
            if not declaration.is_interface:
                break

            for required in declaration.functions:
                try:
                    member = references.resolve_function(class_path, required.name, parents)
                except CompilationError as exc:
                    msg = f"{class_path} must implement {owner}.{required.name}"
                    raise CompilationError(msg) from exc

                actual = member.declaration
                if (
                    FunctionModifier.NATIVE in required.modifiers
                    and FunctionModifier.NATIVE not in actual.modifiers
                ):
                    msg = (
                        f"{class_path}.{actual.name} must be native"
                        f" to implement {owner}.{required.name}"
                    )
                    raise CompilationError(msg)
                if (
                    actual.func_category != required.func_category
                    or self._interface_method_signature(member.owner_class, actual)
                    != self._interface_method_signature(owner, required)
                ):
                    msg = f"{class_path}.{actual.name} must match {owner}.{required.name}"
                    raise CompilationError(msg)

    def _resolve_implemented_interfaces(
        self, class_path: ReferencePath, modifiers: tuple[ClassModifier, ...]
    ) -> list[ReferencePath]:
        """Resolve the interfaces explicitly named by a class."""
        package_name = class_path.get_outer().name
        config = next(config for config in self.context.packages if config.name == package_name)
        visible = collect_visible_packages(config, self.context.packages)

        interfaces: list[ReferencePath] = []

        for modifier in modifiers:
            if modifier.name is not ClassModifierName.IMPLEMENTS:
                continue

            arguments = modifier.arguments
            if not arguments:
                msg = f"{class_path}: implements expects at least one interface"
                raise CompilationError(msg)

            last = arguments[-1]
            eof = Token(TokenCategory.EOF, "", last.line, last.column + len(last))
            parser = TokenParser([*arguments, eof])

            while True:
                name = parser.parse_qualified_name()
                path, declaration = self.context.references.resolve_class(
                    name, package_name, visible
                )

                if not declaration.is_interface:
                    msg = f"{class_path}: {path} is not an interface"
                    raise CompilationError(msg)

                if path in interfaces:
                    msg = f"{class_path}: Interface {path} is listed more than once"
                    raise CompilationError(msg)

                interfaces.append(path)
                if not parser.match(Punctuation.COMMA):
                    break

            if parser.peek().category is not TokenCategory.EOF:
                msg = f"{class_path}: Expected a comma in implements(...)"
                raise CompilationError(msg)

        return interfaces

    def _apply_editor_modifiers(self, class_path: ReferencePath, payload: UClassPayload) -> None:
        hierarchy = list(
            self.context.references.iter_class_hierarchy(class_path, self.context.parents)
        )

        for owner, declaration in reversed(hierarchy):
            for modifier in declaration.modifiers:
                name = modifier.name
                if name not in CLASS_EDITOR_MODIFIERS:
                    continue

                if name is ClassModifierName.FORCE_SCRIPT_ORDER:
                    arguments = modifier.arguments
                    if (
                        arguments is None
                        or len(arguments) != 1
                        or arguments[0] not in (ScriptKeywords.TRUE, ScriptKeywords.FALSE)
                    ):
                        msg = f"{owner}: forcescriptorder expects true or false"
                        raise CompilationError(msg)

                    payload.force_script_order = arguments[0] == ScriptKeywords.TRUE
                    continue

                if name is ClassModifierName.CLASS_GROUP and owner != class_path:
                    continue

                for category in self._read_modifier_names(modifier, owner):
                    match name:
                        case ClassModifierName.CLASS_GROUP:
                            payload.class_groups.append(category)

                        case ClassModifierName.HIDE_CATEGORIES:
                            payload.hide_categories.append(category)

                        case ClassModifierName.SHOW_CATEGORIES:
                            payload.hide_categories[:] = [
                                item for item in payload.hide_categories if item != category
                            ]

                        case ClassModifierName.AUTO_EXPAND_CATEGORIES:
                            if category in payload.auto_collapse_categories:
                                payload.auto_collapse_categories.remove(category)
                            if category not in payload.auto_expand_categories:
                                payload.auto_expand_categories.append(category)

                        case ClassModifierName.AUTO_COLLAPSE_CATEGORIES:
                            if category in payload.auto_expand_categories:
                                payload.auto_expand_categories.remove(category)
                            if category not in payload.auto_collapse_categories:
                                payload.auto_collapse_categories.append(category)

                        case ClassModifierName.DONT_AUTO_COLLAPSE_CATEGORIES:
                            if category in payload.auto_collapse_categories:
                                payload.auto_collapse_categories.remove(category)

                        case ClassModifierName.DONT_SORT_CATEGORIES:
                            if category not in payload.dont_sort_categories:
                                payload.dont_sort_categories.append(category)

                        case _:
                            pass

    def link_classes(self) -> None:
        supported_modifiers = {
            ClassModifierName.ABSTRACT,
            ClassModifierName.EDIT_INLINE_NEW,
            ClassModifierName.PER_OBJECT_LOCALIZED,
            ClassModifierName.CONFIG,
            ClassModifierName.PER_OBJECT_CONFIG,
            ClassModifierName.TRANSIENT,
            ClassModifierName.NO_TRANSIENT,
            ClassModifierName.NON_TRANSIENT,
            ClassModifierName.NOT_EDIT_INLINE_NEW,
            ClassModifierName.PLACEABLE,
            ClassModifierName.NOT_PLACEABLE,
            ClassModifierName.COLLAPSE_CATEGORIES,
            ClassModifierName.DONT_COLLAPSE_CATEGORIES,
            ClassModifierName.NO_EXPORT,
        }

        for class_path, exports in self.classes.items():
            parent = self.context.parents[class_path]

            if parent is None:
                msg = "Building root classes is not supported yet"
                raise NotImplementedError(msg)

            flags = ClassFlags.COMPILED | ClassFlags.PARSED
            flags |= self.resolve_inherited_modifier_flags(class_path)
            config_name = self.resolve_config_name(class_path)
            if config_name == NONE_NAME and any(
                VariableModifier.CONFIG in variable.modifiers
                or VariableModifier.GLOBAL_CONFIG in variable.modifiers
                for variable in exports.declaration.variables
            ):
                msg = (
                    f"Class {class_path} needs a config name for config or globalconfig properties"
                )
                raise CompilationError(msg)
            if config_name != NONE_NAME:
                flags |= ClassFlags.CONFIG

            if any(
                VariableModifier.LOCALIZED in variable.modifiers
                for _, declaration in self.context.references.iter_class_hierarchy(
                    class_path, self.context.parents
                )
                for variable in declaration.variables
            ):
                flags |= ClassFlags.LOCALIZED

            if self.has_instanced_properties(class_path):
                flags |= ClassFlags.HAS_INSTANCED_PROPS

            for modifier in exports.declaration.modifiers:
                modifier_name = modifier.name
                if (
                    modifier_name in CLASS_EDITOR_MODIFIERS
                    or modifier_name is ClassModifierName.IMPLEMENTS
                ):
                    continue

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

            payload = UClassPayload(
                super_struct=parent_reference,
                within=self.references.class_object_reference(
                    self.resolve_within_class(class_path)
                ),
                default_object=exports.default_object.reference(),
                class_flags=flags,
                state_flags=StateFlags.AUTO,
                config_name=config_name,
                probe_mask=self._probe_mask(class_path),
            )

            interfaces = self._resolve_implemented_interfaces(
                class_path, exports.declaration.modifiers
            )
            inherited_interfaces: dict[ReferencePath, ReferencePath] = {}

            if interfaces:
                for owner, declaration in self.context.references.iter_class_hierarchy(
                    parent, self.context.parents
                ):
                    for interface in self._resolve_implemented_interfaces(
                        owner, declaration.modifiers
                    ):
                        inherited_interfaces.setdefault(interface, owner)

            for interface in interfaces:
                inherited_owner = inherited_interfaces.get(interface)
                if inherited_owner is not None:
                    msg = (
                        f"{class_path}: Interface {interface} is already "
                        f"implemented by {inherited_owner}"
                    )
                    raise CompilationError(msg)
                self._validate_interface_methods(class_path, interface)

                reference = self.references.class_object_reference(interface)
                payload.interfaces[reference] = ReferencePath()

            self._apply_editor_modifiers(class_path, payload)
            exports.class_object.payload = payload

    def _resolve_inherited_state(self, class_path: ReferencePath, name: FName) -> ReferencePath:
        parent = self.context.parents[class_path]
        if parent is None:
            return ReferencePath()

        for owner, declaration in self.context.references.iter_class_hierarchy(
            parent, self.context.parents
        ):
            for state in declaration.states:
                if state.name != name:
                    continue

                outer = self.references.class_object_reference(owner)
                if owner.get_outer().name == self.config.name:
                    return self.package.lookup_object_by_path(outer + state.name).reference()

                return self.references.ensure_import(
                    state.name, outer, *CORE_STATE_PATH.full_split()
                )

        return ReferencePath()

    def build_class_states(self) -> None:
        """Export states and link them into their owning class's fields."""
        for class_path, exports in self.classes.items():
            if not exports.declaration.states:
                continue

            class_payload = exports.class_object.payload
            if not isinstance(class_payload, UClassPayload):
                msg = f"Class must be linked before building states: {class_path}"
                raise ValueError(msg)  # noqa: TRY004

            state_class = self.references.class_object_reference(CORE_STATE_PATH)

            for state in reversed(exports.declaration.states):
                with declaration_context(class_path + state.name, state.location):
                    if (
                        state.parent is not None
                        or any(
                            modifier is not StateModifier.SIMULATED for modifier in state.modifiers
                        )
                        or state.editable
                        or state.ignores
                        or state.code_tokens
                    ):
                        msg = (
                            "State modifiers other than simulated, explicit state "
                            "inheritance, ignores, and state code are not implemented yet"
                        )
                        raise NotImplementedError(msg)

                    parent_reference = self._resolve_inherited_state(class_path, state.name)
                    obj = UObject(
                        state.name,
                        ObjectFlags.PUBLIC_EXPORT,
                        exports.class_object.reference(),
                        state_class,
                        super_object=parent_reference,
                        payload=UScriptStatePayload(
                            next_field=class_payload.children,
                            super_struct=parent_reference,
                            state_flags=(
                                StateFlags.SIMULATED
                                if StateModifier.SIMULATED in state.modifiers
                                else StateFlags.NONE
                            ),
                            probe_mask=self._probe_mask(class_path, state.name),
                        ),
                    )
                    class_payload.children = self.package.add_export(obj)

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

    def has_instanced_properties(self, class_path: ReferencePath) -> bool:
        """Check direct and inherited fields for instanced object references."""
        for owner, declaration in self.context.references.iter_class_hierarchy(
            class_path, self.context.parents
        ):
            for variable in declaration.variables:
                if self.properties.type_has_instanced_objects(
                    variable.type_ref, owner, variable.modifiers
                ):
                    return True

        return False

    def _probe_mask(self, class_path: ReferencePath, state_name: FName | None = None) -> int:
        probe_bits = get_game().PROBE_BITS
        mask = 0

        for _, declaration in self.context.references.iter_class_hierarchy(
            class_path, self.context.parents
        ):
            functions = (
                declaration.functions
                if state_name is None
                else (
                    function
                    for state in declaration.states
                    if state.name == state_name
                    for function in state.functions
                )
            )

            for function in functions:
                if function.has_body or FunctionModifier.NATIVE in function.modifiers:
                    mask |= probe_bits.get(function.name, 0)

        return mask
