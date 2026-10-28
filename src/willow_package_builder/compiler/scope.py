from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from willow_package_builder import logging
from willow_package_builder.logging import CompilationError

if TYPE_CHECKING:
    from .declarations import FunctionDeclaration, ParameterDeclaration, VariableDeclaration
    from .references import ReferenceDatabase


class VariableType(StrEnum):
    PARAMETER = "parameter"
    LOCAL = "local"
    INSTANCE = "instance"


@dataclass(frozen=True)
class VariableSymbol:
    type: VariableType
    owner_class: str
    declaration: ParameterDeclaration | VariableDeclaration


@dataclass
class FunctionScope:
    class_path: str
    function: FunctionDeclaration
    references: ReferenceDatabase
    parents: Mapping[str, str | None]

    _variables: dict[str, VariableSymbol] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        for parameter in self.function.parameters:
            self.add_variable(parameter, VariableType.PARAMETER)

    def add_variable(
        self, declaration: ParameterDeclaration | VariableDeclaration, variable_type: VariableType
    ) -> None:
        key = declaration.name.casefold()

        for owner, class_declaration in self.references.iter_class_hierarchy(
            self.class_path, self.parents
        ):
            if any(variable.name.casefold() == key for variable in class_declaration.variables):
                logging.warn(
                    logging.WarningCode.SHADOWED_INSTANCE_VARIABLE,
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

        self._variables[key] = VariableSymbol(
            type=variable_type, owner_class=self.class_path.casefold(), declaration=declaration
        )

    def add_local(self, declaration: VariableDeclaration) -> None:
        self.add_variable(declaration, VariableType.LOCAL)

    def resolve_variable(self, name: str) -> VariableSymbol:
        local = self._variables.get(name.casefold())

        if local is not None:
            return local

        member = self.references.resolve_variable(self.class_path, name, self.parents)

        return VariableSymbol(
            type=VariableType.INSTANCE,
            owner_class=member.owner_class,
            declaration=member.declaration,
        )
