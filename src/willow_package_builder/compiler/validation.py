from dataclasses import dataclass
from typing import TYPE_CHECKING

from willow_package_builder.logging import CompilationError

from .expressions import BinaryExpression, Expression, IdentifierExpression
from .scope import VariableType
from .statements import (
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
from .types import ResolvedType, TypeType

if TYPE_CHECKING:
    from .expression_resolver import ExpressionResolver


@dataclass
class FunctionBodyValidator:
    resolver: ExpressionResolver

    def require_writable(self, expression: Expression) -> None:
        if not isinstance(expression, IdentifierExpression):
            msg = "Assignment destination must be a writable variable"
            raise CompilationError(msg)

        symbol = self.resolver.scope.resolve_variable(expression.name)

        if "const" in symbol.declaration.modifiers:
            msg = f"Cannot assign to const variable {expression.name!r}"
            raise CompilationError(msg)

    def validate_expression(self, expression: Expression) -> ResolvedType:
        match expression:
            case IdentifierExpression():
                symbol = self.resolver.scope.resolve_variable(expression.name)

                if (
                    "static" in self.resolver.scope.function.modifiers
                    and symbol.type is VariableType.INSTANCE
                ):
                    msg = f"Static function cannot directly access instance variable {expression.name!r}"
                    raise CompilationError(msg)

            case BinaryExpression():
                self.validate_expression(expression.left)
                self.validate_expression(expression.right)

                operator = self.resolver.resolve_operator(expression)

                for parameter, argument in zip(
                    operator.declaration.parameters,
                    (expression.left, expression.right),
                    strict=True,
                ):
                    if "out" in parameter.modifiers:
                        self.require_writable(argument)

            case _:
                pass

        return self.resolver.type_of(expression)

    def validate_statement(self, statement: Statement, return_type: ResolvedType) -> None:
        match statement:
            case EmptyStatement():
                return

            case AssignmentStatement():
                self.require_writable(statement.target)

                target_type = self.validate_expression(statement.target)
                value_type = self.validate_expression(statement.value)

                if target_type != value_type:
                    msg = (
                        f"Assignment type mismatch: destination is {target_type!r}, "
                        f"value is {value_type!r}"
                    )
                    raise CompilationError(msg)

                return

            case ReturnStatement():
                if statement.value is None:
                    if return_type.type is not TypeType.VOID:
                        msg = "Non-void function requires a return value"
                        raise CompilationError(msg)

                    return

                if return_type.type is TypeType.VOID:
                    msg = "Void function cannot return a value"
                    raise CompilationError(msg)

                value_type = self.validate_expression(statement.value)

                if value_type != return_type:
                    msg = f"Return type mismatch: expected {return_type!r}, got {value_type!r}"
                    raise CompilationError(msg)

                return

            case ExpressionStatement():
                self.validate_expression(statement.expression)
                return

            case IfStatement():
                condition_type = self.validate_expression(statement.condition)

                if condition_type.type is not TypeType.BOOL:
                    msg = f"If condition must be bool, got {condition_type!r}"
                    raise CompilationError(msg)

                for child in statement.then_statements:
                    self.validate_statement(child, return_type)

                if statement.else_statements is not None:
                    for child in statement.else_statements:
                        self.validate_statement(child, return_type)

                return

            case WhileStatement():
                condition_type = self.validate_expression(statement.condition)

                if condition_type.type is not TypeType.BOOL:
                    msg = f"While condition must be bool, got {condition_type!r}"
                    raise CompilationError(msg)

                for child in statement.statements:
                    self.validate_statement(child, return_type)

                return

            case BreakStatement() | ContinueStatement():
                return

            case _:
                msg = f"Unsupported statement type: {type(statement).__name__}"
                raise TypeError(msg)

    def validate(self, body: FunctionBody) -> None:
        scope = self.resolver.scope

        # Resolve declared types even if these variables are unused.
        for declaration in (*scope.function.parameters, *body.locals):
            self.resolver.resolve_declared_type(declaration.type_ref, scope.class_path)

        return_type = self.resolver.resolve_declared_type(
            scope.function.return_type, scope.class_path
        )

        for statement in body.statements:
            self.validate_statement(statement, return_type)
