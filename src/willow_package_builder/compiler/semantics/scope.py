from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from willow_package_builder.logging import CompilationError, WarningCode, warn

if TYPE_CHECKING:
    from collections.abc import Mapping

    from willow_package_builder.compiler.syntax.declarations import (
        FunctionDeclaration,
        ParameterDeclaration,
        VariableDeclaration,
    )
    from willow_package_builder.upackage import FName, ReferencePath

    from .reference_database import ReferenceDatabase


class VariableCategory(StrEnum):
    PARAMETER = "parameter"
    LOCAL = "local"
    INSTANCE = "instance"


@dataclass(frozen=True)
class VariableSymbol:
    category: VariableCategory
    owner_class: ReferencePath
    declaration: ParameterDeclaration | VariableDeclaration


@dataclass
class FunctionScope:
    class_path: ReferencePath
    function: FunctionDeclaration
    references: ReferenceDatabase
    parents: Mapping[ReferencePath, ReferencePath | None]
    state_name: FName | None = field(default=None, kw_only=True)

    _variables: dict[FName, VariableSymbol] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        for parameter in self.function.parameters:
            self.add_variable(parameter, VariableCategory.PARAMETER)

    def add_variable(
        self,
        declaration: ParameterDeclaration | VariableDeclaration,
        variable_category: VariableCategory,
    ) -> None:
        key = declaration.name

        for owner, class_declaration in self.references.iter_class_hierarchy(
            self.class_path, self.parents
        ):
            if any(variable.name == key for variable in class_declaration.variables):
                warn(
                    WarningCode.SHADOWED_INSTANCE_VARIABLE,
                    f"{declaration.name!r} in "
                    f"{self.class_path}.{self.function.name} "
                    f"shadows instance variable {owner}.{declaration.name}.",
                )
                break

        if key in self._variables:
            msg = (
                f"Duplicate parameter or local {declaration.name!r} "
                f"in {self.class_path}.{self.function.name}"
            )
            raise CompilationError(msg)

        self._variables[key] = VariableSymbol(variable_category, self.class_path, declaration)

    def add_local(self, declaration: VariableDeclaration) -> None:
        self.add_variable(declaration, VariableCategory.LOCAL)

    def resolve_variable(self, name: FName) -> VariableSymbol:
        local = self._variables.get(name)

        if local is not None:
            return local

        member = self.references.resolve_variable(self.class_path, name, self.parents)

        return VariableSymbol(VariableCategory.INSTANCE, member.owner_class, member.declaration)
