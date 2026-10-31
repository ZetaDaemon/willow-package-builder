from willow_package_builder.compiler.syntax.declarations import TypeReference, VariableDeclaration
from willow_package_builder.compiler.syntax.lexer import Token, TokenCategory
from willow_package_builder.logging import CompilationError

from .token_parser import TokenParser

PARAMETERIZED_TYPES = frozenset({"array", "class", "delegate"})
VARIABLE_MODIFIERS = frozenset(
    {
        "native",
        "const",
        "transient",
        "private",
        "protected",
        "public",
        "config",
        "globalconfig",
        "localized",
        "editconst",
        "editinline",
        "export",
        "noexport",
        "duplicatetransient",
    }
)


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

    def parse_type(self) -> TypeReference:
        name = self.parse_qualified_name()
        arguments: list[TypeReference] = []

        if name.casefold() in PARAMETERIZED_TYPES and self.match("<"):
            while True:
                arguments.append(self.parse_type())

                if not self.match(","):
                    break

            self.expect_type_close()

        return TypeReference(name, tuple(arguments))

    def parse_variable_declaration(self, *, is_local: bool = False) -> list[VariableDeclaration]:
        """Parse out a variable declaration.

        Multiple variables can be defined at once, this only parses out a single line declaration.

        local int Temporary; -> one variable
        var int First, Second; -> two variables
        """
        self.expect("local" if is_local else "var")

        category_tokens = None
        modifiers: list[str] = []

        if not is_local:
            if self.peek().text == "(":
                category_tokens = self.parse_parenthesized_tokens()

            while self.peek().text.casefold() in VARIABLE_MODIFIERS:
                modifiers.append(self.advance().text.casefold())

        type_ref = self.parse_type()

        variables: list[VariableDeclaration] = []

        while True:
            name = self.expect_identifier().text
            array_dimension = 1

            if self.match("["):
                size = self.peek()

                if size.category is not TokenCategory.INTEGER:
                    msg = f"Expected array dimension at {size.line}:{size.column}"
                    raise CompilationError(msg)

                self.advance()
                base = 16 if size.text.lower().startswith("0x") else 10
                array_dimension = int(size.text, base)

                if array_dimension < 1:
                    msg = "Array dimension must be positive"
                    raise CompilationError(msg)

                self.expect("]")

            variables.append(
                VariableDeclaration(
                    name, type_ref, array_dimension, tuple(modifiers), category_tokens
                )
            )

            if not self.match(","):
                break

        self.expect(";")
        return variables
