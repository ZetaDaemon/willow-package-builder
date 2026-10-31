from dataclasses import dataclass
from enum import Enum, auto

from willow_package_builder.logging import CompilationError


class TokenCategory(Enum):
    IDENTIFIER = auto()
    INTEGER = auto()
    FLOAT = auto()
    STRING = auto()
    NAME = auto()
    SYMBOL = auto()
    EOF = auto()


@dataclass(frozen=True)
class Token:
    category: TokenCategory
    text: str
    line: int
    column: int


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


class Lexer:
    source: str
    position: int = 0
    line: int = 1
    column: int = 1

    def __init__(self, source: str) -> None:
        self.source = source

    def peek(self, offset: int = 0) -> str:
        position = self.position + offset

        if position >= len(self.source):
            return ""

        return self.source[position]

    def advance(self) -> str:
        character = self.peek()

        if not character:
            return ""

        self.position += 1

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
                self.advance()
                continue

            # Line comment.
            if character == "/" and self.peek(1) == "/":
                self.advance()
                self.advance()

                while self.peek() and self.peek() != "\n":
                    self.advance()

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
            self.advance()

            while self.peek() and (self.peek().isalnum() or self.peek() == "_"):
                self.advance()

            return Token(TokenCategory.IDENTIFIER, self.source[start : self.position], line, column)

        if character.isdigit() or (character == "." and self.peek(1).isdigit()):
            return self.read_number()

        if character in PUNCTUATION:
            self.advance()
            return Token(TokenCategory.SYMBOL, character, line, column)

        if character in ('"', "'"):
            return self.read_quoted()

        for operator in OPERATORS:
            if self.source.startswith(operator, self.position):
                for _ in operator:
                    self.advance()

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
