from willow_package_builder.compiler.syntax.declarations import (
    MAX_FIXED_ARRAY_DIMENSION,
    TypeReference,
    VariableDeclaration,
)
from willow_package_builder.compiler.syntax.lexer import Token, TokenCategory
from willow_package_builder.compiler.syntax.modifiers import VariableModifier
from willow_package_builder.logging import CompilationError, SourceLocation

from .token_parser import TokenParser

PARAMETERIZED_TYPES = frozenset({"array", "class", "delegate"})


class DeclarationSyntaxParser(TokenParser):
    def expect_type_close(self) -> None:
        token = self.peek()

        if token.category is not TokenCategory.SYMBOL or token.text not in (">", ">>", ">>>"):
            msg = f"Expected '>', got {token.text!r} at {token.line}:{token.column}"
            raise CompilationError(msg)

        self.advance()

        # Consume one closing bracket and leave the others for outer types.
        if len(token.text) > 1:
            self.tokens.insert(
                self.position,
                Token(TokenCategory.SYMBOL, token.text[1:], token.line, token.column + 1),
            )

    def parse_type(self, *, allow_modifiers: bool = False) -> TypeReference:
        modifiers: list[VariableModifier] = []

        if allow_modifiers:
            while self.peek().text.casefold() in VariableModifier:
                modifiers.append(VariableModifier(self.advance().text.casefold()))

        name = self.parse_qualified_name()
        arguments: list[TypeReference] = []

        if name.casefold() == "map" and self.match("{"):
            arguments.append(self.parse_type())
            self.expect(",")
            arguments.append(self.parse_type())
            self.expect("}")

            return TypeReference(name, tuple(arguments), tuple(modifiers))

        if name.casefold() in PARAMETERIZED_TYPES and self.match("<"):
            while True:
                arguments.append(self.parse_type(allow_modifiers=True))

                if not self.match(","):
                    break

            self.expect_type_close()

        return TypeReference(name, tuple(arguments), tuple(modifiers))

    def parse_variable_declaration(self, *, is_local: bool = False) -> list[VariableDeclaration]:
        """Parse out a variable declaration.

        Multiple variables can be defined at once, this only parses out a single line declaration.

        local int Temporary; -> one variable
        var int First, Second; -> two variables
        """
        self.expect("local" if is_local else "var")

        category_tokens = None
        modifiers: list[VariableModifier] = []

        if not is_local:
            if self.peek().text == "(":
                category_tokens = self.parse_parenthesized_tokens()

            while self.peek().text.casefold() in VariableModifier:
                modifiers.append(VariableModifier(self.advance().text.casefold()))

        type_ref = self.parse_type()

        variables: list[VariableDeclaration] = []

        while True:
            name_token = self.expect_identifier()
            name = name_token.text
            array_dimension, array_dimension_name = self.parse_array_dimension()

            variables.append(
                VariableDeclaration(
                    name,
                    type_ref,
                    array_dimension,
                    tuple(modifiers),
                    category_tokens,
                    array_dimension_name,
                    location=SourceLocation(name_token.line, name_token.column),
                )
            )

            if not self.match(","):
                break

        self.expect(";")
        return variables

    def parse_array_dimension(self) -> tuple[int, str | None]:
        if not self.match("["):
            return 1, None

        token = self.peek()
        dimension = 1
        dimension_name = None

        if token.category is TokenCategory.INTEGER:
            self.advance()
            base = 16 if token.text.lower().startswith("0x") else 10
            dimension = int(token.text, base)

            if not 1 < dimension <= MAX_FIXED_ARRAY_DIMENSION:
                msg = f"Fixed array dimension must be between 2 and {MAX_FIXED_ARRAY_DIMENSION}"
                raise CompilationError(msg, SourceLocation(token.line, token.column))

        elif token.category is TokenCategory.IDENTIFIER:
            dimension_name = self.parse_qualified_name()

        else:
            msg = "Expected an integer or named array dimension"
            raise CompilationError(msg, SourceLocation(token.line, token.column))

        self.expect("]")
        return dimension, dimension_name
