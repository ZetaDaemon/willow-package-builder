from abc import ABC
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from willow_package_builder.compiler.syntax.declarations import OperatorCategory


class Expression(ABC):
    pass


@dataclass
class IntegerExpression(Expression):
    value: int


@dataclass
class IdentifierExpression(Expression):
    name: str


@dataclass
class BinaryExpression(Expression):
    left: Expression
    operator: str
    right: Expression


@dataclass
class UnaryExpression(Expression):
    operator: str
    operand: Expression
    op_category: Literal[OperatorCategory.PREFIX, OperatorCategory.POSTFIX]


@dataclass
class BooleanExpression(Expression):
    value: bool


@dataclass
class FloatExpression(Expression):
    value: float


@dataclass
class StringExpression(Expression):
    value: str


@dataclass
class CallExpression(Expression):
    callee: Expression
    arguments: list[Expression | None]
