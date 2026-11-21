from dataclasses import dataclass
from enum import Enum, auto
from functools import cached_property
from typing import override

from willow_package_builder.compiler.syntax.keyword import Keyword
from willow_package_builder.compiler.syntax.punctuation import Operator, Punctuation
from willow_package_builder.logging import CompilationError
from willow_package_builder.upackage import FName


class TokenCategory(Enum):
    IDENTIFIER = auto()
    INTEGER = auto()
    FLOAT = auto()
    STRING = auto()
    NAME = auto()
    SYMBOL = auto()
    EOF = auto()


@dataclass(frozen=True, eq=False)
class Token:
    category: TokenCategory
    _text: str
    line: int
    column: int

    @override
    def __str__(self) -> str:
        return self._text

    @override
    def __eq__(self, other: object) -> bool:
        match other:
            case Keyword():
                return self.category is TokenCategory.IDENTIFIER and self.keyword == other

            case Punctuation() | Operator():
                return self.category is TokenCategory.SYMBOL and self._text == other.value

            case Token():
                return (
                    self.category == other.category
                    and self._text == other._text
                    and self.line == other.line
                    and self.column == other.column
                )

            case _:
                return NotImplemented

    def __len__(self) -> int:  # noqa: D105
        return len(self._text)

    def __float__(self) -> float:  # noqa: D105
        return float(self._text)

    def __int__(self) -> int:  # noqa: D105
        base = 16 if self._text.startswith(("0x", "0X")) else 10
        return int(self._text, base)

    @cached_property
    def keyword(self) -> Keyword | None:
        """Interpret an identifier as a keyword."""
        if self.category is not TokenCategory.IDENTIFIER:
            return None
        return Keyword(self._text)

    @property
    def fname(self) -> FName:
        """Interpret an identifier as an Unreal name."""
        if self.category is not TokenCategory.IDENTIFIER:
            msg = f"Expected an identifier, got {self} at {self.line}:{self.column}"
            raise CompilationError(msg)

        return FName(self._text)

    @property
    def operator_name(self) -> Operator | Keyword | None:
        """Interpret a recognized symbol or identifier as an operator name."""
        if self.category is TokenCategory.IDENTIFIER:
            return self.keyword

        if self.category is TokenCategory.SYMBOL:
            for operator in Operator:
                if self == operator:
                    return operator

        return None


PUNCTUATION = frozenset("{}()[];,.")
OPERATORS = tuple(
    sorted(
        {
            "+",
            "-",
            "*",
            "/",
            "%",
            "**",
            "++",
            "--",
            "=",
            "+=",
            "-=",
            "*=",
            "/=",
            "%=",
            "==",
            "!=",
            "~=",
            "<",
            ">",
            "<=",
            ">=",
            "!",
            "&&",
            "||",
            "^^",
            "~",
            "&",
            "|",
            "^",
            "&=",
            "|=",
            "^=",
            "<<",
            ">>",
            ">>>",
            "<<=",
            ">>=",
            ">>>=",
            "$",
            "@",
            "$=",
            "@=",
            "?",
            ":",
        },
        key=len,
        reverse=True,
    )
)
OPERATORS_BY_FIRST: dict[str, tuple[str, ...]] = {
    character: tuple(operator for operator in OPERATORS if operator[0] == character)
    for character in {operator[0] for operator in OPERATORS}
}


class Lexer:
    source: str
    _source_length: int
    position: int = 0
    line: int = 1
    column: int = 1

    def __init__(self, source: str) -> None:
        self.source = source
        self._source_length = len(source)

    def peek(self, offset: int = 0) -> str:
        position = self.position + offset

        if position >= self._source_length:
            return ""

        return self.source[position]

    def advance(self) -> str:
        position = self.position
        if position >= self._source_length:
            return ""

        character = self.source[position]
        self.position = position + 1

        if character == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1

        return character

    def skip_trivia(self) -> None:
        """Skip whitespace and comments."""
        while True:
            character = self.peek()

            if character and character.isspace():
                source = self.source
                source_length = self._source_length
                start = self.position
                position = start + 1

                while position < source_length and source[position].isspace():
                    position += 1

                whitespace = source[start:position]
                newline_count = whitespace.count("\n")

                if newline_count:
                    self.line += newline_count
                    self.column = len(whitespace) - whitespace.rfind("\n")
                else:
                    self.column += position - start

                self.position = position
                continue

            # Line comment.
            if character == "/" and self.peek(1) == "/":
                start = self.position
                end = self.source.find("\n", start + 2)

                if end == -1:
                    end = self._source_length

                self.position = end
                self.column += end - start
                continue

            # Block comment, including nested block comments.
            if character == "/" and self.peek(1) == "*":
                line = self.line
                column = self.column

                self.advance()
                self.advance()
                depth = 1

                while depth:
                    if not self.peek():
                        msg = f"Unterminated block comment at {line}:{column}"
                        raise CompilationError(msg)

                    if self.peek() == "/" and self.peek(1) == "*":
                        self.advance()
                        self.advance()
                        depth += 1
                    elif self.peek() == "*" and self.peek(1) == "/":
                        self.advance()
                        self.advance()
                        depth -= 1
                    else:
                        self.advance()

                continue

            return

    def read_number(self) -> Token:
        start = self.position
        line = self.line
        column = self.column

        # Hexadecimal integer.
        if self.peek() == "0" and self.peek(1) in ("x", "X"):
            self.advance()
            self.advance()
            digits_start = self.position

            while self.peek() and self.peek() in "0123456789abcdefABCDEF":
                self.advance()

            if self.position == digits_start:
                msg = f"Expected hexadecimal digits at {line}:{column}"
                raise CompilationError(msg)

            return Token(TokenCategory.INTEGER, self.source[start : self.position], line, column)

        while self.peek() and self.peek().isdigit():
            self.advance()

        category = TokenCategory.INTEGER

        # Fractional portion.
        if self.peek() == ".":
            category = TokenCategory.FLOAT
            self.advance()

            while self.peek() and self.peek().isdigit():
                self.advance()

        # Scientific notation.
        if self.peek() in ("e", "E"):
            category = TokenCategory.FLOAT
            self.advance()

            if self.peek() in ("+", "-"):
                self.advance()

            digits_start = self.position

            while self.peek() and self.peek().isdigit():
                self.advance()

            if self.position == digits_start:
                msg = f"Expected exponent digits at {line}:{column}"
                raise CompilationError(msg)

        return Token(category, self.source[start : self.position], line, column)

    def read_quoted(self) -> Token:
        start = self.position
        line = self.line
        column = self.column
        quote = self.advance()

        category = TokenCategory.STRING if quote == '"' else TokenCategory.NAME

        while True:
            character = self.peek()

            if not character or character in ("\r", "\n"):
                msg = f"Unterminated quoted literal at {line}:{column}"
                raise CompilationError(msg)

            self.advance()

            if character == quote:
                break

            if character == "\\":
                escaped = self.peek()

                if not escaped or escaped in ("\r", "\n"):
                    msg = f"Unterminated escape sequence at {line}:{column}"
                    raise CompilationError(msg)

                self.advance()

        return Token(category, self.source[start : self.position], line, column)

    def next_token(self) -> Token:
        self.skip_trivia()

        start = self.position
        line = self.line
        column = self.column
        character = self.peek()

        if not character:
            return Token(TokenCategory.EOF, "", line, column)

        if character.isalpha() or character == "_":
            source = self.source
            source_length = self._source_length
            position = start + 1

            while position < source_length:
                character = source[position]
                if not (character.isalnum() or character == "_"):
                    break
                position += 1

            self.position = position
            self.column += position - start

            return Token(TokenCategory.IDENTIFIER, source[start:position], line, column)

        if character.isdigit() or (character == "." and self.peek(1).isdigit()):
            return self.read_number()

        if character in PUNCTUATION:
            self.advance()
            return Token(TokenCategory.SYMBOL, character, line, column)

        if character in ('"', "'"):
            return self.read_quoted()

        for operator in OPERATORS_BY_FIRST.get(character, ()):
            if self.source.startswith(operator, start):
                length = len(operator)
                self.position = start + length
                self.column += length

                return Token(TokenCategory.SYMBOL, operator, line, column)

        msg = f"Unexpected character {character!r} at {line}:{column}"
        raise CompilationError(msg)

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []

        while True:
            token = self.next_token()
            tokens.append(token)

            if token.category is TokenCategory.EOF:
                return tokens
