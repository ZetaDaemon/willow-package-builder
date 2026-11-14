from typing import TYPE_CHECKING, Self

from willow_package_builder.compiler.semantics.reference_database import PRIMITIVE_TYPES
from willow_package_builder.compiler.semantics.types import TypeCategory
from willow_package_builder.compiler.syntax.declarations import OperatorCategory, TypeReference
from willow_package_builder.compiler.syntax.expressions import (
    ArrayCountExpression,
    BinaryExpression,
    BooleanExpression,
    CallExpression,
    CastExpression,
    ClassLiteralExpression,
    ConditionalExpression,
    Expression,
    FloatExpression,
    GlobalExpression,
    IdentifierExpression,
    IndexExpression,
    IntegerExpression,
    MemberExpression,
    NameExpression,
    NewExpression,
    NoneExpression,
    SelfExpression,
    StringExpression,
    SuperExpression,
    UnaryExpression,
    VectorExpression,
)
from willow_package_builder.compiler.syntax.keyword import ScriptKeywords
from willow_package_builder.compiler.syntax.lexer import Token, TokenCategory
from willow_package_builder.compiler.syntax.punctuation import Operator, Punctuation
from willow_package_builder.compiler.syntax.statements import (
    AssignmentStatement,
    BreakStatement,
    ContinueStatement,
    DoUntilStatement,
    EmptyStatement,
    ExpressionStatement,
    ForeachStatement,
    ForStatement,
    FunctionBody,
    IfStatement,
    ReturnStatement,
    Statement,
    WhileStatement,
)
from willow_package_builder.logging import CompilationError, SourceLocation
from willow_package_builder.upackage import FName, ReferencePath

from .declaration_syntax_parser import DeclarationSyntaxParser

if TYPE_CHECKING:
    from collections.abc import Sequence

    from willow_package_builder.compiler.semantics.expression_resolver import ExpressionResolver
    from willow_package_builder.compiler.syntax.declarations import (
        FunctionDeclaration,
        VariableDeclaration,
    )


class FunctionParser(DeclarationSyntaxParser):
    expression_resolver: ExpressionResolver | None

    def __init__(  # noqa: D107
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
            column = last.column + len(last)

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

    def _parse_vector_component(self) -> float:
        negative = self.match(Operator.SUBTRACT)
        token = self.peek()

        match token.category:
            case TokenCategory.INTEGER:
                value = float(int(token))
            case TokenCategory.FLOAT:
                value = float(token)
            case _:
                msg = f"Expected a numeric vector component at {token.line}:{token.column}"
                raise CompilationError(msg)

        self.advance()
        return -value if negative else value

    def parse_primary_expression(self) -> Expression:
        token = self.peek()

        match token.category:
            case TokenCategory.INTEGER:
                self.advance()
                return IntegerExpression(int(token))

            case TokenCategory.IDENTIFIER:
                self.advance()

                match token:
                    case ScriptKeywords.VECT if self.match(Punctuation.LEFT_PAREN):
                        x = self._parse_vector_component()
                        self.expect(Punctuation.COMMA)
                        y = self._parse_vector_component()
                        self.expect(Punctuation.COMMA)
                        z = self._parse_vector_component()
                        self.expect(Punctuation.RIGHT_PAREN)
                        return VectorExpression(x, y, z)

                    case ScriptKeywords.GLOBAL:
                        self.expect(Punctuation.DOT)
                        return GlobalExpression(self.expect_identifier().fname)

                    case ScriptKeywords.SUPER:
                        ancestor = None
                        if self.match(Punctuation.LEFT_PAREN):
                            ancestor = self.expect_identifier().fname
                            self.expect(Punctuation.RIGHT_PAREN)

                        self.expect(Punctuation.DOT)
                        name = self.expect_identifier().fname
                        return SuperExpression(ancestor, name)

                    case ScriptKeywords.CLASS if self.peek().category is TokenCategory.NAME:
                        literal = self.advance()
                        path = str(literal)[1:-1]
                        if not path or "\\" in path or any(not part for part in path.split(".")):
                            msg = f"Invalid class literal at {literal.line}:{literal.column}"
                            raise CompilationError(msg)

                        return ClassLiteralExpression(ReferencePath(path))

                    case ScriptKeywords.TRUE:
                        return BooleanExpression(True)  # noqa: FBT003

                    case ScriptKeywords.FALSE:
                        return BooleanExpression(False)  # noqa: FBT003

                    case ScriptKeywords.SELF:
                        return SelfExpression()

                    case ScriptKeywords.NONE:
                        return NoneExpression()

                    case ScriptKeywords.ARRAY_COUNT:
                        self.expect(Punctuation.LEFT_PAREN)
                        array = self.parse_expression()
                        self.expect(Punctuation.RIGHT_PAREN)
                        return ArrayCountExpression(array)

                    case ScriptKeywords.NEW:
                        self.expect(Punctuation.LEFT_PAREN)
                        outer = self.parse_expression()
                        self.expect(Punctuation.RIGHT_PAREN)

                        if (
                            self.peek() != ScriptKeywords.CLASS
                            or self.peek(1).category is not TokenCategory.NAME
                        ):
                            msg = "Expected a class literal after new(Outer)"
                            raise CompilationError(msg)

                        object_class = self.parse_primary_expression()
                        if not isinstance(object_class, ClassLiteralExpression):
                            msg = "Expected a class literal after new(Outer)"
                            raise CompilationError(msg)

                        return NewExpression(outer, object_class)

                    case _:
                        resolver = self.expression_resolver
                        if resolver is not None and self.peek() not in (
                            Punctuation.LEFT_PAREN,
                            Punctuation.DOT,
                        ):
                            constant = resolver.resolve_integer_constant(token.fname)
                            if constant is not None:
                                return constant

                            member = resolver.resolve_bare_enum_member(token.fname)
                            if member is not None:
                                return member

                        return IdentifierExpression(token.fname)

            case TokenCategory.FLOAT:
                self.advance()
                return FloatExpression(float(token))

            case TokenCategory.STRING:
                self.advance()
                value = str(token)[1:-1]

                if "\\" in value:
                    msg = (
                        "String escape decoding is not implemented yet "
                        f"at {token.line}:{token.column}"
                    )
                    raise NotImplementedError(msg)

                return StringExpression(value)

            case TokenCategory.NAME:
                self.advance()
                value = str(token)[1:-1]

                if "\\" in value:
                    msg = f"Name literal escapes are not implemented at {token.line}:{token.column}"
                    raise NotImplementedError(msg)

                return NameExpression(FName(value))

            case _:
                pass

        if self.match(Punctuation.LEFT_PAREN):
            expression = self.parse_expression()
            self.expect(Punctuation.RIGHT_PAREN)
            return expression

        msg = f"Expected expression, got {token} at {token.line}:{token.column}"
        raise CompilationError(msg)

    def parse_expression(
        self, maximum_precedence: int | None = None, *, enum_hint: ReferencePath | None = None
    ) -> Expression:
        resolver = self.expression_resolver

        if resolver is None:
            msg = "Expression parsing requires an expression resolver"
            raise ValueError(msg)

        member = None
        if (
            enum_hint is not None
            and self.peek().category is TokenCategory.IDENTIFIER
            and self.peek(1)
            not in (Punctuation.DOT, Punctuation.LEFT_PAREN, Punctuation.LEFT_BRACKET)
        ):
            member = resolver.resolve_enum_member_hint(self.peek().fname, enum_hint)

        if member is None:
            left = self.parse_unary_expression()
        else:
            self.advance()
            left = member

        while True:
            token = self.peek()
            operator = token.operator_name

            if operator is None:
                break

            left_type = resolver.type_of(left)
            precedence = resolver.binary_precedence(operator, left_type)

            if precedence is None:
                break

            if maximum_precedence is not None and precedence > maximum_precedence:
                break

            self.advance()
            right = self.parse_expression(
                precedence - 1,
                enum_hint=(
                    left_type.declaration_path if left_type.category is TypeCategory.ENUM else None
                ),
            )

            expression = BinaryExpression(left, operator, right)
            resolver.resolve_operator(expression)
            left = expression

        if maximum_precedence is None and self.match(Operator.QUESTION):
            when_true = self.parse_expression()
            self.expect(Punctuation.COLON)
            when_false = self.parse_expression()
            return ConditionalExpression(left, when_true, when_false)

        return left

    def parse_local_declarations(self) -> list[VariableDeclaration]:
        declarations: list[VariableDeclaration] = []

        while self.peek() == ScriptKeywords.LOCAL:
            declarations.extend(self.parse_variable_declaration(is_local=True))

        return declarations

    def parse_statement_branch(self) -> list[Statement]:
        if not self.match(Punctuation.LEFT_BRACE):
            return [self.parse_statement()]

        statements: list[Statement] = []

        while not self.match(Punctuation.RIGHT_BRACE):
            token = self.peek()

            if token.category is TokenCategory.EOF:
                msg = f"Unterminated statement block at {token.line}:{token.column}"
                raise CompilationError(msg)

            statements.append(self.parse_statement())

        return statements

    def parse_if_statement(self) -> IfStatement:
        self.expect(ScriptKeywords.IF)
        self.expect(Punctuation.LEFT_PAREN)
        condition = self.parse_expression()
        self.expect(Punctuation.RIGHT_PAREN)

        then_statements = self.parse_statement_branch()

        else_statements = None
        if self.match(ScriptKeywords.ELSE):
            else_statements = self.parse_statement_branch()

        return IfStatement(condition, then_statements, else_statements)

    def parse_while_statement(self) -> WhileStatement:
        self.expect(ScriptKeywords.WHILE)
        self.expect(Punctuation.LEFT_PAREN)
        condition = self.parse_expression()
        self.expect(Punctuation.RIGHT_PAREN)

        statements = self.parse_statement_branch()
        return WhileStatement(condition, statements)

    def parse_foreach_statement(self) -> ForeachStatement:
        self.expect(ScriptKeywords.FOREACH)
        iterator = self.parse_postfix_expression()

        if not isinstance(iterator, CallExpression):
            msg = "Expected an iterator call after foreach"
            raise CompilationError(msg)

        return ForeachStatement(iterator, self.parse_statement_branch())

    def _parse_statement(self) -> Statement:
        if self.match(Punctuation.SEMICOLON):
            return EmptyStatement()

        if self.match(ScriptKeywords.RETURN):
            if self.match(Punctuation.SEMICOLON):
                return ReturnStatement()

            value = self.parse_expression()
            self.expect(Punctuation.SEMICOLON)
            return ReturnStatement(value)

        token = self.peek()

        # Because the match case ends up replacing the token variable with the match
        # i assigned it to a secondary variable so token.line and token.column remain available.
        t = token
        match t:
            case ScriptKeywords.LOCAL:
                msg = (
                    "Local declarations must precede executable statements "
                    f"at {token.line}:{token.column}"
                )
                raise CompilationError(msg)

            case ScriptKeywords.IF:
                return self.parse_if_statement()

            case ScriptKeywords.WHILE:
                return self.parse_while_statement()

            case ScriptKeywords.FOR:
                return self.parse_for_statement()

            case ScriptKeywords.DO:
                return self.parse_do_until_statement()

            case ScriptKeywords.FOREACH:
                return self.parse_foreach_statement()

            case _:
                pass

        if self.match(ScriptKeywords.BREAK):
            self.expect(Punctuation.SEMICOLON)
            return BreakStatement()

        if self.match(ScriptKeywords.CONTINUE):
            self.expect(Punctuation.SEMICOLON)
            return ContinueStatement()

        expression = self.parse_expression()

        if self.match(Operator.EQUAL):
            value = self.parse_expression()
            self.expect(Punctuation.SEMICOLON)
            return AssignmentStatement(expression, value)

        self.expect(Punctuation.SEMICOLON)
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
            resolver.resolve_local_array_dimension(declaration)
            resolver.scope.add_local(declaration)

        statements: list[Statement] = []

        while self.peek().category is not TokenCategory.EOF:
            statements.append(self.parse_statement())

        return FunctionBody(function_locals, statements)

    def parse_for_clause(self) -> Statement:
        token = self.peek()
        location = SourceLocation(token.line, token.column)
        expression = self.parse_expression()

        if self.match(Operator.EQUAL):
            value = self.parse_expression()
            return AssignmentStatement(expression, value, location=location)

        return ExpressionStatement(expression, location=location)

    def parse_for_statement(self) -> ForStatement:
        self.expect(ScriptKeywords.FOR)
        self.expect(Punctuation.LEFT_PAREN)

        initializer = self.parse_for_clause()
        self.expect(Punctuation.SEMICOLON)

        condition = self.parse_expression()
        self.expect(Punctuation.SEMICOLON)

        increment = self.parse_for_clause()
        self.expect(Punctuation.RIGHT_PAREN)

        statements = self.parse_statement_branch()

        return ForStatement(initializer, condition, increment, statements)

    def parse_do_until_statement(self) -> DoUntilStatement:
        self.expect(ScriptKeywords.DO)
        statements = self.parse_statement_branch()

        self.expect(ScriptKeywords.UNTIL)
        self.expect(Punctuation.LEFT_PAREN)
        condition = self.parse_expression()
        self.expect(Punctuation.RIGHT_PAREN)
        self.expect(Punctuation.SEMICOLON)

        return DoUntilStatement(statements, condition)

    def parse_postfix_expression(self) -> Expression:
        resolver = self.expression_resolver

        if resolver is None:
            msg = "Postfix expression parsing requires an expression resolver"
            raise ValueError(msg)

        expression = self.parse_primary_expression()

        while True:
            if self.match(Punctuation.DOT):
                name = self.expect_identifier().fname

                if isinstance(expression, IdentifierExpression):
                    member = resolver.resolve_qualified_enum_member(expression.name, name)
                    if member is not None:
                        expression = member
                        continue

                expression = MemberExpression(expression, name)
                continue

            if self.peek() == Punctuation.LEFT_PAREN:
                arguments = self.parse_call_arguments()

                if isinstance(expression, IdentifierExpression) and (
                    (target := ReferencePath(expression.name)) in PRIMITIVE_TYPES
                    or resolver.is_object_cast_target(expression.name)
                ):
                    if len(arguments) != 1 or (operand := arguments[0]) is None:
                        msg = f"{target}(...) requires exactly one argument"
                        raise CompilationError(msg)

                    expression = CastExpression(TypeReference(target), operand)

                else:
                    expression = CallExpression(expression, arguments)
                continue

            if self.match(Punctuation.LEFT_BRACKET):
                index = self.parse_expression()
                self.expect(Punctuation.RIGHT_BRACKET)
                expression = IndexExpression(expression, index)
                continue

            operator_name = self.peek().operator_name
            if operator_name is not None and resolver.has_unary_operator(
                operator_name, OperatorCategory.POSTFIX
            ):
                # we already got what we needed in operator_name, now just progress the parser.
                self.advance()
                expression = UnaryExpression(operator_name, expression, OperatorCategory.POSTFIX)
                resolver.resolve_unary_operator(expression)
                continue

            return expression

    def parse_unary_expression(self) -> Expression:
        resolver = self.expression_resolver

        if resolver is None:
            msg = "Unary expression parsing requires an expression resolver"
            raise ValueError(msg)

        operator_name = self.peek().operator_name

        if operator_name is not None and resolver.has_unary_operator(
            operator_name, OperatorCategory.PREFIX
        ):
            # we already got what we needed in operator_name, now just progress the parser.
            self.advance()
            operand = self.parse_unary_expression()

            expression = UnaryExpression(operator_name, operand, OperatorCategory.PREFIX)
            resolver.resolve_unary_operator(expression)
            return expression

        return self.parse_postfix_expression()

    def parse_call_arguments(self) -> list[Expression | None]:
        self.expect(Punctuation.LEFT_PAREN)
        arguments: list[Expression | None] = []

        if self.match(Punctuation.RIGHT_PAREN):
            return arguments

        while True:
            if self.peek() in (Punctuation.COMMA, Punctuation.RIGHT_PAREN):
                arguments.append(None)
            else:
                arguments.append(self.parse_expression())

            if self.match(Punctuation.RIGHT_PAREN):
                return arguments

            self.expect(Punctuation.COMMA)

    def parse_default_expression(self) -> Expression:
        expression = self.parse_expression()

        token = self.peek()
        if token.category is not TokenCategory.EOF:
            msg = f"Unexpected token {token} after parameter default at {token.line}:{token.column}"
            raise CompilationError(msg)

        return expression
