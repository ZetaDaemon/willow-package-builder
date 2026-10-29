from typing import TYPE_CHECKING, Self

from willow_package_builder.compiler.expressions import (
    BinaryExpression,
    Expression,
    IdentifierExpression,
    IntegerExpression,
)
from willow_package_builder.compiler.lexer import Token, TokenType
from willow_package_builder.compiler.statements import (
    AssignmentStatement,
    BreakStatement,
    ContinueStatement,
    EmptyStatement,
    ExpressionStatement,
    FunctionBody,
    IfStatement,
    ReturnStatement,
    Statement,
    WhileStatement,
)
from willow_package_builder.logging import CompilationError

from .declaration_syntax_parser import DeclarationSyntaxParser

if TYPE_CHECKING:
    from willow_package_builder.compiler.declarations import (
        FunctionDeclaration,
        VariableDeclaration,
    )
    from willow_package_builder.compiler.expression_resolver import ExpressionResolver


class FunctionParser(DeclarationSyntaxParser):
    expression_resolver: ExpressionResolver | None

    def __init__(
        self, tokens: list[Token], *, expression_resolver: ExpressionResolver | None = None
    ) -> None:
        super().__init__(tokens)
        self.expression_resolver = expression_resolver

    def parse_primary_expression(self) -> Expression:
        token = self.peek()

        if token.type is TokenType.INTEGER:
            self.advance()
            base = 16 if token.text.lower().startswith("0x") else 10
            return IntegerExpression(value=int(token.text, base))

        if token.type is TokenType.IDENTIFIER:
            self.advance()
            return IdentifierExpression(name=token.text)

        if self.match("("):
            expression = self.parse_expression()
            self.expect(")")
            return expression

        msg = f"Expected expression, got {token.text!r} at {token.line}:{token.column}"
        raise CompilationError(msg)

    def parse_expression(self, maximum_precedence: int | None = None) -> Expression:
        resolver = self.expression_resolver

        if resolver is None:
            msg = "Expression parsing requires an expression resolver"
            raise ValueError(msg)

        left = self.parse_primary_expression()

        while True:
            token = self.peek()

            if token.type not in (TokenType.SYMBOL, TokenType.IDENTIFIER):
                break

            precedence = resolver.binary_precedence(token.text, resolver.type_of(left))

            if precedence is None:
                break

            if maximum_precedence is not None and precedence > maximum_precedence:
                break

            self.advance()
            right = self.parse_expression(maximum_precedence=precedence - 1)

            expression = BinaryExpression(left=left, operator=token.text, right=right)

            # Verify that these two operand types have an exact overload.
            resolver.resolve_operator(expression)
            left = expression

        return left

    def parse_local_declarations(self) -> list[VariableDeclaration]:
        declarations: list[VariableDeclaration] = []

        while self.peek().text.casefold() == "local":
            declarations.extend(self.parse_variable_declaration(is_local=True))

        return declarations

    def parse_statement_branch(self) -> list[Statement]:
        if not self.match("{"):
            return [self.parse_statement()]

        statements: list[Statement] = []

        while not self.match("}"):
            token = self.peek()

            if token.type is TokenType.EOF:
                msg = f"Unterminated statement block at {token.line}:{token.column}"
                raise CompilationError(msg)

            statements.append(self.parse_statement())

        return statements

    def parse_if_statement(self) -> IfStatement:
        self.expect("if")
        self.expect("(")
        condition = self.parse_expression()
        self.expect(")")

        then_statements = self.parse_statement_branch()

        else_statements = None
        if self.match("else"):
            else_statements = self.parse_statement_branch()

        return IfStatement(condition, then_statements, else_statements)

    def parse_while_statement(self) -> WhileStatement:
        self.expect("while")
        self.expect("(")
        condition = self.parse_expression()
        self.expect(")")

        statements = self.parse_statement_branch()
        return WhileStatement(condition, statements)

    def parse_statement(self) -> Statement:
        if self.match(";"):
            return EmptyStatement()

        if self.match("return"):
            if self.match(";"):
                return ReturnStatement()

            value = self.parse_expression()
            self.expect(";")
            return ReturnStatement(value=value)

        token = self.peek()

        if token.text.casefold() == "local":
            msg = (
                "Local declarations must precede executable statements "
                f"at {token.line}:{token.column}"
            )
            raise CompilationError(msg)

        if token.text.casefold() == "if":
            return self.parse_if_statement()

        if token.text.casefold() == "while":
            return self.parse_while_statement()

        if self.match("break"):
            self.expect(";")
            return BreakStatement()

        if self.match("continue"):
            self.expect(";")
            return ContinueStatement()

        expression = self.parse_expression()

        if self.match("="):
            value = self.parse_expression()
            self.expect(";")

            return AssignmentStatement(target=expression, value=value)

        self.expect(";")
        return ExpressionStatement(expression=expression)

    def parse_function_body(self) -> FunctionBody:
        resolver = self.expression_resolver

        if resolver is None:
            msg = "Function-body parsing requires an expression resolver"
            raise ValueError(msg)

        locals_ = self.parse_local_declarations()

        for declaration in locals_:
            resolver.scope.add_local(declaration)

        statements: list[Statement] = []

        while self.peek().type is not TokenType.EOF:
            statements.append(self.parse_statement())

        return FunctionBody(locals=locals_, statements=statements)

    @classmethod
    def from_function_body(
        cls, function: FunctionDeclaration, *, expression_resolver: ExpressionResolver | None = None
    ) -> Self:
        if function.body_tokens is None:
            msg = f"Function {function.name!r} has no captured body tokens"
            raise CompilationError(msg)

        tokens = list(function.body_tokens)

        line = 1
        column = 1

        if tokens:
            last = tokens[-1]
            line = last.line
            column = last.column + len(last.text)

        tokens.append(Token(type=TokenType.EOF, text="", line=line, column=column))

        # Local declarations don't require expression precedence.
        return cls(tokens, expression_resolver=expression_resolver)
