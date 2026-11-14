import string
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Self, cast

from willow_package_builder.compiler.syntax.declarations import DefaultObjectDeclaration
from willow_package_builder.compiler.syntax.keyword import KeywordEnum, ScriptKeywords
from willow_package_builder.compiler.syntax.lexer import Token, TokenCategory
from willow_package_builder.compiler.syntax.parser.token_parser import TokenParser
from willow_package_builder.compiler.syntax.punctuation import Operator, Punctuation
from willow_package_builder.logging import CompilationError, SourceLocation
from willow_package_builder.upackage import FName, ReferencePath

BYTE_LENGTH = 2


class ArrayDefaultOperationCategory(Enum):
    SET_INDEX = auto()
    ADD = auto()
    REMOVE = auto()
    REMOVE_INDEX = auto()
    REPLACE = auto()
    EMPTY = auto()


@dataclass
class DefaultOperation:
    name: FName
    value: object


@dataclass
class ArrayDefaultOperation:
    category: ArrayDefaultOperationCategory
    values: tuple[object, ...] = ()
    index: int | None = None
    location: SourceLocation | None = None


@dataclass
class ArrayDefaults:
    initial: object = None
    has_initial: bool = field(default=False, kw_only=True)
    updates: list[ArrayDefaultOperation] = field(default_factory=list)


class DefaultObjectAttribute(KeywordEnum):
    """Attributes accepted on a Begin Object declaration."""

    CLASS = "class"
    NAME = "name"


class DefaultArrayMethod(KeywordEnum):
    ADD = "add"
    REMOVE = "remove"
    REMOVE_INDEX = "removeindex"
    REPLACE = "replace"
    EMPTY = "empty"


class DefaultsParser(TokenParser):
    """Parse default property blocks into untyped Python data."""

    def __init__(self, tokens: list[Token]) -> None:
        super().__init__(tokens)
        self.default_objects: list[DefaultObjectDeclaration] = []

    def _merge_value(self, previous: object, supplied: object) -> object:
        match previous, supplied:
            case dict(), dict():
                fields = cast("dict[FName, object]", previous).copy()
                for name, value in cast("dict[FName, object]", supplied).items():
                    self._apply_operation(fields, DefaultOperation(name, value))
                return fields

            case dict(), ():
                return previous.copy()

            case list(), ():
                return []

            case _:
                return supplied

    def _apply_operation(self, values: dict[FName, object], operation: DefaultOperation) -> None:
        key = next((name for name in values if name == operation.name), operation.name)
        previous = values.get(key)
        update = operation.value

        if not isinstance(update, ArrayDefaultOperation):
            values[key] = self._merge_value(previous, update)
            return

        if isinstance(previous, ArrayDefaults):
            array = previous
        else:
            array = ArrayDefaults(initial=previous, has_initial=key in values)
            values[key] = array

        array.updates.append(update)

    def parse_operation(self) -> DefaultOperation:
        token = self.expect_identifier()
        location = SourceLocation(token.line, token.column)

        if self.match(Punctuation.DOT):
            return DefaultOperation(token.fname, self._parse_array_method(location))

        index = None
        if self.match(Punctuation.LEFT_PAREN):
            index = self.parse_integer()
            self.expect(Punctuation.RIGHT_PAREN)
        elif self.match(Punctuation.LEFT_BRACKET):
            index = self.parse_integer()
            self.expect(Punctuation.RIGHT_BRACKET)

        self.expect(Operator.EQUAL)
        value = self.parse_value()

        if index is not None:
            value = ArrayDefaultOperation(
                ArrayDefaultOperationCategory.SET_INDEX,
                values=(value,),
                index=index,
                location=location,
            )

        return DefaultOperation(token.fname, value)

    def _parse_array_method(self, location: SourceLocation) -> ArrayDefaultOperation:
        token = self.expect_identifier()
        if token not in DefaultArrayMethod:
            msg = f"Unknown default array method {token}"
            raise CompilationError(msg, location)

        method = DefaultArrayMethod(token)
        category = ArrayDefaultOperationCategory[method.name]

        if method is DefaultArrayMethod.EMPTY:
            if self.match(Punctuation.LEFT_PAREN):
                self.expect(Punctuation.RIGHT_PAREN)

            return ArrayDefaultOperation(category, location=location)

        self.expect(Punctuation.LEFT_PAREN)

        if method is DefaultArrayMethod.REMOVE_INDEX:
            index = self.parse_integer()
            self.expect(Punctuation.RIGHT_PAREN)
            return ArrayDefaultOperation(category, index=index, location=location)

        first = self.parse_value()
        values = (first,)

        if method is DefaultArrayMethod.REPLACE:
            self.expect(Punctuation.COMMA)
            values = (first, self.parse_value())

        self.expect(Punctuation.RIGHT_PAREN)
        return ArrayDefaultOperation(category, values=values, location=location)

    def _parse_struct_value(self) -> dict[FName, object]:
        self.expect(Punctuation.LEFT_PAREN)
        values: dict[FName, object] = {}

        if self.match(Punctuation.RIGHT_PAREN):
            return values

        while True:
            self._apply_operation(values, self.parse_operation())
            if self.match(Punctuation.RIGHT_PAREN):
                return values
            self.expect(Punctuation.COMMA)

    def parse_value(self) -> object:
        token = self.peek()
        location = SourceLocation(token.line, token.column)

        if self.match(Operator.SUBTRACT):
            number = self.peek()
            match number.category:
                case TokenCategory.INTEGER:
                    return -self.parse_integer()
                case TokenCategory.FLOAT:
                    self.advance()
                    return -float(str(number))
                case _:
                    msg = "Expected a numeric default after '-'"
                    raise CompilationError(msg, location)

        match token.category:
            case TokenCategory.INTEGER:
                return self.parse_integer()

            case TokenCategory.FLOAT:
                self.advance()
                return float(str(token))

            case TokenCategory.STRING:
                return self.parse_string_value()

            case TokenCategory.NAME:
                self.advance()
                value = str(token)[1:-1]
                if "\\" in value:
                    msg = f"Default literal escape decoding is not implemented at {location}"
                    raise NotImplementedError(msg)
                return value

            case TokenCategory.IDENTIFIER:
                match token:
                    case ScriptKeywords.TRUE:
                        self.advance()
                        return True
                    case ScriptKeywords.FALSE:
                        self.advance()
                        return False
                    case ScriptKeywords.NONE:
                        self.advance()
                        return None
                    case _:
                        name = self.parse_qualified_name()

                if self.peek().category is TokenCategory.NAME:
                    path_token = self.advance()
                    if "\\" in str(path_token):
                        msg = f"Default reference escape decoding is not implemented at {location}"
                        raise NotImplementedError(msg)
                    return f"{name}{path_token}"

                while self.match(Operator.COLON):
                    child = self.parse_qualified_name()
                    name = ReferencePath(str(child), name)

                return str(name)

            case TokenCategory.SYMBOL if token == Punctuation.LEFT_PAREN:
                return self._parse_parenthesized_value()

            case _:
                msg = f"Expected a default value, got {token}"
                raise CompilationError(msg, location)

    def _parse_object_name(self) -> FName:
        """Read an unqualified subobject name, allowing quoted spelling."""
        token = self.peek()
        location = SourceLocation(token.line, token.column)

        match token.category:
            case TokenCategory.IDENTIFIER:
                name = self.advance().fname
            case TokenCategory.STRING:
                name = FName(self.parse_string_value())
            case TokenCategory.NAME:
                self.advance()
                name = FName(str(token)[1:-1])
            case _:
                msg = f"Expected a default object name, got {token}"
                raise CompilationError(msg, location)

        text = str(name)

        if not text.strip() or any(separator in text for separator in (".", ":", "/", "\\")):
            msg = f"Default object name must be unqualified, got {text!r}"
            raise CompilationError(msg, location)

        return name

    def parse_object_declaration(
        self, *, include_properties: bool = True
    ) -> DefaultObjectDeclaration:
        """Parse a new or inherited subobject and its nested declarations."""
        opening = self.expect(ScriptKeywords.BEGIN)
        self.expect(ScriptKeywords.OBJECT)
        location = SourceLocation(opening.line, opening.column)
        name: FName | None = None
        class_name: ReferencePath | None = None

        while True:
            token = self.peek()

            if token == DefaultObjectAttribute.CLASS:
                if class_name is not None:
                    msg = "Duplicate Class attribute in default object declaration"
                    raise CompilationError(msg, SourceLocation(token.line, token.column))
                self.advance()
                self.expect(Operator.EQUAL)
                class_name = self.parse_qualified_name()
            elif token == DefaultObjectAttribute.NAME:
                if name is not None:
                    msg = "Duplicate Name attribute in default object declaration"
                    raise CompilationError(msg, SourceLocation(token.line, token.column))
                self.advance()
                self.expect(Operator.EQUAL)
                name = self._parse_object_name()
            else:
                break

        if name is None:
            msg = "Default object declaration requires Name"
            raise CompilationError(msg, location)

        declaration = DefaultObjectDeclaration(name, class_name, location=location)

        while True:
            token = self.peek()

            if token.category is TokenCategory.EOF:
                msg = f"Unterminated default object declaration for {name}"
                raise CompilationError(msg, location)

            if self.match(Punctuation.SEMICOLON):
                continue

            if token == ScriptKeywords.END and self.peek(1) == ScriptKeywords.OBJECT:
                self.advance()
                self.advance()
                return declaration

            if token == ScriptKeywords.BEGIN and self.peek(1) == ScriptKeywords.OBJECT:
                declaration.children.append(
                    self.parse_object_declaration(include_properties=include_properties)
                )
                continue

            if include_properties:
                self._apply_operation(declaration.properties, self.parse_operation())
            else:
                self.advance()

    def parse_defaults(self, *, include_object_properties: bool = False) -> dict[FName, object]:
        """Parse property assignments and retain separately declared subobjects."""
        values: dict[FName, object] = {}

        while self.peek().category is not TokenCategory.EOF:
            if self.match(Punctuation.SEMICOLON):
                continue

            if self.peek() == ScriptKeywords.BEGIN and self.peek(1) == ScriptKeywords.OBJECT:
                self.default_objects.append(
                    self.parse_object_declaration(include_properties=include_object_properties)
                )
                continue

            if (
                not include_object_properties
                and self.peek().category is TokenCategory.IDENTIFIER
                and self.peek(1) == Operator.EQUAL
                and self.peek(2).line > self.peek(1).line
                and self.peek(2).category is TokenCategory.IDENTIFIER
                and self.peek(3) == Operator.EQUAL
            ):
                self.advance()  # Property name.
                self.advance()  # Equals sign.
                continue

            self._apply_operation(values, self.parse_operation())

        return values

    @classmethod
    def from_default_tokens(cls, tokens: tuple[Token, ...]) -> Self:
        line = 1
        column = 1
        if tokens:
            last = tokens[-1]
            line = last.line
            column = last.column + len(last)
        eof = Token(TokenCategory.EOF, "", line, column)
        return cls([*tokens, eof])

    def _parse_parenthesized_value(self) -> object:
        if self.peek(1) == Punctuation.RIGHT_PAREN:
            self.expect(Punctuation.LEFT_PAREN)
            self.expect(Punctuation.RIGHT_PAREN)
            # The declared type will distinguish an empty struct from an array.
            return ()

        if self.peek(1).category is TokenCategory.IDENTIFIER:
            if self.peek(2) == Operator.EQUAL:
                return self._parse_struct_value()
            if (
                self.peek(2) in (Punctuation.LEFT_PAREN, Punctuation.LEFT_BRACKET)
                and self.peek(3).category is TokenCategory.INTEGER
                and self.peek(4)
                == (
                    Punctuation.RIGHT_PAREN
                    if self.peek(2) == Punctuation.LEFT_PAREN
                    else Punctuation.RIGHT_BRACKET
                )
                and self.peek(5) == Operator.EQUAL
            ):
                return self._parse_struct_value()
        return self._parse_array_value()

    def _parse_array_value(self) -> list[object]:
        self.expect(Punctuation.LEFT_PAREN)
        elements: list[object] = []
        while True:
            elements.append(self.parse_value())
            if self.match(Punctuation.RIGHT_PAREN):
                return elements
            self.expect(Punctuation.COMMA)

    def parse_string_value(self) -> str:
        token = self.advance()
        value = str(token)[1:-1]
        result: list[str] = []
        index = 0

        while index < len(value):
            character = value[index]

            if character != "\\":
                result.append(character)
                index += 1
                continue

            location = SourceLocation(token.line, token.column + index + 1)
            index += 1

            if index == len(value):
                msg = "Unterminated default string escape"
                raise CompilationError(msg, location)

            escaped = value[index]

            match escaped:
                case "n":
                    result.append("\n")

                case "r":
                    result.append("\r")

                case "\\" | '"':
                    result.append(escaped)

                case _:
                    digits = value[index : index + 2]

                    if len(digits) != BYTE_LENGTH or any(c not in string.hexdigits for c in digits):
                        msg = (
                            f"Default string escape decoding for {escaped!r} "
                            f"is not implemented at {location}"
                        )
                        raise NotImplementedError(msg)

                    result.append(chr(int(digits, 16)))
                    index += 1

            index += 1

        return "".join(result)
