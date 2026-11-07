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
from willow_package_builder.compiler.syntax.keyword import Keyword
from willow_package_builder.compiler.syntax.punctuation import Operator
from willow_package_builder.logging import (
    CompilationError,
    UnknownPropertyError,
    declaration_context,
)
from willow_package_builder.package_config import PackageConfig, collect_visible_packages
from willow_package_builder.upackage import (
    CORE_INTERFACE_PATH,
    CORE_OBJECT_PATH,
    FName,
    ReferencePath,
)

from .intrinsics import INTRINSICS, PROPERTY_CLASS_PATHS, IntrinsicDefinition
from .types import ResolvedType, TypeCategory

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

DELEGATE_TYPE = ReferencePath("delegate")
MAP_TYPE = ReferencePath("map")
ARRAY_TYPE = ReferencePath("array")
CLASS_TYPE = ReferencePath("class")

PRIMITIVE_TYPES = {
    ReferencePath(category.value): ResolvedType(category)
    for category in (
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
    owner_class: ReferencePath
    declaration: T


@dataclass
class ReferenceDatabase:
    classes: dict[ReferencePath, ClassDeclaration] = field(default_factory=dict)
    operators: dict[Operator | Keyword, list[OperatorDeclaration]] = field(default_factory=dict)
    intrinsics: dict[ReferencePath, IntrinsicDefinition] = field(
        default_factory=lambda: dict(INTRINSICS)
    )

    _parent_cache: dict[ReferencePath, ReferencePath | None] | None = field(
        default=None, init=False, repr=False
    )
    _parent_cache_packages: tuple[PackageConfig, ...] | None = field(
        default=None, init=False, repr=False
    )

    def add_class(self, package_name: FName, declaration: ClassDeclaration) -> None:
        path = ReferencePath(declaration.name, ReferencePath(package_name))

        if path in self.classes:
            msg = f"Class already registered: {path}"
            raise CompilationError(msg)

        for operator in declaration.operators:
            if operator.op_category is OperatorCategory.BINARY and operator.precedence is None:
                msg = f"Binary operator {operator.name!r} in {path} has no precedence"
                raise CompilationError(msg)

        self.classes[path] = declaration
        self._parent_cache = None
        self._parent_cache_packages = None

        for operator in declaration.operators:
            operator_key = operator.name
            self.operators.setdefault(operator_key, []).append(operator)

    def resolve_class_path(
        self,
        name: ReferencePath,
        current_package: FName,
        visible_packages: set[FName],
        additional_paths: Iterable[ReferencePath] = (),
        *,
        include_intrinsics: bool = False,
    ) -> ReferencePath:
        """Resolve a class name to its qualified path."""
        allowed_packages = {current_package, *(package for package in visible_packages)}
        available = set(self.classes)
        available.update(path for path in additional_paths)

        if include_intrinsics:
            available.update(self.intrinsics)

        if (package_path := name.outer) is not None:
            package_name = package_path.name
            if package_name not in allowed_packages:
                msg = f"Package {package_name!r} is not available to {current_package}"
                raise CompilationError(msg)

            if name not in available:
                msg = f"Unknown class: {name}"
                raise CompilationError(msg)

            return name

        local_key = ReferencePath(name.name, ReferencePath(current_package))

        if local_key in available:
            return local_key

        matches = [
            key
            for package_name in sorted(allowed_packages)
            if (key := ReferencePath(name.name, ReferencePath(package_name))) in available
        ]

        if not matches:
            msg = f"Unknown class: {name}"
            raise CompilationError(msg)

        if len(matches) > 1:
            candidates = ", ".join([str(m) for m in matches])
            msg = f"Ambiguous class {name!r}; use a qualified name: {candidates}"
            raise CompilationError(msg)

        return matches[0]

    def parent_class_name(
        self, class_path: ReferencePath, declaration: ClassDeclaration
    ) -> ReferencePath | None:
        """Return the explicit or implicit parent class name."""
        if declaration.parent is not None:
            return declaration.parent

        if declaration.is_interface:
            if class_path == CORE_INTERFACE_PATH:
                return CORE_OBJECT_PATH

            return CORE_INTERFACE_PATH

        return None

    def resolve_class(
        self, name: ReferencePath, current_package: FName, visible_packages: set[FName]
    ) -> tuple[ReferencePath, ClassDeclaration]:
        path = self.resolve_class_path(name, current_package, visible_packages)
        return path, self.classes[path]

    def resolve_parent_classes(
        self, packages: tuple[PackageConfig, ...]
    ) -> dict[ReferencePath, ReferencePath | None]:
        if self._parent_cache is not None and self._parent_cache_packages == packages:
            return self._parent_cache.copy()

        configs = {config.name: config for config in packages}
        visibility = {
            name: collect_visible_packages(config, packages) for name, config in configs.items()
        }
        parents: dict[ReferencePath, ReferencePath | None] = {}

        for class_path, declaration in self.classes.items():
            if class_path.outer is None:
                msg = f"Expected qualified class path, got {class_path}"
                raise ValueError(msg)

            package_key = class_path.outer.name
            config = configs[package_key]
            parent_name = self.parent_class_name(class_path, declaration)

            if parent_name is None:
                parents[class_path] = None
                continue

            with declaration_context(class_path, declaration.location):
                parent_path, _ = self.resolve_class(
                    parent_name, config.name, visibility[package_key]
                )
                parents[class_path] = parent_path

        self._parent_cache = parents
        self._parent_cache_packages = packages
        return parents.copy()

    def inheritance_order(
        self, parents: Mapping[ReferencePath, ReferencePath | None]
    ) -> tuple[ReferencePath, ...]:
        ordered: list[ReferencePath] = []
        completed: set[ReferencePath] = set()
        active: list[ReferencePath] = []
        active_set: set[ReferencePath] = set()

        def visit(class_path: ReferencePath) -> None:
            if class_path in completed:
                return

            if class_path in active_set:
                start = active.index(class_path)
                cycle = [*active[start:], class_path]
                description = " -> ".join([str(c) for c in cycle])
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
        self, class_path: ReferencePath, parents: Mapping[ReferencePath, ReferencePath | None]
    ) -> Iterator[tuple[ReferencePath, ClassDeclaration]]:
        current: ReferencePath | None = class_path

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
        self,
        class_path: ReferencePath,
        name: FName,
        parents: Mapping[ReferencePath, ReferencePath | None],
    ) -> ResolvedMember[VariableDeclaration]:

        for owner, declaration in self.iter_class_hierarchy(class_path, parents):
            for variable in declaration.variables:
                if variable.name == name:
                    return ResolvedMember(owner, variable)

        msg = f"Unknown variable {name!r} on {class_path}"
        raise UnknownPropertyError(msg)

    def resolve_function(
        self,
        class_path: ReferencePath,
        name: FName,
        parents: Mapping[ReferencePath, ReferencePath | None],
    ) -> ResolvedMember[FunctionDeclaration]:

        for owner, declaration in self.iter_class_hierarchy(class_path, parents):
            for function in declaration.functions:
                if function.name == name:
                    return ResolvedMember(owner, function)

        msg = f"Unknown function {name!r} on {class_path}"
        raise CompilationError(msg)

    def resolve_type(
        self,
        type_ref: TypeReference | None,
        current_class: ReferencePath,
        visible_packages: set[FName],
        parents: Mapping[ReferencePath, ReferencePath | None],
    ) -> ResolvedType:
        if type_ref is None:
            return ResolvedType(TypeCategory.VOID)

        package_path = current_class.outer

        if package_path is None or package_path.is_none():
            msg = f"Expected a qualified current class path, got {current_class}"
            raise ValueError(msg)

        current_package = package_path.name
        name = type_ref.name

        if name == DELEGATE_TYPE:
            if len(type_ref.arguments) != 1:
                msg = "delegate requires exactly one signature"
                raise CompilationError(msg)

            signature = type_ref.arguments[0]

            if signature.arguments or signature.modifiers:
                msg = "Delegate signature must be a function name"
                raise CompilationError(msg)

            owner_name = signature.name.outer
            function_name = signature.name.name

            if owner_name is not None and not owner_name.is_none():
                owner_path, _ = self.resolve_class(owner_name, current_package, visible_packages)
            else:
                owner_path = current_class

            member = self.resolve_function(owner_path, function_name, parents)

            if member.declaration.func_category is not FunctionCategory.DELEGATE:
                msg = (
                    f"{member.owner_class}.{member.declaration.name} is not a delegate declaration"
                )
                raise CompilationError(msg)

            path = member.owner_class + member.declaration.name
            return ResolvedType(TypeCategory.DELEGATE, path)

        if name == MAP_TYPE:
            msg = "Native map type resolution is not implemented"
            raise NotImplementedError(msg)

        if name == ARRAY_TYPE:
            if len(type_ref.arguments) != 1:
                msg = "array requires exactly one type argument"
                raise CompilationError(msg)

            element_type = self.resolve_type(
                type_ref.arguments[0], current_class, visible_packages, parents
            )
            return ResolvedType(TypeCategory.ARRAY, arguments=(element_type,))

        if name == CLASS_TYPE:
            if len(type_ref.arguments) > 1:
                msg = "class accepts at most one type argument"
                raise CompilationError(msg)

            bound_ref = (
                type_ref.arguments[0] if type_ref.arguments else TypeReference(CORE_OBJECT_PATH)
            )
            bound = self.resolve_type(bound_ref, current_class, visible_packages, parents)

            if bound.category is not TypeCategory.OBJECT:
                msg = "class requires an object class as its bound"
                raise CompilationError(msg)

            return ResolvedType(TypeCategory.CLASS, arguments=(bound,))

        if type_ref.arguments:
            msg = f"Type {name} does not accept type arguments"
            raise CompilationError(msg)

        primitive = PRIMITIVE_TYPES.get(name)

        if primitive is not None:
            return primitive

        owner_name = name.outer

        if owner_name is None or owner_name.is_none():
            member_type = self.find_member_type(current_class, name.name, parents)

            if member_type is not None:
                return member_type

            member_type = self.find_visible_member_type(
                name.name, current_package, visible_packages
            )

            if member_type is not None:
                return member_type

        elif name not in self.classes and name not in self.intrinsics:
            # Examples: Object.Vector or Core.Object.Vector.
            owner_path, _ = self.resolve_class(owner_name, current_package, visible_packages)
            member_type = self.find_member_type(owner_path, name.name, parents)

            if member_type is None:
                msg = f"Unknown struct or enum {name.name!r} on {owner_path}"
                raise CompilationError(msg)

            return member_type

        class_path = self.resolve_class_path(
            name, current_package, visible_packages, include_intrinsics=True
        )
        return ResolvedType(TypeCategory.OBJECT, class_path)

    def resolve_struct(
        self,
        class_path: ReferencePath,
        name: FName,
        parents: Mapping[ReferencePath, ReferencePath | None],
    ) -> ResolvedMember[StructDeclaration]:

        for owner, declaration in self.iter_class_hierarchy(class_path, parents):
            for struct in declaration.structs:
                if struct.name == name:
                    return ResolvedMember(owner, struct)

        msg = f"Unknown struct {name!r} on {class_path}"
        raise CompilationError(msg)

    def resolve_enum(
        self,
        class_path: ReferencePath,
        name: FName,
        parents: Mapping[ReferencePath, ReferencePath | None],
    ) -> ResolvedMember[EnumDeclaration]:

        for owner, declaration in self.iter_class_hierarchy(class_path, parents):
            for enum in declaration.enums:
                if enum.name == name:
                    return ResolvedMember(owner, enum)

        msg = f"Unknown enum {name!r} on {class_path}"
        raise CompilationError(msg)

    def find_member_type(
        self,
        class_path: ReferencePath,
        name: FName,
        parents: Mapping[ReferencePath, ReferencePath | None],
    ) -> ResolvedType | None:

        for owner, declaration in self.iter_class_hierarchy(class_path, parents):
            for struct in declaration.structs:
                if struct.name == name:
                    return ResolvedType(TypeCategory.STRUCT, owner + struct.name)

            for enum in declaration.enums:
                if enum.name == name:
                    return ResolvedType(TypeCategory.ENUM, owner + enum.name)

        return None

    def resolve_binary_operator(
        self,
        name: Operator | Keyword,
        left: ResolvedType,
        right: ResolvedType,
        current_class: ReferencePath,
        visible_packages: set[FName],
        parents: Mapping[ReferencePath, ReferencePath | None],
    ) -> ResolvedMember[OperatorDeclaration]:

        for owner, declaration in self.iter_class_hierarchy(current_class, parents):
            matches: list[OperatorDeclaration] = []

            for operator in declaration.operators:
                if operator.op_category is not OperatorCategory.BINARY or operator.name != name:
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

    def lookup_class(self, path: ReferencePath) -> ClassDeclaration | IntrinsicDefinition:

        intrinsic = self.intrinsics.get(path)
        if intrinsic is not None:
            return intrinsic

        declaration = self.classes.get(path)
        if declaration is not None:
            return declaration

        msg = f"Unknown class: {path}"
        raise CompilationError(msg)

    def property_class(self, resolved: ResolvedType) -> IntrinsicDefinition:
        path = PROPERTY_CLASS_PATHS.get(resolved.category)

        if path is None:
            msg = f"Type {resolved} cannot be represented as a property"
            raise CompilationError(msg)

        return self.intrinsics[path]

    def resolve_unary_operator(
        self,
        name: Keyword | Operator,
        category: Literal[OperatorCategory.PREFIX, OperatorCategory.POSTFIX],
        operand: ResolvedType,
        current_class: ReferencePath,
        visible_packages: set[FName],
        parents: Mapping[ReferencePath, ReferencePath | None],
    ) -> ResolvedMember[OperatorDeclaration]:

        for owner, declaration in self.iter_class_hierarchy(current_class, parents):
            matches: list[OperatorDeclaration] = []

            for operator in declaration.operators:
                if operator.op_category is not category or operator.name != name:
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
        struct_path: ReferencePath,
        name: FName,
        parents: Mapping[ReferencePath, ReferencePath | None],
        visible_packages: set[FName],
    ) -> ResolvedMember[VariableDeclaration]:
        current = struct_path
        visited: set[ReferencePath] = set()

        while True:
            if current in visited:
                msg = f"Struct inheritance cycle while resolving {struct_path}.{name}"
                raise CompilationError(msg)

            visited.add(current)
            owner_class, struct_name = current.split()
            if owner_class is None:
                msg = f"Expected a fully qualified struct, got {current}."
                raise ValueError(msg)
            member = self.resolve_struct(owner_class, struct_name, parents)
            declaration = member.declaration

            for variable in declaration.variables:
                if variable.name == name:
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

            current = parent.declaration_path

        msg = f"Unknown field {name!r} on struct {struct_path}"
        raise UnknownPropertyError(msg)

    def struct_hierarchy(
        self,
        struct_path: ReferencePath,
        parents: Mapping[ReferencePath, ReferencePath | None],
        packages: tuple[PackageConfig, ...],
    ) -> list[tuple[ReferencePath, StructDeclaration]]:
        """Return parent-to-child declarations and their owning classes."""
        hierarchy: list[tuple[ReferencePath, StructDeclaration]] = []
        visited: set[ReferencePath] = set()
        current = struct_path

        while True:
            if current in visited:
                msg = f"Struct inheritance cycle at {current}"
                raise CompilationError(msg)

            visited.add(current)

            owner_class, struct_name = current.split()
            if owner_class is None:
                msg = f"Expected a fully qualified struct, got {current}."
                raise ValueError(msg)

            member = self.resolve_struct(owner_class, struct_name, parents)
            declaration = member.declaration
            hierarchy.append((member.owner_class, declaration))

            if declaration.parent is None:
                break

            if member.owner_class.outer is None:
                msg = f"Expected fully qualified class name, got {member.owner_class}"
                raise ValueError(msg)

            package_name = member.owner_class.outer.name
            config = next(config for config in packages if config.name == package_name)
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
        self,
        class_path: ReferencePath,
        base_path: ReferencePath,
        parents: Mapping[ReferencePath, ReferencePath | None],
    ) -> bool:
        """Check whether a class is the given base class or extends it."""
        self.lookup_class(base_path)

        current: ReferencePath | None = class_path
        visited: set[ReferencePath] = set()

        while current is not None:
            if current in visited:
                msg = f"Inheritance cycle while checking {class_path}: {current}"
                raise CompilationError(msg)

            visited.add(current)
            definition = self.lookup_class(current)

            if current == base_path:
                return True

            if isinstance(definition, IntrinsicDefinition):
                current = definition.parent
            else:
                current = parents[current]

        return False

    def resolve_within_class(
        self,
        class_path: ReferencePath,
        parents: Mapping[ReferencePath, ReferencePath | None],
        packages: Iterable[PackageConfig],
    ) -> ReferencePath:
        configs = {config.name: config for config in packages}
        package_list = tuple(configs.values())

        for owner, declaration in self.iter_class_hierarchy(class_path, parents):
            if declaration.within is None:
                continue

            if owner.outer is None:
                msg = f"Expected fully qualified class path, got {owner}"
                raise ValueError(msg)
            config = configs[owner.outer.name]
            visible = collect_visible_packages(config, package_list)

            return self.resolve_class_path(
                declaration.within, config.name, visible, include_intrinsics=True
            )

        return CORE_OBJECT_PATH

    def find_visible_member_type(
        self, name: FName, current_package: FName, visible_packages: set[FName]
    ) -> ResolvedType | None:
        allowed = {current_package, *visible_packages}
        candidates: list[ResolvedType] = []

        for owner, declaration in self.classes.items():
            if owner.base not in allowed:
                continue

            candidates.extend(
                [
                    ResolvedType(TypeCategory.STRUCT, owner + struct.name)
                    for struct in declaration.structs
                    if struct.name == name
                ]
            )

            candidates.extend(
                [
                    ResolvedType(TypeCategory.ENUM, owner + enum.name)
                    for enum in declaration.enums
                    if enum.name == name
                ]
            )

        local = [
            candidate
            for candidate in candidates
            if candidate.declaration_path is not None
            and candidate.declaration_path.base == current_package
        ]
        candidates = local or candidates

        if len(candidates) > 1:
            paths = ", ".join(str(candidate.declaration_path) for candidate in candidates)
            msg = f"Ambiguous struct or enum {name!r}: {paths}"
            raise CompilationError(msg)

        return candidates[0] if candidates else None

    def resolve_array_dimension(
        self,
        name: ReferencePath,
        current_class: ReferencePath,
        visible_packages: set[FName],
        parents: Mapping[ReferencePath, ReferencePath | None],
    ) -> int:
        resolved = self.resolve_type(TypeReference(name), current_class, visible_packages, parents)

        if resolved.category is not TypeCategory.ENUM:
            msg = f"Resolving non-enum array dimension {name!r} is not implemented"
            raise NotImplementedError(msg)

        if resolved.declaration_path is None:
            msg = "Resolved array dimension enum has no declaration path"
            raise ValueError(msg)

        owner, enum_name = resolved.declaration_path.split()
        if owner is None:
            msg = f"Expected a fully qualified enum, got {resolved.declaration_path}."
            raise ValueError(msg)

        member = self.resolve_enum(owner, enum_name, parents)
        dimension = len(member.declaration.members)

        if not 1 < dimension <= MAX_FIXED_ARRAY_DIMENSION:
            msg = (
                f"Array dimension {name!r} resolves to {dimension}; "
                f"expected 2 through {MAX_FIXED_ARRAY_DIMENSION}"
            )
            raise CompilationError(msg)

        return dimension
