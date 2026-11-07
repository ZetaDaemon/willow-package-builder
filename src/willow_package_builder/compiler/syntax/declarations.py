from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from willow_package_builder.compiler.syntax.keyword import Keyword, KeywordEnum
from willow_package_builder.upackage import FName, ReferencePath

if TYPE_CHECKING:
    from willow_package_builder.compiler.syntax.modifiers import (
        ClassModifierName,
        ParameterModifier,
        StructModifier,
        VariableModifier,
    )
    from willow_package_builder.compiler.syntax.punctuation import Operator
    from willow_package_builder.logging import SourceLocation
    from willow_package_builder.properties.values import Value

    from .lexer import Token
    from .modifiers import FunctionModifier

MAX_FIXED_ARRAY_DIMENSION = 2048


class OperatorCategory(KeywordEnum):
    BINARY = "operator"
    PREFIX = "preoperator"
    POSTFIX = "postoperator"


class FunctionCategory(KeywordEnum):
    FUNCTION = "function"
    EVENT = "event"
    DELEGATE = "delegate"


@dataclass
class ConstantDeclaration:
    name: FName
    value_tokens: tuple[Token, ...]


@dataclass
class EnumDeclaration:
    name: FName
    members: tuple[FName, ...]


@dataclass(frozen=True)
class TypeReference:
    name: ReferencePath
    arguments: tuple[TypeReference, ...] = ()
    modifiers: tuple[VariableModifier, ...] = ()


@dataclass
class VariableDeclaration:
    name: FName
    type_ref: TypeReference
    array_dimension: int = 1
    modifiers: tuple[VariableModifier, ...] = ()
    category_tokens: tuple[Token, ...] | None = None
    array_dimension_name: ReferencePath | None = field(default=None)

    location: SourceLocation | None = field(default=None, compare=False, repr=False, kw_only=True)


@dataclass
class ParameterDeclaration:
    name: FName
    type_ref: TypeReference
    modifiers: tuple[ParameterModifier, ...] = ()
    default_tokens: tuple[Token, ...] | None = None
    array_dimension: int = 1
    array_dimension_name: ReferencePath | None = field(default=None)

    location: SourceLocation | None = field(default=None, compare=False, repr=False, kw_only=True)


@dataclass
class OperatorDeclaration:
    name: Operator | Keyword
    op_category: OperatorCategory
    return_type: TypeReference
    parameters: list[ParameterDeclaration]
    native_index: int | None
    precedence: int | None
    modifiers: tuple[FunctionModifier, ...]

    has_body: bool = False
    body_tokens: list[Token] | None = None

    location: SourceLocation | None = field(default=None, compare=False, repr=False, kw_only=True)

    @property
    def fname(self) -> FName:
        return FName(str(self.name))


@dataclass
class FunctionDeclaration:
    name: FName
    return_type: TypeReference | None
    parameters: list[ParameterDeclaration]

    func_category: FunctionCategory = FunctionCategory.FUNCTION
    modifiers: tuple[FunctionModifier, ...] = ()
    native_index: int | None = None

    has_body: bool = False
    body_tokens: list[Token] | None = None

    location: SourceLocation | None = field(default=None, compare=False, repr=False, kw_only=True)

    @property
    def fname(self) -> FName:
        return self.name


@dataclass
class ClassModifier:
    name: ClassModifierName
    arguments: tuple[Token, ...] | None = None


@dataclass
class StructDeclaration:
    name: FName
    parent: ReferencePath | None = None
    modifiers: tuple[StructModifier, ...] = ()

    variables: list[VariableDeclaration] = field(default_factory=list)
    default_tokens: tuple[Token, ...] | None = None
    parsed_defaults: dict[FName, object] = field(default_factory=dict)
    defaults: dict[FName, Value] = field(default_factory=dict)

    default_parse_error: str | None = None
    location: SourceLocation | None = field(default=None, compare=False, repr=False, kw_only=True)


@dataclass
class ClassDeclaration:
    name: FName
    parent: ReferencePath | None

    is_interface: bool = False
    within: ReferencePath | None = None
    modifiers: tuple[ClassModifier, ...] = ()

    constants: list[ConstantDeclaration] = field(default_factory=list)
    enums: list[EnumDeclaration] = field(default_factory=list)
    structs: list[StructDeclaration] = field(default_factory=list)
    variables: list[VariableDeclaration] = field(default_factory=list)
    functions: list[FunctionDeclaration] = field(default_factory=list)
    operators: list[OperatorDeclaration] = field(default_factory=list)

    default_tokens: tuple[Token, ...] | None = None
    parsed_defaults: dict[FName, object] = field(default_factory=dict)
    defaults: dict[FName, Value] = field(default_factory=dict)

    default_parse_error: str | None = None
    location: SourceLocation | None = field(default=None, compare=False, repr=False, kw_only=True)
