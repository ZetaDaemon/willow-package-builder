from abc import ABC
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .declarations import VariableDeclaration
    from .expressions import Expression


class Statement(ABC):
    pass


@dataclass
class AssignmentStatement(Statement):
    target: Expression
    value: Expression


@dataclass
class ReturnStatement(Statement):
    value: Expression | None = None


@dataclass
class ExpressionStatement(Statement):
    expression: Expression


@dataclass
class EmptyStatement(Statement):
    pass


@dataclass
class FunctionBody:
    locals: list[VariableDeclaration]
    statements: list[Statement]


@dataclass
class IfStatement(Statement):
    condition: Expression
    then_statements: list[Statement]
    else_statements: list[Statement] | None = None


@dataclass
class WhileStatement(Statement):
    condition: Expression
    statements: list[Statement]


@dataclass
class BreakStatement(Statement):
    pass


@dataclass
class ContinueStatement(Statement):
    pass
