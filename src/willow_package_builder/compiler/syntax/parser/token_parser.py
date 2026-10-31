from willow_package_builder.compiler.syntax.lexer import Token, TokenCategory
from willow_package_builder.logging import CompilationError


class TokenParser:
    tokens: list[Token]
    position: int = 0

    def __init__(self, tokens: list[Token]) -> None:
        if not tokens or tokens[-1].category is not TokenCategory.EOF:
            msg = "Token stream must end with EOF"
            raise ValueError(msg)

        self.tokens = list(tokens)
        self.position = 0

    def peek(self, offset: int = 0) -> Token:
        index = min(self.position + offset, len(self.tokens) - 1)
        return self.tokens[index]

    def advance(self) -> Token:
        token = self.peek()

        if token.category is not TokenCategory.EOF:
            self.position += 1

        return token

    def match(self, text: str) -> bool:
        token = self.peek()

        if token.category is TokenCategory.EOF:
            return False

        if token.text.casefold() != text.casefold():
            return False

        self.advance()
        return True

    def expect(self, text: str) -> Token:
        token = self.peek()

        if not self.match(text):
            msg = f"Expected {text!r}, got {token.text!r} at {token.line}:{token.column}"
            raise CompilationError(msg)

        return token

    def expect_identifier(self) -> Token:
        token = self.peek()

        if token.category is not TokenCategory.IDENTIFIER:
            msg = f"Expected identifier, got {token.text!r} at {token.line}:{token.column}"
            raise CompilationError(msg)

        return self.advance()

    def parse_qualified_name(self) -> str:
        parts = [self.expect_identifier().text]

        while self.match("."):
            parts.append(self.expect_identifier().text)

        return ".".join(parts)

    def parse_integer(self) -> int:
        token = self.peek()

        if token.category is not TokenCategory.INTEGER:
            msg = f"Expected integer at {token.line}:{token.column}"
            raise CompilationError(msg)

        self.advance()
        base = 16 if token.text.lower().startswith("0x") else 10
        return int(token.text, base)

    def parse_parenthesized_tokens(self) -> tuple[Token, ...]:
        opening = self.expect("(")
        tokens: list[Token] = []
        depth = 1

        while depth:
            token = self.advance()

            if token.category is TokenCategory.EOF:
                msg = f"Unterminated parentheses opened at {opening.line}:{opening.column}"
                raise CompilationError(msg)

            if token.category is TokenCategory.SYMBOL:
                if token.text == "(":
                    depth += 1
                elif token.text == ")":
                    depth -= 1

            if depth:
                tokens.append(token)

        return tuple(tokens)

    def parse_braced_tokens(self) -> tuple[Token, ...]:
        opening = self.expect("{")
        tokens: list[Token] = []
        depth = 1

        while depth:
            token = self.advance()

            if token.category is TokenCategory.EOF:
                msg = f"Unterminated block opened at {opening.line}:{opening.column}"
                raise CompilationError(msg)

            if token.category is TokenCategory.SYMBOL:
                if token.text == "{":
                    depth += 1
                elif token.text == "}":
                    depth -= 1

            if depth:
                tokens.append(token)

        return tuple(tokens)
