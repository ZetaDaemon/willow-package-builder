from collections.abc import Sequence
from typing import TYPE_CHECKING, Self

from willow_package_builder.compiler.syntax.declarations import OperatorCategory
from willow_package_builder.compiler.syntax.expressions import (
    BinaryExpression,
    BooleanExpression,
    CallExpression,
    Expression,
    FloatExpression,
    IdentifierExpression,
    IntegerExpression,
    StringExpression,
    UnaryExpression,
)
from willow_package_builder.compiler.syntax.lexer import Token, TokenCategory
from willow_package_builder.compiler.syntax.statements import (
    AssignmentStatement,
    BreakStatement,
    ContinueStatement,
    DoUntilStatement,
    EmptyStatement,
    ExpressionStatement,
    ForStatement,
    FunctionBody,
    IfStatement,
    ReturnStatement,
    Statement,
    WhileStatement,
)
from willow_package_builder.logging import CompilationError
from willow_package_builder.source_location import SourceLocation

from .declaration_syntax_parser import DeclarationSyntaxParser

if TYPE_CHECKING:
    from willow_package_builder.compiler.semantics.expression_resolver import ExpressionResolver
    from willow_package_builder.compiler.syntax.declarations import (
        FunctionDeclaration,
        VariableDeclaration,
    )


class FunctionParser(DeclarationSyntaxParser):
    expression_resolver: ExpressionResolver | None

    def __init__(
        self, tokens: list[Token], expression_resolver: ExpressionResolver | None = None
    ) -> None:
        super().__init__(tokens)
        self.expression_resolver = expression_resolver

    @classmethod
    def from_tokens(
        cls, tokens: Sequence[Token], expression_resolver: ExpressionResolver | None = None
    ) -> Self:
        line = 1
        column = 1

        if tokens:
            last = tokens[-1]
            line = last.line
            column = last.column + len(last.text)

        eof = Token(TokenCategory.EOF, "", line, column)

        return cls([*tokens, eof], expression_resolver=expression_resolver)

    @classmethod
    def from_function_body(
        cls, function: FunctionDeclaration, expression_resolver: ExpressionResolver | None = None
    ) -> Self:
        if function.body_tokens is None:
            msg = f"Function {function.name!r} has no captured body tokens"
            raise ValueError(msg)

        return cls.from_tokens(function.body_tokens, expression_resolver)

    def parse_primary_expression(self) -> Expression:
        token = self.peek()

        match token.category:
            case TokenCategory.INTEGER:
                self.advance()
                base = 16 if token.text.lower().startswith("0x") else 10
                return IntegerExpression(int(token.text, base))

            case TokenCategory.IDENTIFIER:
                self.advance()
                keyword = token.text.casefold()

                if keyword in ("true", "false"):
                    return BooleanExpression(keyword == "true")

                return IdentifierExpression(token.text)

            case TokenCategory.FLOAT:
                self.advance()
                return FloatExpression(float(token.text))

            case TokenCategory.STRING:
                self.advance()
                value = token.text[1:-1]

                if "\\" in value:
                    msg = (
                        "String escape decoding is not implemented yet "
                        f"at {token.line}:{token.column}"
                    )
                    raise NotImplementedError(msg)

                return StringExpression(value)

            case _:
                pass

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

        left = self.parse_unary_expression()

        while True:
            token = self.peek()

            if token.category not in (TokenCategory.SYMBOL, TokenCategory.IDENTIFIER):
                break

            precedence = resolver.binary_precedence(token.text, resolver.type_of(left))

            if precedence is None:
                break

            if maximum_precedence is not None and precedence > maximum_precedence:
                break

            self.advance()
            right = self.parse_expression(precedence - 1)

            expression = BinaryExpression(left, token.text, right)

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

            if token.category is TokenCategory.EOF:
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

    def _parse_statement(self) -> Statement:
        if self.match(";"):
            return EmptyStatement()

        if self.match("return"):
            if self.match(";"):
                return ReturnStatement()

            value = self.parse_expression()
            self.expect(";")
            return ReturnStatement(value)

        token = self.peek()

        match token.text.casefold():
            case "local":
                msg = (
                    "Local declarations must precede executable statements "
                    f"at {token.line}:{token.column}"
                )
                raise CompilationError(msg)

            case "if":
                return self.parse_if_statement()

            case "while":
                return self.parse_while_statement()

            case "for":
                return self.parse_for_statement()

            case "do":
                return self.parse_do_until_statement()

            case _:
                pass

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

            return AssignmentStatement(expression, value)

        self.expect(";")
        return ExpressionStatement(expression)

    def parse_statement(self) -> Statement:
        token = self.peek()
        statement = self._parse_statement()
        statement.location = SourceLocation(token.line, token.column)
        return statement

    def parse_function_body(self) -> FunctionBody:
        resolver = self.expression_resolver

        if resolver is None:
            msg = "Function-body parsing requires an expression resolver"
            raise ValueError(msg)

        function_locals = self.parse_local_declarations()

        for declaration in function_locals:
            resolver.scope.add_local(declaration)

        statements: list[Statement] = []

        while self.peek().category is not TokenCategory.EOF:
            statements.append(self.parse_statement())

        return FunctionBody(function_locals, statements)

    def parse_for_clause(self) -> Statement:
        token = self.peek()
        location = SourceLocation(token.line, token.column)
        expression = self.parse_expression()

        if self.match("="):
            value = self.parse_expression()
            return AssignmentStatement(expression, value, location=location)

        return ExpressionStatement(expression, location=location)

    def parse_for_statement(self) -> ForStatement:
        self.expect("for")
        self.expect("(")

        initializer = self.parse_for_clause()
        self.expect(";")

        condition = self.parse_expression()
        self.expect(";")

        increment = self.parse_for_clause()
        self.expect(")")

        statements = self.parse_statement_branch()

        return ForStatement(initializer, condition, increment, statements)

    def parse_do_until_statement(self) -> DoUntilStatement:
        self.expect("do")
        statements = self.parse_statement_branch()

        self.expect("until")
        self.expect("(")
        condition = self.parse_expression()
        self.expect(")")
        self.expect(";")

        return DoUntilStatement(statements, condition)

    def parse_postfix_expression(self) -> Expression:
        resolver = self.expression_resolver

        if resolver is None:
            msg = "Postfix expression parsing requires an expression resolver"
            raise ValueError(msg)

        expression = self.parse_primary_expression()

        while True:
            if self.peek().text == "(":
                arguments = self.parse_call_arguments()
                expression = CallExpression(expression, arguments)
                continue

            if resolver.has_unary_operator(self.peek().text, OperatorCategory.POSTFIX):
                token = self.advance()
                expression = UnaryExpression(token.text, expression, OperatorCategory.POSTFIX)
                resolver.resolve_unary_operator(expression)
                continue

            return expression

    def parse_unary_expression(self) -> Expression:
        resolver = self.expression_resolver

        if resolver is None:
            msg = "Unary expression parsing requires an expression resolver"
            raise ValueError(msg)

        token = self.peek()

        if resolver.has_unary_operator(token.text, OperatorCategory.PREFIX):
            self.advance()
            operand = self.parse_unary_expression()

            expression = UnaryExpression(token.text, operand, OperatorCategory.PREFIX)
            resolver.resolve_unary_operator(expression)
            return expression

        return self.parse_postfix_expression()

    def parse_call_arguments(self) -> list[Expression | None]:
        self.expect("(")
        arguments: list[Expression | None] = []

        if self.match(")"):
            return arguments

        while True:
            if self.peek().text in (",", ")"):
                arguments.append(None)
            else:
                arguments.append(self.parse_expression())

            if self.match(")"):
                return arguments

            self.expect(",")

    def parse_default_expression(self) -> Expression:
        expression = self.parse_expression()

        token = self.peek()
        if token.category is not TokenCategory.EOF:
            msg = (
                f"Unexpected token {token.text!r} after parameter default "
                f"at {token.line}:{token.column}"
            )
            raise CompilationError(msg)

        return expression
