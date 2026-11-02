from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from willow_package_builder.compiler.syntax.declarations import (
    StructDeclaration,
    TypeReference,
    VariableDeclaration,
)
from willow_package_builder.compiler.syntax.defaults import (
    ArrayDefaultValue,
    DefaultAssignment,
    DefaultValue,
    EmptyDefaultValue,
    IdentifierDefaultValue,
    LiteralDefaultValue,
    NameDefaultValue,
    ObjectDefaultValue,
    StructDefaultValue,
)
from willow_package_builder.compiler.syntax.parser.defaults_parser import DefaultsParser
from willow_package_builder.logging import CompilationError
from willow_package_builder.upackage import INT32_MAX, UINT8_MAX

from .types import ResolvedType, TypeCategory

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .references import ReferenceDatabase


@dataclass
class DefaultTarget:
    owner_class: str
    declaration: VariableDeclaration
    resolved_type: ResolvedType
    array_index: int | None


@dataclass
class ResolvedPropertyDefault:
    target: DefaultTarget
    value: DefaultValue


@dataclass
class ResolvedStructValue(DefaultValue):
    struct_path: str
    fields: dict[str, ResolvedPropertyDefault]


@dataclass
class ResolvedEnumValue(DefaultValue):
    enum_path: str
    member_name: str
    index: int


@dataclass
class ResolvedArrayValue(DefaultValue):
    elements: list[DefaultValue]


@dataclass
class DefaultsResolver:
    references: ReferenceDatabase
    parents: Mapping[str, str | None]
    visible_packages: set[str]

    _initializing_structs: set[str] = field(default_factory=set, init=False, repr=False)

    def resolve_variable_target(
        self, owner_class: str, variable: VariableDeclaration, assignment: DefaultAssignment
    ) -> DefaultTarget:
        resolved = self.references.resolve_type(
            variable.type_ref, owner_class, self.visible_packages, self.parents
        )

        index = assignment.array_index

        if index is not None:
            if index < 0:
                msg = f"Array index cannot be negative: {index}"
                raise CompilationError(msg, assignment.location)

            if variable.array_dimension != 1:
                if index >= variable.array_dimension:
                    msg = (
                        f"Index {index} exceeds the fixed array "
                        f"{variable.name}[{variable.array_dimension}]"
                    )
                    raise CompilationError(msg, assignment.location)

            elif resolved.category is TypeCategory.ARRAY:
                resolved = resolved.arguments[0]

            else:
                msg = f"Property {variable.name!r} is not an array"
                raise CompilationError(msg, assignment.location)

        return DefaultTarget(owner_class, variable, resolved, index)

    def resolve_target(self, class_path: str, assignment: DefaultAssignment) -> DefaultTarget:
        member = self.references.resolve_variable(class_path, assignment.name, self.parents)

        return self.resolve_variable_target(member.owner_class, member.declaration, assignment)

    def resolve_scalar_value(
        self, assignment: DefaultAssignment, resolved_type: ResolvedType
    ) -> DefaultValue:
        value = assignment.value
        category = resolved_type.category

        if category is TypeCategory.NAME:
            if isinstance(value, NameDefaultValue):
                return value

            msg = f"Property {assignment.name!r} requires a name literal"
            raise CompilationError(msg, assignment.location)

        if category in (TypeCategory.OBJECT, TypeCategory.CLASS):
            if isinstance(value, LiteralDefaultValue) and value.value is None:
                return value

            msg = f"Non-null {category.value} default references are not implemented"
            raise NotImplementedError(msg)

        supported = {
            TypeCategory.INT,
            TypeCategory.BYTE,
            TypeCategory.FLOAT,
            TypeCategory.BOOL,
            TypeCategory.STRING,
        }

        if category not in supported:
            msg = f"Default resolution for {category.value} is not implemented"
            raise NotImplementedError(msg)

        if not isinstance(value, LiteralDefaultValue):
            msg = f"Resolving {type(value).__name__} as {category.value} is not implemented"
            raise NotImplementedError(msg)

        literal = value.value

        match category:
            # type() is X is used because we want to check the exact type, not subtype,
            # as bool is a subclass of int
            case TypeCategory.INT:
                if type(literal) is int and -(INT32_MAX + 1) <= literal <= INT32_MAX:
                    return value

            case TypeCategory.BYTE:
                if type(literal) is int and 0 <= literal <= UINT8_MAX:
                    return value

            case TypeCategory.FLOAT:
                if type(literal) is int or type(literal) is float:
                    return LiteralDefaultValue(float(literal))

            case TypeCategory.BOOL:
                if type(literal) is bool:
                    return value

            case TypeCategory.STRING:
                if type(literal) is str:
                    return value

            case _:
                pass
        msg = f"Invalid {category.value} default for {assignment.name!r}: {literal!r}"
        raise CompilationError(msg, assignment.location)

    def initial_scalar_value(self, resolved_type: ResolvedType) -> DefaultValue:
        """Return a scalar property's initial value before explicit defaults."""
        match resolved_type.category:
            case TypeCategory.INT | TypeCategory.BYTE:
                return LiteralDefaultValue(0)

            case TypeCategory.FLOAT:
                return LiteralDefaultValue(0.0)

            case TypeCategory.BOOL:
                return LiteralDefaultValue(False)  # noqa: FBT003

            case TypeCategory.STRING:
                return LiteralDefaultValue("")

            case TypeCategory.NAME:
                return NameDefaultValue("None")

            case TypeCategory.OBJECT | TypeCategory.CLASS:
                return LiteralDefaultValue(None)

            case _:
                msg = (
                    "Initial default resolution for "
                    f"{resolved_type.category.value} is not implemented"
                )
                raise NotImplementedError(msg)

    def resolve_class_defaults(self, class_path: str) -> dict[str, ResolvedPropertyDefault]:
        """Resolve explicit defaults, including inherited assignments."""
        defaults: dict[str, ResolvedPropertyDefault] = {}

        hierarchy = list(self.references.iter_class_hierarchy(class_path, self.parents))

        for owner, declaration in reversed(hierarchy):
            for variable in declaration.variables:
                key = variable.name.casefold()

                if key in defaults:
                    continue

                resolved = self.references.resolve_type(
                    variable.type_ref, owner, self.visible_packages, self.parents
                )

                target = DefaultTarget(owner, variable, resolved, None)
                defaults[key] = ResolvedPropertyDefault(
                    target, self.initial_field_value(variable, resolved)
                )

            if declaration.default_tokens is None:
                continue

            assignments = DefaultsParser.from_default_tokens(
                declaration.default_tokens
            ).parse_defaults()

            for assignment in assignments:
                member = self.references.resolve_variable(owner, assignment.name, self.parents)
                key = member.declaration.name.casefold()

                defaults[key] = self.apply_field_default(assignment, defaults[key])

        return defaults

    def struct_hierarchy(self, struct_path: str) -> list[tuple[str, StructDeclaration]]:
        """Return struct declarations in parent-to-child order."""
        hierarchy: list[tuple[str, StructDeclaration]] = []
        visited: set[str] = set()
        current = struct_path

        while True:
            key = current.casefold()

            if key in visited:
                msg = f"Struct inheritance cycle at {current}"
                raise CompilationError(msg)

            visited.add(key)

            owner_class, _, struct_name = current.rpartition(".")
            member = self.references.resolve_struct(owner_class, struct_name, self.parents)
            declaration = member.declaration

            hierarchy.append((member.owner_class, declaration))

            if declaration.parent is None:
                break

            parent = self.references.resolve_type(
                TypeReference(declaration.parent),
                member.owner_class,
                self.visible_packages,
                self.parents,
            )

            if parent.category is not TypeCategory.STRUCT:
                msg = f"Struct {current} has a non-struct parent"
                raise CompilationError(msg)

            if parent.declaration_path is None:
                msg = f"Parent struct of {current} has no declaration path"
                raise ValueError(msg)

            current = parent.declaration_path

        hierarchy.reverse()
        return hierarchy

    def _inner_resolve_struct_defaults(self, struct_path: str) -> ResolvedStructValue:
        fields: dict[str, ResolvedPropertyDefault] = {}

        for owner, declaration in self.struct_hierarchy(struct_path):
            for variable in declaration.variables:
                key = variable.name.casefold()

                if key in fields:
                    continue

                resolved = self.references.resolve_type(
                    variable.type_ref, owner, self.visible_packages, self.parents
                )

                target = DefaultTarget(owner, variable, resolved, None)
                fields[key] = ResolvedPropertyDefault(
                    target, self.initial_field_value(variable, resolved)
                )

            if declaration.default_tokens is None:
                continue

            assignments = DefaultsParser.from_default_tokens(
                declaration.default_tokens
            ).parse_defaults()

            for assignment in assignments:
                key = assignment.name.casefold()
                existing = fields.get(key)

                if existing is None:
                    msg = f"Unknown field {assignment.name!r} in struct {owner}.{declaration.name}"
                    raise CompilationError(msg, assignment.location)

                fields[key] = self.apply_field_default(assignment, existing)

        return ResolvedStructValue(struct_path, fields)

    def resolve_struct_defaults(self, struct_path: str) -> ResolvedStructValue:
        key = struct_path.casefold()

        if key in self._initializing_structs:
            msg = f"Recursive struct layout while initializing defaults for {struct_path}"
            raise CompilationError(msg)

        self._initializing_structs.add(key)

        try:
            return self._inner_resolve_struct_defaults(struct_path)
        finally:
            self._initializing_structs.remove(key)

    def apply_struct_default(
        self, assignment: DefaultAssignment, existing: ResolvedStructValue
    ) -> ResolvedStructValue:
        value = assignment.value

        if isinstance(value, EmptyDefaultValue):
            return ResolvedStructValue(existing.struct_path, existing.fields.copy())

        if not isinstance(value, StructDefaultValue):
            msg = f"Property {assignment.name!r} requires a struct value"
            raise CompilationError(msg, assignment.location)

        fields = existing.fields.copy()

        for field_assignment in value.fields:
            key = field_assignment.name.casefold()
            previous = fields.get(key)

            if previous is None:
                msg = f"Unknown field {field_assignment.name!r} in struct {existing.struct_path}"
                raise CompilationError(msg, field_assignment.location)

            fields[key] = self.apply_field_default(field_assignment, previous)

        return ResolvedStructValue(existing.struct_path, fields)

    def initial_value(self, resolved_type: ResolvedType) -> DefaultValue:
        match resolved_type.category:
            case TypeCategory.ENUM:
                return self.resolve_enum_value(resolved_type)

            case TypeCategory.STRUCT:
                struct_path = resolved_type.declaration_path

                if struct_path is None:
                    msg = "Resolved struct type has no declaration path"
                    raise ValueError(msg)

                return self.resolve_struct_defaults(struct_path)

            case TypeCategory.ARRAY:
                return ResolvedArrayValue([])

            case _:
                return self.initial_scalar_value(resolved_type)

    def resolve_value(
        self,
        assignment: DefaultAssignment,
        resolved_type: ResolvedType,
        existing: DefaultValue,
        current_class: str,
    ) -> DefaultValue:
        if resolved_type.category is TypeCategory.ENUM:
            return self.resolve_enum_value(resolved_type, assignment)

        if resolved_type.category is TypeCategory.CLASS:
            return self.resolve_class_reference(assignment, resolved_type, current_class)

        if resolved_type.category is TypeCategory.STRUCT:
            if not isinstance(existing, ResolvedStructValue):
                msg = f"Struct property {assignment.name!r} has no initialized struct value"
                raise ValueError(msg)

            return self.apply_struct_default(assignment, existing)

        if resolved_type.category is TypeCategory.ARRAY:
            return self.resolve_array_value(assignment, resolved_type, current_class)

        return self.resolve_scalar_value(assignment, resolved_type)

    def resolve_class_reference(
        self, assignment: DefaultAssignment, resolved_type: ResolvedType, current_class: str
    ) -> DefaultValue:
        value = assignment.value

        if isinstance(value, LiteralDefaultValue) and value.value is None:
            return value

        if not isinstance(value, ObjectDefaultValue):
            msg = f"Property {assignment.name!r} requires a class reference"
            raise CompilationError(msg, assignment.location)

        if value.class_name.casefold() not in ("class", "core.class"):
            msg = f"Expected a Class literal, got {value.class_name!r}"
            raise CompilationError(msg, assignment.location)

        path, _ = self.references.resolve_class(
            value.path, current_class.partition(".")[0], self.visible_packages
        )

        bound = resolved_type.arguments[0].declaration_path

        if bound is None:
            msg = "Resolved class bound has no declaration path"
            raise ValueError(msg)

        hierarchy = {
            owner.casefold()
            for owner, _ in self.references.iter_class_hierarchy(path, self.parents)
        }

        if bound.casefold() not in hierarchy:
            msg = (
                f"Class {value.path!r} does not extend {bound}; "
                f"it cannot be assigned to {assignment.name!r}"
            )
            raise CompilationError(msg, assignment.location)

        return ObjectDefaultValue("Class", path)

    def resolve_enum_value(
        self, resolved_type: ResolvedType, assignment: DefaultAssignment | None = None
    ) -> ResolvedEnumValue:
        enum_path = resolved_type.declaration_path

        if enum_path is None:
            msg = "Resolved enum type has no declaration path"
            raise ValueError(msg)

        owner_class, _, enum_name = enum_path.rpartition(".")
        member = self.references.resolve_enum(owner_class, enum_name, self.parents)
        declaration = member.declaration

        if not declaration.members:
            msg = f"Enum {enum_path} has no members"
            raise CompilationError(msg)

        if assignment is None:
            return ResolvedEnumValue(enum_path, declaration.members[0], 0)

        value = assignment.value

        if not isinstance(value, IdentifierDefaultValue):
            msg = f"Property {assignment.name!r} requires an enum member"
            raise CompilationError(msg, assignment.location)

        if "." in value.name:
            msg = "Qualified enum default names are not implemented"
            raise NotImplementedError(msg)

        for index, name in enumerate(declaration.members):
            if name.casefold() == value.name.casefold():
                return ResolvedEnumValue(enum_path, name, index)

        msg = f"Unknown member {value.name!r} of enum {enum_path}"
        raise CompilationError(msg, assignment.location)

    def initial_field_value(
        self, variable: VariableDeclaration, resolved_type: ResolvedType
    ) -> DefaultValue:
        if variable.array_dimension == 1:
            return self.initial_value(resolved_type)

        return ResolvedArrayValue(
            [self.initial_value(resolved_type) for _ in range(variable.array_dimension)]
        )

    def apply_indexed_default(
        self, assignment: DefaultAssignment, target: DefaultTarget, existing: ResolvedArrayValue
    ) -> ResolvedArrayValue:
        index = target.array_index

        if index is None:
            msg = "Indexed default assignment has no array index"
            raise ValueError(msg)

        elements = existing.elements.copy()

        # Dynamic arrays grow to include the assigned element.
        # Fixed-array bounds were already checked by resolve_target().
        while len(elements) <= index:
            elements.append(self.initial_value(target.resolved_type))

        elements[index] = self.resolve_value(
            assignment, target.resolved_type, elements[index], target.owner_class
        )

        return ResolvedArrayValue(elements)

    def apply_field_default(
        self, assignment: DefaultAssignment, previous: ResolvedPropertyDefault
    ) -> ResolvedPropertyDefault:
        target = self.resolve_variable_target(
            previous.target.owner_class, previous.target.declaration, assignment
        )

        if target.array_index is not None:
            if not isinstance(previous.value, ResolvedArrayValue):
                msg = f"Array property {assignment.name!r} has no array value"
                raise ValueError(msg)

            value = self.apply_indexed_default(assignment, target, previous.value)
        else:
            if target.declaration.array_dimension != 1:
                msg = "Whole fixed-array defaults are not implemented"
                raise NotImplementedError(msg)

            value = self.resolve_value(
                assignment, target.resolved_type, previous.value, target.owner_class
            )

        return ResolvedPropertyDefault(previous.target, value)

    def resolve_array_value(
        self, assignment: DefaultAssignment, resolved_type: ResolvedType, current_class: str
    ) -> ResolvedArrayValue:
        value = assignment.value

        if isinstance(value, EmptyDefaultValue):
            return ResolvedArrayValue([])

        if not isinstance(value, ArrayDefaultValue):
            msg = f"Property {assignment.name!r} requires an array value"
            raise CompilationError(msg, assignment.location)

        element_type = resolved_type.arguments[0]
        elements: list[DefaultValue] = []

        for element in value.elements:
            element_assignment = DefaultAssignment(assignment.name, element, assignment.location)
            elements.append(
                self.resolve_value(
                    element_assignment,
                    element_type,
                    self.initial_value(element_type),
                    current_class,
                )
            )

        return ResolvedArrayValue(elements)
