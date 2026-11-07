import string
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self, cast

from willow_package_builder.compiler.syntax.keyword import ScriptKeywords
from willow_package_builder.compiler.syntax.lexer import Token, TokenCategory
from willow_package_builder.compiler.syntax.parser.token_parser import TokenParser
from willow_package_builder.compiler.syntax.punctuation import Operator, Punctuation
from willow_package_builder.logging import CompilationError, SourceLocation
from willow_package_builder.upackage import ReferencePath

if TYPE_CHECKING:
    from willow_package_builder.upackage import FName

BYTE_LENGTH = 2


@dataclass
class DefaultOperation:
    name: FName
    value: object
    array_index: int | None = None
    location: SourceLocation | None = None


@dataclass
class IndexedArrayDefaults:
    initial: object = None
    has_initial: bool = field(default=False, kw_only=True)
    updates: list[tuple[int, object]] = field(default_factory=list)


class DefaultsParser(TokenParser):
    """Parse default property blocks into untyped Python data."""

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

        if operation.array_index is None:
            values[key] = self._merge_value(values.get(key), operation.value)
            return

        previous = values.get(key)

        if isinstance(previous, IndexedArrayDefaults):
            indexed = previous
        else:
            indexed = IndexedArrayDefaults(initial=previous, has_initial=key in values)

        indexed.updates.append((operation.array_index, operation.value))
        values[key] = indexed

    def parse_operation(self) -> DefaultOperation:
        token = self.expect_identifier()
        location = SourceLocation(token.line, token.column)
        array_index = None

        if self.match(Punctuation.LEFT_PAREN):
            array_index = self.parse_integer()
            self.expect(Punctuation.RIGHT_PAREN)
        elif self.match(Punctuation.LEFT_BRACKET):
            array_index = self.parse_integer()
            self.expect(Punctuation.RIGHT_BRACKET)

        self.expect(Operator.EQUAL)

        return DefaultOperation(token.fname, self.parse_value(), array_index, location)

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

    def parse_defaults(self, *, skip_object_definitions: bool = False) -> dict[FName, object]:
        values: dict[FName, object] = {}

        while self.peek().category is not TokenCategory.EOF:
            if self.peek() == ScriptKeywords.BEGIN and self.peek(1) == ScriptKeywords.OBJECT:
                if not skip_object_definitions:
                    token = self.peek()
                    msg = (
                        "Default object definitions are not implemented "
                        f"at {token.line}:{token.column}"
                    )
                    raise NotImplementedError(msg)

                self.skip_object_definition()
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

    def skip_object_definition(self) -> None:
        opening = self.peek()
        self.expect(ScriptKeywords.BEGIN)
        self.expect(ScriptKeywords.OBJECT)
        depth = 1

        while depth:
            token = self.peek()

            if token.category is TokenCategory.EOF:
                msg = "Unterminated default object definition"
                raise CompilationError(msg, SourceLocation(opening.line, opening.column))

            if (
                token.category is TokenCategory.IDENTIFIER
                and self.peek(1) == ScriptKeywords.OBJECT
                and token in (ScriptKeywords.BEGIN, ScriptKeywords.END)
            ):
                self.advance()
                self.advance()
                depth += 1 if token == ScriptKeywords.BEGIN else -1
                continue

            self.advance()

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
