from abc import ABC
from dataclasses import KW_ONLY, dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from willow_package_builder.source_location import SourceLocation

    from .declarations import VariableDeclaration
    from .expressions import Expression


@dataclass
class Statement(ABC):
    _: KW_ONLY
    location: SourceLocation | None = field(default=None)


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
    function_locals: list[VariableDeclaration]
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


@dataclass
class ForStatement(Statement):
    initializer: Statement
    condition: Expression
    increment: Statement
    statements: list[Statement]


@dataclass
class DoUntilStatement(Statement):
    statements: list[Statement]
    condition: Expression
