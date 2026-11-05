from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from willow_package_builder.logging import SourceLocation
from willow_package_builder.properties.values import Value
from willow_package_builder.upackage import FName

if TYPE_CHECKING:
    from willow_package_builder.compiler.syntax.modifiers import (
        ClassModifierName,
        ParameterModifier,
        StructModifier,
        VariableModifier,
    )

    from .lexer import Token
    from .modifiers import FunctionModifier

MAX_FIXED_ARRAY_DIMENSION = 2048


class OperatorCategory(StrEnum):
    BINARY = "operator"
    PREFIX = "preoperator"
    POSTFIX = "postoperator"


class FunctionCategory(StrEnum):
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


@dataclass(frozen=True)
class TypeReference:
    name: str
    arguments: tuple[TypeReference, ...] = ()
    modifiers: tuple[VariableModifier, ...] = ()


@dataclass
class VariableDeclaration:
    name: str
    type_ref: TypeReference
    array_dimension: int = 1
    modifiers: tuple[VariableModifier, ...] = ()
    category_tokens: tuple[Token, ...] | None = None
    array_dimension_name: str | None = field(default=None)

    location: SourceLocation | None = field(default=None, compare=False, repr=False, kw_only=True)


@dataclass
class ParameterDeclaration:
    name: str
    type_ref: TypeReference
    modifiers: tuple[ParameterModifier, ...] = ()
    default_tokens: tuple[Token, ...] | None = None
    array_dimension: int = 1
    array_dimension_name: str | None = field(default=None)

    location: SourceLocation | None = field(default=None, compare=False, repr=False, kw_only=True)


@dataclass
class OperatorDeclaration:
    name: str
    op_category: OperatorCategory
    return_type: TypeReference
    parameters: list[ParameterDeclaration]
    native_index: int | None
    precedence: int | None
    modifiers: tuple[FunctionModifier, ...]

    has_body: bool = False
    body_tokens: list[Token] | None = None

    location: SourceLocation | None = field(default=None, compare=False, repr=False, kw_only=True)


@dataclass
class FunctionDeclaration:
    name: str
    return_type: TypeReference | None
    parameters: list[ParameterDeclaration]

    func_category: FunctionCategory = FunctionCategory.FUNCTION
    modifiers: tuple[FunctionModifier, ...] = ()
    native_index: int | None = None

    has_body: bool = False
    body_tokens: list[Token] | None = None

    location: SourceLocation | None = field(default=None, compare=False, repr=False, kw_only=True)


@dataclass
class ClassModifier:
    name: ClassModifierName
    arguments: tuple[Token, ...] | None = None


@dataclass
class StructDeclaration:
    name: str
    parent: str | None = None
    modifiers: tuple[StructModifier, ...] = ()

    variables: list[VariableDeclaration] = field(default_factory=list)
    default_tokens: tuple[Token, ...] | None = None
    parsed_defaults: dict[str, object] = field(default_factory=dict)
    defaults: dict[FName, Value] = field(default_factory=dict)

    default_parse_error: str | None = None
    location: SourceLocation | None = field(default=None, compare=False, repr=False, kw_only=True)


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

    default_tokens: tuple[Token, ...] | None = None
    parsed_defaults: dict[str, object] = field(default_factory=dict)
    defaults: dict[FName, Value] = field(default_factory=dict)

    default_parse_error: str | None = None
    location: SourceLocation | None = field(default=None, compare=False, repr=False, kw_only=True)
