from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from willow_package_builder.compiler.syntax.declarations import (
    MAX_FIXED_ARRAY_DIMENSION,
    ClassDeclaration,
    EnumDeclaration,
    FunctionCategory,
    FunctionDeclaration,
    OperatorCategory,
    OperatorDeclaration,
    StructDeclaration,
    TypeReference,
    VariableDeclaration,
)
from willow_package_builder.logging import (
    CompilationError,
    UnknownPropertyError,
    declaration_context,
)
from willow_package_builder.package_config import PackageConfig, collect_visible_packages

from .intrinsics import INTRINSICS, PROPERTY_CLASS_PATHS, IntrinsicDefinition
from .types import ResolvedType, TypeCategory

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

PRIMITIVE_TYPES = {
    t.value: ResolvedType(t)
    for t in (
        TypeCategory.BYTE,
        TypeCategory.INT,
        TypeCategory.BOOL,
        TypeCategory.FLOAT,
        TypeCategory.STRING,
        TypeCategory.NAME,
    )
}


@dataclass(frozen=True)
class ResolvedMember[T]:
    owner_class: str
    declaration: T


@dataclass
class ReferenceDatabase:
    classes: dict[str, ClassDeclaration] = field(default_factory=dict)
    operators: dict[str, list[OperatorDeclaration]] = field(default_factory=dict)
    intrinsics: dict[str, IntrinsicDefinition] = field(default_factory=lambda: dict(INTRINSICS))

    _class_paths: dict[str, str] = field(default_factory=dict, init=False, repr=False)
    _parent_cache: dict[str, str | None] | None = field(default=None, init=False, repr=False)
    _parent_cache_packages: tuple[PackageConfig, ...] | None = field(
        default=None, init=False, repr=False
    )

    def add_class(self, package_name: str, declaration: ClassDeclaration) -> None:
        path = f"{package_name}.{declaration.name}"
        key = path.casefold()

        if key in self.classes:
            msg = f"Class already registered: {path}"
            raise CompilationError(msg)

        for operator in declaration.operators:
            if operator.op_category is OperatorCategory.BINARY and operator.precedence is None:
                msg = f"Binary operator {operator.name!r} in {path} has no precedence"
                raise CompilationError(msg)

        self.classes[key] = declaration
        self._class_paths[key] = path
        self._parent_cache = None
        self._parent_cache_packages = None

        for operator in declaration.operators:
            operator_key = operator.name.casefold()
            self.operators.setdefault(operator_key, []).append(operator)

    def resolve_class_path(
        self,
        name: str,
        current_package: str,
        visible_packages: set[str],
        additional_paths: Iterable[str] = (),
        *,
        include_intrinsics: bool = False,
    ) -> str:
        """Resolve a class name to its qualified path."""
        allowed_packages = {
            current_package.casefold(),
            *(package.casefold() for package in visible_packages),
        }
        available = set(self.classes)
        available.update(path.casefold() for path in additional_paths)

        if include_intrinsics:
            available.update(self.intrinsics)

        if "." in name:
            key = name.casefold()
            package_name = key.partition(".")[0]

            if package_name not in allowed_packages:
                msg = f"Package {package_name!r} is not available to {current_package}"
                raise CompilationError(msg)

            if key not in available:
                msg = f"Unknown class: {name}"
                raise CompilationError(msg)

            return key

        local_key = f"{current_package}.{name}".casefold()

        if local_key in available:
            return local_key

        matches = [
            key
            for package_name in sorted(allowed_packages)
            if (key := f"{package_name}.{name}".casefold()) in available
        ]

        if not matches:
            msg = f"Unknown class: {name}"
            raise CompilationError(msg)

        if len(matches) > 1:
            candidates = ", ".join(matches)
            msg = f"Ambiguous class {name!r}; use a qualified name: {candidates}"
            raise CompilationError(msg)

        return matches[0]

    def parent_class_name(self, class_path: str, declaration: ClassDeclaration) -> str | None:
        """Return the explicit or implicit parent class name."""
        if declaration.parent is not None:
            return declaration.parent

        if declaration.is_interface:
            if class_path.casefold() == "core.interface":
                return "Core.Object"

            return "Core.Interface"

        return None

    def resolve_class(
        self, name: str, current_package: str, visible_packages: set[str]
    ) -> tuple[str, ClassDeclaration]:
        path = self.resolve_class_path(name, current_package, visible_packages)
        return path, self.classes[path]

    def resolve_parent_classes(self, packages: tuple[PackageConfig, ...]) -> dict[str, str | None]:
        if self._parent_cache is not None and self._parent_cache_packages == packages:
            return self._parent_cache.copy()

        configs = {config.name.casefold(): config for config in packages}
        visibility = {
            name: collect_visible_packages(config, packages) for name, config in configs.items()
        }
        parents: dict[str, str | None] = {}

        for class_path, declaration in self.classes.items():
            package_key = class_path.partition(".")[0]
            config = configs[package_key]
            parent_name = self.parent_class_name(class_path, declaration)

            if parent_name is None:
                parents[class_path] = None
                continue

            display_path = self.display_class_path(class_path)

            with declaration_context(display_path, declaration.location):
                parent_path, _ = self.resolve_class(
                    parent_name, config.name, visibility[package_key]
                )
                parents[class_path] = parent_path

        self._parent_cache = parents
        self._parent_cache_packages = packages
        return parents.copy()

    def inheritance_order(self, parents: Mapping[str, str | None]) -> tuple[str, ...]:
        ordered: list[str] = []
        completed: set[str] = set()
        active: list[str] = []
        active_set: set[str] = set()

        def visit(class_path: str) -> None:
            if class_path in completed:
                return

            if class_path in active_set:
                start = active.index(class_path)
                cycle = [*active[start:], class_path]
                description = " -> ".join(cycle)
                msg = f"Inheritance cycle: {description}"
                raise CompilationError(msg)

            if class_path not in self.classes:
                msg = f"Unknown class in inheritance graph: {class_path}"
                raise CompilationError(msg)

            if class_path not in parents:
                msg = f"Missing parent resolution for {class_path}"
                raise CompilationError(msg)

            active.append(class_path)
            active_set.add(class_path)

            try:
                parent = parents[class_path]

                if parent is not None:
                    visit(parent)
            finally:
                active.pop()
                active_set.remove(class_path)

            completed.add(class_path)
            ordered.append(class_path)

        for class_path in self.classes:
            visit(class_path)

        return tuple(ordered)

    def iter_class_hierarchy(
        self, class_path: str, parents: Mapping[str, str | None]
    ) -> Iterator[tuple[str, ClassDeclaration]]:
        current: str | None = class_path.casefold()

        while current is not None:
            declaration = self.classes.get(current)

            if declaration is None:
                msg = f"Unknown class: {current}"
                raise CompilationError(msg)

            if current not in parents:
                msg = f"Missing parent resolution for {current}"
                raise CompilationError(msg)

            yield current, declaration
            current = parents[current]

    def resolve_variable(
        self, class_path: str, name: str, parents: Mapping[str, str | None]
    ) -> ResolvedMember[VariableDeclaration]:
        key = name.casefold()

        for owner, declaration in self.iter_class_hierarchy(class_path, parents):
            for variable in declaration.variables:
                if variable.name.casefold() == key:
                    return ResolvedMember(owner, variable)

        display_path = self.display_class_path(class_path)
        msg = f"Unknown variable {name!r} on {display_path}"
        raise UnknownPropertyError(msg)

    def resolve_function(
        self, class_path: str, name: str, parents: Mapping[str, str | None]
    ) -> ResolvedMember[FunctionDeclaration]:
        key = name.casefold()

        for owner, declaration in self.iter_class_hierarchy(class_path, parents):
            for function in declaration.functions:
                if function.name.casefold() == key:
                    return ResolvedMember(owner, function)

        msg = f"Unknown function {name!r} on {class_path}"
        raise CompilationError(msg)

    def resolve_type(
        self,
        type_ref: TypeReference | None,
        current_class: str,
        visible_packages: set[str],
        parents: Mapping[str, str | None],
    ) -> ResolvedType:
        current_package = current_class.partition(".")[0]

        if type_ref is None:
            return ResolvedType(TypeCategory.VOID)

        name = type_ref.name.casefold()

        if name == "delegate":
            if len(type_ref.arguments) != 1:
                msg = "delegate requires exactly one signature"
                raise CompilationError(msg)

            signature = type_ref.arguments[0]

            if signature.arguments or signature.modifiers:
                msg = "Delegate signature must be a function name"
                raise CompilationError(msg)

            owner_name, separator, function_name = signature.name.rpartition(".")

            if separator:
                owner_path, _ = self.resolve_class(owner_name, current_package, visible_packages)
            else:
                owner_path = current_class
                function_name = signature.name

            member = self.resolve_function(owner_path, function_name, parents)

            if member.declaration.func_category is not FunctionCategory.DELEGATE:
                owner = self.display_class_path(member.owner_class)
                msg = f"{owner}.{member.declaration.name} is not a delegate declaration"
                raise CompilationError(msg)

            path = f"{member.owner_class}.{member.declaration.name}".casefold()
            return ResolvedType(TypeCategory.DELEGATE, path)

        if name == "map":
            msg = "Native map type resolution is not implemented"
            raise NotImplementedError(msg)

        if name == "array":
            if len(type_ref.arguments) != 1:
                msg = "array requires exactly one type argument"
                raise CompilationError(msg)

            element_type = self.resolve_type(
                type_ref.arguments[0], current_class, visible_packages, parents
            )

            return ResolvedType(TypeCategory.ARRAY, arguments=(element_type,))

        if name == "class":
            if len(type_ref.arguments) > 1:
                msg = "class accepts at most one type argument"
                raise CompilationError(msg)

            bound_ref = (
                type_ref.arguments[0] if type_ref.arguments else TypeReference("Core.Object")
            )

            bound = self.resolve_type(bound_ref, current_class, visible_packages, parents)

            if bound.category is not TypeCategory.OBJECT:
                msg = "class requires an object class as its bound"
                raise CompilationError(msg)

            return ResolvedType(TypeCategory.CLASS, arguments=(bound,))

        if type_ref.arguments:
            msg = f"Type {type_ref.name!r} does not accept type arguments"
            raise CompilationError(msg)

        primitive = PRIMITIVE_TYPES.get(name)
        if primitive is not None:
            return primitive

        if "." not in name:
            member_type = self.find_member_type(current_class, type_ref.name, parents)

            if member_type is not None:
                return member_type

            member_type = self.find_visible_member_type(
                type_ref.name, current_package, visible_packages
            )

            if member_type is not None:
                return member_type

        elif name not in self.classes and name not in self.intrinsics:
            # Examples: Object.Vector or Core.Object.Vector.
            owner_name, _, member_name = type_ref.name.rpartition(".")

            owner_path, _ = self.resolve_class(owner_name, current_package, visible_packages)

            member_type = self.find_member_type(owner_path, member_name, parents)

            if member_type is None:
                msg = f"Unknown struct or enum {member_name!r} on {owner_path}"
                raise CompilationError(msg)

            return member_type

        class_path = self.resolve_class_path(
            type_ref.name, current_package, visible_packages, include_intrinsics=True
        )

        return ResolvedType(TypeCategory.OBJECT, class_path)

    def resolve_struct(
        self, class_path: str, name: str, parents: Mapping[str, str | None]
    ) -> ResolvedMember[StructDeclaration]:
        key = name.casefold()

        for owner, declaration in self.iter_class_hierarchy(class_path, parents):
            for struct in declaration.structs:
                if struct.name.casefold() == key:
                    return ResolvedMember(owner, struct)

        msg = f"Unknown struct {name!r} on {class_path}"
        raise CompilationError(msg)

    def resolve_enum(
        self, class_path: str, name: str, parents: Mapping[str, str | None]
    ) -> ResolvedMember[EnumDeclaration]:
        key = name.casefold()

        for owner, declaration in self.iter_class_hierarchy(class_path, parents):
            for enum in declaration.enums:
                if enum.name.casefold() == key:
                    return ResolvedMember(owner, enum)

        msg = f"Unknown enum {name!r} on {class_path}"
        raise CompilationError(msg)

    def find_member_type(
        self, class_path: str, name: str, parents: Mapping[str, str | None]
    ) -> ResolvedType | None:
        key = name.casefold()

        for owner, declaration in self.iter_class_hierarchy(class_path, parents):
            for struct in declaration.structs:
                if struct.name.casefold() == key:
                    return ResolvedType(TypeCategory.STRUCT, f"{owner}.{struct.name}".casefold())

            for enum in declaration.enums:
                if enum.name.casefold() == key:
                    return ResolvedType(TypeCategory.ENUM, f"{owner}.{enum.name}".casefold())

        return None

    def resolve_binary_operator(
        self,
        name: str,
        left: ResolvedType,
        right: ResolvedType,
        current_class: str,
        visible_packages: set[str],
        parents: Mapping[str, str | None],
    ) -> ResolvedMember[OperatorDeclaration]:
        key = name.casefold()

        for owner, declaration in self.iter_class_hierarchy(current_class, parents):
            matches: list[OperatorDeclaration] = []

            for operator in declaration.operators:
                if (
                    operator.op_category is not OperatorCategory.BINARY
                    or operator.name.casefold() != key
                ):
                    continue

                left_type = self.resolve_type(
                    operator.parameters[0].type_ref, owner, visible_packages, parents
                )

                if left_type != left:
                    continue

                right_type = self.resolve_type(
                    operator.parameters[1].type_ref, owner, visible_packages, parents
                )

                if right_type == right:
                    matches.append(operator)

            if len(matches) > 1:
                msg = f"Multiple exact overloads of {name!r} on {owner} for {left!r} and {right!r}"
                raise CompilationError(msg)

            if matches:
                return ResolvedMember(owner, matches[0])

        msg = f"No exact overload of {name!r} for {left!r} and {right!r}"
        raise CompilationError(msg)

    def lookup_class(self, path: str) -> ClassDeclaration | IntrinsicDefinition:
        key = path.casefold()

        intrinsic = self.intrinsics.get(key)
        if intrinsic is not None:
            return intrinsic

        declaration = self.classes.get(key)
        if declaration is not None:
            return declaration

        msg = f"Unknown class: {path}"
        raise CompilationError(msg)

    def property_class(self, resolved: ResolvedType) -> IntrinsicDefinition:
        path = PROPERTY_CLASS_PATHS.get(resolved.category)

        if path is None:
            msg = f"Type {resolved} cannot be represented as a property"
            raise CompilationError(msg)

        return self.intrinsics[path.casefold()]

    def resolve_unary_operator(
        self,
        name: str,
        category: Literal[OperatorCategory.PREFIX, OperatorCategory.POSTFIX],
        operand: ResolvedType,
        current_class: str,
        visible_packages: set[str],
        parents: Mapping[str, str | None],
    ) -> ResolvedMember[OperatorDeclaration]:

        key = name.casefold()

        for owner, declaration in self.iter_class_hierarchy(current_class, parents):
            matches: list[OperatorDeclaration] = []

            for operator in declaration.operators:
                if operator.op_category is not category or operator.name.casefold() != key:
                    continue

                parameter_type = self.resolve_type(
                    operator.parameters[0].type_ref, owner, visible_packages, parents
                )

                if parameter_type == operand:
                    matches.append(operator)

            if len(matches) > 1:
                msg = (
                    f"Multiple exact {category.value} overloads "
                    f"of {name!r} on {owner} for {operand!r}"
                )
                raise CompilationError(msg)

            if matches:
                return ResolvedMember(owner, matches[0])

        msg = f"No exact {category.value} overload of {name!r} for {operand!r}"
        raise CompilationError(msg)

    def resolve_struct_variable(
        self,
        struct_path: str,
        name: str,
        parents: Mapping[str, str | None],
        visible_packages: set[str],
    ) -> ResolvedMember[VariableDeclaration]:
        current = struct_path.casefold()
        key = name.casefold()
        visited: set[str] = set()

        while True:
            if current in visited:
                msg = f"Struct inheritance cycle while resolving {struct_path}.{name}"
                raise CompilationError(msg)

            visited.add(current)
            owner_class, _, struct_name = current.rpartition(".")
            member = self.resolve_struct(owner_class, struct_name, parents)
            declaration = member.declaration

            for variable in declaration.variables:
                if variable.name.casefold() == key:
                    return ResolvedMember(member.owner_class, variable)

            if declaration.parent is None:
                break

            parent = self.resolve_type(
                TypeReference(declaration.parent), member.owner_class, visible_packages, parents
            )

            if parent.category is not TypeCategory.STRUCT:
                msg = f"Struct {current} has a non-struct parent"
                raise CompilationError(msg)

            if parent.declaration_path is None:
                msg = f"Parent struct of {current} has no declaration path"
                raise ValueError(msg)

            current = parent.declaration_path.casefold()

        display_path = self.display_type_path(struct_path, parents)
        msg = f"Unknown field {name!r} on struct {display_path}"
        raise UnknownPropertyError(msg)

    def struct_hierarchy(
        self,
        struct_path: str,
        parents: Mapping[str, str | None],
        packages: tuple[PackageConfig, ...],
    ) -> list[tuple[str, StructDeclaration]]:
        """Return parent-to-child declarations and their owning classes."""
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
            member = self.resolve_struct(owner_class, struct_name, parents)
            declaration = member.declaration
            hierarchy.append((member.owner_class, declaration))

            if declaration.parent is None:
                break

            package_name = member.owner_class.partition(".")[0]
            config = next(
                config for config in packages if config.name.casefold() == package_name.casefold()
            )
            visible = collect_visible_packages(config, packages)

            parent = self.resolve_type(
                TypeReference(declaration.parent), member.owner_class, visible, parents
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

    def is_subclass(
        self, class_path: str, base_path: str, parents: Mapping[str, str | None]
    ) -> bool:
        """Check whether a class is the given base class or extends it."""
        base = base_path.casefold()
        self.lookup_class(base)

        current: str | None = class_path.casefold()
        visited: set[str] = set()

        while current is not None:
            key = current.casefold()

            if key in visited:
                msg = f"Inheritance cycle while checking {class_path}: {current}"
                raise CompilationError(msg)

            visited.add(key)
            definition = self.lookup_class(key)

            if key == base:
                return True

            if isinstance(definition, IntrinsicDefinition):
                current = definition.parent
            else:
                current = parents[key]

        return False

    def resolve_within_class(
        self, class_path: str, parents: Mapping[str, str | None], packages: Iterable[PackageConfig]
    ) -> str:
        configs = {config.name.casefold(): config for config in packages}
        package_list = tuple(configs.values())

        for owner, declaration in self.iter_class_hierarchy(class_path, parents):
            if declaration.within is None:
                continue

            config = configs[owner.partition(".")[0].casefold()]
            visible = collect_visible_packages(config, package_list)

            return self.resolve_class_path(
                declaration.within, config.name, visible, include_intrinsics=True
            )

        return "core.object"

    def find_visible_member_type(
        self, name: str, current_package: str, visible_packages: set[str]
    ) -> ResolvedType | None:
        key = name.casefold()
        package_key = current_package.casefold()
        allowed = {package_key, *(p.casefold() for p in visible_packages)}
        candidates: list[ResolvedType] = []

        for owner, declaration in self.classes.items():
            if owner.partition(".")[0].casefold() not in allowed:
                continue

            candidates.extend(
                [
                    ResolvedType(TypeCategory.STRUCT, f"{owner}.{struct.name}".casefold())
                    for struct in declaration.structs
                    if struct.name.casefold() == key
                ]
            )

            candidates.extend(
                [
                    ResolvedType(TypeCategory.ENUM, f"{owner}.{enum.name}".casefold())
                    for enum in declaration.enums
                    if enum.name.casefold() == key
                ]
            )

        local = [
            candidate
            for candidate in candidates
            if candidate.declaration_path is not None
            and candidate.declaration_path.partition(".")[0] == package_key
        ]
        candidates = local or candidates

        if len(candidates) > 1:
            paths = ", ".join(str(candidate.declaration_path) for candidate in candidates)
            msg = f"Ambiguous struct or enum {name!r}: {paths}"
            raise CompilationError(msg)

        return candidates[0] if candidates else None

    def display_class_path(self, class_path: str) -> str:
        key = class_path.casefold()

        if key in self._class_paths:
            return self._class_paths[key]

        intrinsic = self.intrinsics.get(key)

        if intrinsic is not None:
            return intrinsic.path

        return class_path

    def display_type_path(self, path: str, parents: Mapping[str, str | None]) -> str:
        """Format a class, struct, or enum path using declaration spelling."""
        key = path.casefold()

        if key in self.classes or key in self.intrinsics:
            return self.display_class_path(path)

        owner, separator, member_name = path.rpartition(".")

        if not separator:
            return path

        current: str | None = owner.casefold()
        visited: set[str] = set()

        while current is not None and current not in visited:
            visited.add(current)
            declaration = self.classes.get(current)

            if declaration is None:
                break

            for member in (*declaration.structs, *declaration.enums):
                if member.name.casefold() == member_name.casefold():
                    return f"{self.display_class_path(current)}.{member.name}"

            current = parents.get(current)

            if current is not None:
                current = current.casefold()

        return f"{self.display_class_path(owner)}.{member_name}"

    def display_type(self, resolved: ResolvedType, parents: Mapping[str, str | None]) -> str:
        """Format a resolved type for diagnostics."""
        if resolved.declaration_path is not None:
            name = self.display_type_path(resolved.declaration_path, parents)
        else:
            name = resolved.category.value

        if resolved.arguments:
            arguments = ", ".join(
                self.display_type(argument, parents) for argument in resolved.arguments
            )
            return f"{name}<{arguments}>"

        return name

    def resolve_array_dimension(
        self,
        name: str,
        current_class: str,
        visible_packages: set[str],
        parents: Mapping[str, str | None],
    ) -> int:
        resolved = self.resolve_type(TypeReference(name), current_class, visible_packages, parents)

        if resolved.category is not TypeCategory.ENUM:
            msg = f"Resolving non-enum array dimension {name!r} is not implemented"
            raise NotImplementedError(msg)

        if resolved.declaration_path is None:
            msg = "Resolved array dimension enum has no declaration path"
            raise ValueError(msg)

        owner, _, enum_name = resolved.declaration_path.rpartition(".")
        member = self.resolve_enum(owner, enum_name, parents)
        dimension = len(member.declaration.members)

        if not 1 < dimension <= MAX_FIXED_ARRAY_DIMENSION:
            msg = (
                f"Array dimension {name!r} resolves to {dimension}; "
                f"expected 2 through {MAX_FIXED_ARRAY_DIMENSION}"
            )
            raise CompilationError(msg)

        return dimension
