from abc import ABC
from dataclasses import dataclass


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
