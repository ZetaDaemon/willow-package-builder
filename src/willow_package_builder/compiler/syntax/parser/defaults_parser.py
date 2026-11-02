from typing import Self

from willow_package_builder.compiler.syntax.defaults import (
    ArrayDefaultValue,
    DefaultAssignment,
    DefaultValue,
    EmptyDefaultValue,
    IdentifierDefaultValue,
    LiteralDefaultValue,
    NameDefaultValue,
    ObjectDefaultValue,
    StructDefaultValue,
)
from willow_package_builder.compiler.syntax.lexer import Token, TokenCategory
from willow_package_builder.logging import CompilationError, SourceLocation

from .token_parser import TokenParser


class DefaultsParser(TokenParser):
    """Parse class and struct default property blocks."""

    def _parse_struct_value(self) -> StructDefaultValue:
        self.expect("(")
        fields: list[DefaultAssignment] = []

        if self.match(")"):
            return StructDefaultValue(fields)

        while True:
            fields.append(self.parse_assignment())

            if self.match(")"):
                return StructDefaultValue(fields)

            self.expect(",")

    def parse_value(self) -> DefaultValue:
        token = self.peek()
        location = SourceLocation(token.line, token.column)

        if self.match("-"):
            number = self.peek()

            match number.category:
                case TokenCategory.INTEGER:
                    return LiteralDefaultValue(-self.parse_integer())

                case TokenCategory.FLOAT:
                    self.advance()
                    return LiteralDefaultValue(-float(number.text))

                case _:
                    msg = "Expected a numeric default after '-'"
                    raise CompilationError(msg, location)

        match token.category:
            case TokenCategory.INTEGER:
                return LiteralDefaultValue(self.parse_integer())

            case TokenCategory.FLOAT:
                self.advance()
                return LiteralDefaultValue(float(token.text))

            case TokenCategory.STRING:
                self.advance()
                value = token.text[1:-1]

                if "\\" in value:
                    msg = f"Default string escape decoding is not implemented at {location}"
                    raise NotImplementedError(msg)

                return LiteralDefaultValue(value)

            case TokenCategory.IDENTIFIER:
                match token.text.casefold():
                    case "true":
                        self.advance()
                        return LiteralDefaultValue(True)  # noqa: FBT003

                    case "false":
                        self.advance()
                        return LiteralDefaultValue(False)  # noqa: FBT003

                    case "none":
                        self.advance()
                        return LiteralDefaultValue(None)

                    case _:
                        name = self.parse_qualified_name()

                if self.peek().category is TokenCategory.NAME:
                    path_token = self.advance()
                    path = path_token.text[1:-1]

                    if "\\" in path:
                        msg = (
                            "Default object reference escape decoding "
                            f"is not implemented at {location}"
                        )
                        raise NotImplementedError(msg)

                    return ObjectDefaultValue(name, path)

                return IdentifierDefaultValue(name)

            case TokenCategory.NAME:
                self.advance()
                value = token.text[1:-1]

                if "\\" in value:
                    msg = f"Default name escape decoding is not implemented at {location}"
                    raise NotImplementedError(msg)

                return NameDefaultValue(value)

            case TokenCategory.SYMBOL if token.text == "(":
                return self._parse_parenthesized_value()

            case _:
                msg = f"Expected a default value, got {token.text!r}"
                raise CompilationError(msg, location)

    def parse_assignment(self) -> DefaultAssignment:
        token = self.expect_identifier()
        location = SourceLocation(token.line, token.column)
        array_index = None

        if self.match("("):
            array_index = self.parse_integer()
            self.expect(")")

        self.expect("=")
        value = self.parse_value()

        return DefaultAssignment(token.text, value, location, array_index)

    def parse_defaults(self) -> list[DefaultAssignment]:
        assignments: list[DefaultAssignment] = []

        while self.peek().category is not TokenCategory.EOF:
            assignments.append(self.parse_assignment())

        return assignments

    @classmethod
    def from_default_tokens(cls, tokens: tuple[Token, ...]) -> Self:
        """Construct a parser for a captured default property block."""
        line = 1
        column = 1

        if tokens:
            last = tokens[-1]
            line = last.line
            column = last.column + len(last.text)

        eof = Token(TokenCategory.EOF, "", line, column)
        return cls([*tokens, eof])

    def _parse_parenthesized_value(self) -> DefaultValue:
        if self.peek(1).text == ")":
            self.expect("(")
            self.expect(")")
            return EmptyDefaultValue()

        # Struct fields begin with Name= or Name(Index)=.
        if self.peek(1).category is TokenCategory.IDENTIFIER:
            if self.peek(2).text == "=":
                return self._parse_struct_value()

            if (
                self.peek(2).text == "("
                and self.peek(3).category is TokenCategory.INTEGER
                and self.peek(4).text == ")"
                and self.peek(5).text == "="
            ):
                return self._parse_struct_value()

        return self._parse_array_value()

    def _parse_array_value(self) -> ArrayDefaultValue:
        self.expect("(")
        elements: list[DefaultValue] = []

        while True:
            elements.append(self.parse_value())

            if self.match(")"):
                return ArrayDefaultValue(elements)

            self.expect(",")
