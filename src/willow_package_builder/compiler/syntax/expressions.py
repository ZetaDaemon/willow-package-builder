from abc import ABC
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from willow_package_builder.compiler.syntax.declarations import OperatorCategory
    from willow_package_builder.compiler.syntax.keyword import Keyword
    from willow_package_builder.compiler.syntax.punctuation import Operator
    from willow_package_builder.upackage import FName


class Expression(ABC):
    """Representation of code that produces or refers to a value."""


@dataclass
class IntegerExpression(Expression):
    value: int


@dataclass
class IdentifierExpression(Expression):
    name: FName


@dataclass
class BinaryExpression(Expression):
    left: Expression
    operator: Operator | Keyword
    right: Expression


@dataclass
class UnaryExpression(Expression):
    operator: Operator | Keyword
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


@dataclass
class MemberExpression(Expression):
    object: Expression
    name: FName


@dataclass
class SelfExpression(Expression):
    pass


@dataclass
class IndexExpression(Expression):
    array: Expression
    index: Expression


@dataclass
class NameExpression(Expression):
    value: FName


@dataclass
class ArrayCountExpression(Expression):
    array: Expression
