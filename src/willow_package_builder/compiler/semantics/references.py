from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from willow_package_builder.compiler.syntax.declarations import (
    ClassDeclaration,
    EnumDeclaration,
    FunctionDeclaration,
    OperatorDeclaration,
    OperatorType,
    StructDeclaration,
    TypeReference,
    VariableDeclaration,
)
from willow_package_builder.logging import CompilationError
from willow_package_builder.package_config import PackageConfig, collect_visible_packages

from .intrinsics import INTRINSICS, PROPERTY_CLASS_PATHS, IntrinsicDefinition
from .types import ResolvedType, TypeType

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

PRIMITIVE_TYPES = {
    t.value: ResolvedType(t)
    for t in (
        TypeType.BYTE,
        TypeType.INT,
        TypeType.BOOL,
        TypeType.FLOAT,
        TypeType.STRING,
        TypeType.NAME,
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

    def add_class(self, package_name: str, declaration: ClassDeclaration) -> None:
        path = f"{package_name}.{declaration.name}"
        key = path.casefold()

        if key in self.classes:
            msg = f"Class already registered: {path}"
            raise CompilationError(msg)

        for operator in declaration.operators:
            if operator.op_type is OperatorType.BINARY and operator.precedence is None:
                msg = f"Binary operator {operator.name!r} in {path} has no precedence"
                raise CompilationError(msg)

        self.classes[key] = declaration

        for operator in declaration.operators:
            operator_key = operator.name.casefold()
            self.operators.setdefault(operator_key, []).append(operator)

    def resolve_class(
        self, name: str, *, current_package: str, visible_packages: set[str]
    ) -> tuple[str, ClassDeclaration]:
        allowed_packages = {
            current_package.casefold(),
            *(package.casefold() for package in visible_packages),
        }

        # Explicitly qualified name.
        if "." in name:
            key = name.casefold()
            package_name = key.partition(".")[0]

            if package_name not in allowed_packages:
                msg = f"Package {package_name!r} is not available to {current_package}"
                raise CompilationError(msg)

            declaration = self.classes.get(key)

            if declaration is None:
                msg = f"Unknown class: {name}"
                raise CompilationError(msg)

            return key, declaration

        # Prefer a class declared in the current package.
        local_key = f"{current_package}.{name}".casefold()
        local = self.classes.get(local_key)

        if local is not None:
            return local_key, local

        matches: list[tuple[str, ClassDeclaration]] = []

        for package_name in sorted(allowed_packages):
            key = f"{package_name}.{name}".casefold()
            declaration = self.classes.get(key)

            if declaration is not None:
                matches.append((key, declaration))

        if not matches:
            msg = f"Unknown class: {name}"
            raise CompilationError(msg)

        if len(matches) > 1:
            candidates = ", ".join(path for path, _ in matches)
            msg = f"Ambiguous class {name!r}; use a qualified name: {candidates}"
            raise CompilationError(msg)

        return matches[0]

    def resolve_parent_classes(self, packages: tuple[PackageConfig, ...]) -> dict[str, str | None]:
        configs = {config.name.casefold(): config for config in packages}

        visibility = {
            name: collect_visible_packages(config, packages) for name, config in configs.items()
        }

        parents: dict[str, str | None] = {}

        for class_path, declaration in self.classes.items():
            package_key = class_path.partition(".")[0]
            config = configs[package_key]

            parent_name = declaration.parent

            if parent_name is None and declaration.is_interface:
                parent_name = "Core.Object" if class_path == "core.interface" else "Core.Interface"

            if parent_name is None:
                parents[class_path] = None
                continue

            parent_path, _ = self.resolve_class(
                parent_name, current_package=config.name, visible_packages=visibility[package_key]
            )

            parents[class_path] = parent_path

        return parents

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
                    return ResolvedMember(owner_class=owner, declaration=variable)

        msg = f"Unknown variable {name!r} on {class_path}"
        raise CompilationError(msg)

    def resolve_function(
        self, class_path: str, name: str, parents: Mapping[str, str | None]
    ) -> ResolvedMember[FunctionDeclaration]:
        key = name.casefold()

        for owner, declaration in self.iter_class_hierarchy(class_path, parents):
            for function in declaration.functions:
                if function.name.casefold() == key:
                    return ResolvedMember(owner_class=owner, declaration=function)

        msg = f"Unknown function {name!r} on {class_path}"
        raise CompilationError(msg)

    def resolve_type(
        self,
        type_ref: TypeReference | None,
        *,
        current_class: str,
        visible_packages: set[str],
        parents: Mapping[str, str | None],
    ) -> ResolvedType:
        current_package = current_class.partition(".")[0]

        if type_ref is None:
            return ResolvedType(type=TypeType.VOID)

        name = type_ref.name.casefold()

        if name == "array":
            if len(type_ref.arguments) != 1:
                msg = "array requires exactly one type argument"
                raise CompilationError(msg)

            element_type = self.resolve_type(
                type_ref.arguments[0],
                current_class=current_class,
                visible_packages=visible_packages,
                parents=parents,
            )

            return ResolvedType(type=TypeType.ARRAY, arguments=(element_type,))

        if name == "class":
            if len(type_ref.arguments) > 1:
                msg = "class accepts at most one type argument"
                raise CompilationError(msg)

            bound_ref = (
                type_ref.arguments[0] if type_ref.arguments else TypeReference(name="Core.Object")
            )

            bound = self.resolve_type(
                bound_ref,
                current_class=current_class,
                visible_packages=visible_packages,
                parents=parents,
            )

            if bound.type is not TypeType.OBJECT:
                msg = "class requires an object class as its bound"
                raise CompilationError(msg)

            return ResolvedType(type=TypeType.CLASS, arguments=(bound,))

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

        elif name not in self.classes:
            # Examples: Object.Vector or Core.Object.Vector.
            owner_name, _, member_name = type_ref.name.rpartition(".")

            owner_path, _ = self.resolve_class(
                owner_name, current_package=current_package, visible_packages=visible_packages
            )

            member_type = self.find_member_type(owner_path, member_name, parents)

            if member_type is None:
                msg = f"Unknown struct or enum {member_name!r} on {owner_path}"
                raise CompilationError(msg)

            return member_type

        class_path, _ = self.resolve_class(
            type_ref.name, current_package=current_package, visible_packages=visible_packages
        )

        return ResolvedType(type=TypeType.OBJECT, declaration_path=class_path)

    def resolve_struct(
        self, class_path: str, name: str, parents: Mapping[str, str | None]
    ) -> ResolvedMember[StructDeclaration]:
        key = name.casefold()

        for owner, declaration in self.iter_class_hierarchy(class_path, parents):
            for struct in declaration.structs:
                if struct.name.casefold() == key:
                    return ResolvedMember(owner_class=owner, declaration=struct)

        msg = f"Unknown struct {name!r} on {class_path}"
        raise CompilationError(msg)

    def resolve_enum(
        self, class_path: str, name: str, parents: Mapping[str, str | None]
    ) -> ResolvedMember[EnumDeclaration]:
        key = name.casefold()

        for owner, declaration in self.iter_class_hierarchy(class_path, parents):
            for enum in declaration.enums:
                if enum.name.casefold() == key:
                    return ResolvedMember(owner_class=owner, declaration=enum)

        msg = f"Unknown enum {name!r} on {class_path}"
        raise CompilationError(msg)

    def find_member_type(
        self, class_path: str, name: str, parents: Mapping[str, str | None]
    ) -> ResolvedType | None:
        key = name.casefold()

        for owner, declaration in self.iter_class_hierarchy(class_path, parents):
            for struct in declaration.structs:
                if struct.name.casefold() == key:
                    return ResolvedType(
                        type=TypeType.STRUCT, declaration_path=f"{owner}.{struct.name}".casefold()
                    )

            for enum in declaration.enums:
                if enum.name.casefold() == key:
                    return ResolvedType(
                        type=TypeType.ENUM, declaration_path=f"{owner}.{enum.name}".casefold()
                    )

        return None

    def resolve_binary_operator(
        self,
        name: str,
        left: ResolvedType,
        right: ResolvedType,
        *,
        current_class: str,
        visible_packages: set[str],
        parents: Mapping[str, str | None],
    ) -> ResolvedMember[OperatorDeclaration]:
        key = name.casefold()

        for owner, declaration in self.iter_class_hierarchy(current_class, parents):
            matches: list[OperatorDeclaration] = []

            for operator in declaration.operators:
                if operator.op_type is not OperatorType.BINARY or operator.name.casefold() != key:
                    continue

                left_type = self.resolve_type(
                    operator.parameters[0].type_ref,
                    current_class=owner,
                    visible_packages=visible_packages,
                    parents=parents,
                )

                if left_type != left:
                    continue

                right_type = self.resolve_type(
                    operator.parameters[1].type_ref,
                    current_class=owner,
                    visible_packages=visible_packages,
                    parents=parents,
                )

                if right_type == right:
                    matches.append(operator)

            if len(matches) > 1:
                msg = f"Multiple exact overloads of {name!r} on {owner} for {left!r} and {right!r}"
                raise CompilationError(msg)

            if matches:
                return ResolvedMember(owner_class=owner, declaration=matches[0])

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
        path = PROPERTY_CLASS_PATHS.get(resolved.type)

        if path is None:
            msg = f"Type {resolved!r} cannot be represented as a property"
            raise CompilationError(msg)

        return self.intrinsics[path.casefold()]
