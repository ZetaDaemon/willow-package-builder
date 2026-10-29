from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .lexer import Token


class OperatorType(StrEnum):
    BINARY = "operator"
    PREFIX = "preoperator"
    POSTFIX = "postoperator"


class FunctionType(StrEnum):
    FUNCTION = "function"
    EVENT = "event"
    DELEGATE = "delegate"


@dataclass
class ConstantDeclaration:
    name: str
    value_tokens: tuple[Token, ...]


@dataclass
class EnumDeclaration:
    name: str
    members: tuple[str, ...]


@dataclass
class StructDeclaration:
    name: str
    parent: str | None = None
    modifiers: tuple[str, ...] = ()

    variables: list[VariableDeclaration] = field(default_factory=list)
    default_tokens: tuple[Token, ...] | None = None


@dataclass(frozen=True)
class TypeReference:
    name: str
    arguments: tuple[TypeReference, ...] = ()


@dataclass
class VariableDeclaration:
    name: str
    type_ref: TypeReference
    array_dimension: int = 1
    modifiers: tuple[str, ...] = ()
    category_tokens: tuple[Token, ...] | None = None


@dataclass
class ParameterDeclaration:
    name: str
    type_ref: TypeReference
    modifiers: tuple[str, ...] = ()
    default_tokens: tuple[Token, ...] | None = None


@dataclass
class OperatorDeclaration:
    name: str
    op_type: OperatorType
    return_type: TypeReference
    parameters: list[ParameterDeclaration]
    native_index: int | None
    precedence: int | None
    modifiers: tuple[str, ...]

    has_body: bool = False
    body_tokens: list[Token] | None = None


@dataclass
class FunctionDeclaration:
    name: str
    return_type: TypeReference | None
    parameters: list[ParameterDeclaration]

    func_type: FunctionType = FunctionType.FUNCTION
    modifiers: tuple[str, ...] = ()
    native_index: int | None = None

    has_body: bool = False
    body_tokens: list[Token] | None = None


@dataclass
class ClassModifier:
    name: str
    arguments: tuple[Token, ...] | None = None


@dataclass
class ClassDeclaration:
    name: str
    parent: str | None

    is_interface: bool = False
    within: str | None = None
    modifiers: tuple[ClassModifier, ...] = ()

    constants: list[ConstantDeclaration] = field(default_factory=list)
    enums: list[EnumDeclaration] = field(default_factory=list)
    structs: list[StructDeclaration] = field(default_factory=list)
    variables: list[VariableDeclaration] = field(default_factory=list)
    functions: list[FunctionDeclaration] = field(default_factory=list)
    operators: list[OperatorDeclaration] = field(default_factory=list)
