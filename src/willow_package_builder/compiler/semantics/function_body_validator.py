from dataclasses import dataclass
from typing import TYPE_CHECKING

from willow_package_builder.compiler.syntax.expressions import (
    BinaryExpression,
    CallExpression,
    Expression,
    IdentifierExpression,
    UnaryExpression,
)
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

from .scope import VariableCategory
from .types import ResolvedType, TypeCategory

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
                    and symbol.category is VariableCategory.INSTANCE
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

            case UnaryExpression():
                self.validate_expression(expression.operand)

                operator = self.resolver.resolve_unary_operator(expression)
                parameter = operator.declaration.parameters[0]

                if "out" in parameter.modifiers:
                    self.require_writable(expression.operand)

            case CallExpression():
                self.validate_call(expression)

            case _:
                pass

        return self.resolver.type_of(expression)

    def _validate_statement(self, statement: Statement, return_type: ResolvedType) -> None:
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
                    if return_type.category is not TypeCategory.VOID:
                        msg = "Non-void function requires a return value"
                        raise CompilationError(msg)

                    return

                if return_type.category is TypeCategory.VOID:
                    msg = "Void function cannot return a value"
                    raise CompilationError(msg)

                value_type = self.validate_expression(statement.value)

                if value_type != return_type:
                    msg = f"Return type mismatch: expected {return_type!r}, got {value_type!r}"
                    raise CompilationError(msg)

                return

            case ExpressionStatement():
                self.validate_command_expression(statement.expression)
                return

            case IfStatement():
                condition_type = self.validate_expression(statement.condition)

                if condition_type.category is not TypeCategory.BOOL:
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

                if condition_type.category is not TypeCategory.BOOL:
                    msg = f"While condition must be bool, got {condition_type!r}"
                    raise CompilationError(msg)

                for child in statement.statements:
                    self.validate_statement(child, return_type)

                return

            case BreakStatement() | ContinueStatement():
                return

            case ForStatement():
                self.validate_statement(statement.initializer, return_type)

                condition_type = self.validate_expression(statement.condition)

                if condition_type.category is not TypeCategory.BOOL:
                    msg = f"For condition must be bool, got {condition_type!r}"
                    raise CompilationError(msg)

                self.validate_statement(statement.increment, return_type)

                for child in statement.statements:
                    self.validate_statement(child, return_type)

                return

            case DoUntilStatement():
                for child in statement.statements:
                    self.validate_statement(child, return_type)

                condition_type = self.validate_expression(statement.condition)

                if condition_type.category is not TypeCategory.BOOL:
                    msg = f"Until condition must be bool, got {condition_type!r}"
                    raise CompilationError(msg)

            case _:
                msg = f"Unsupported statement type: {type(statement).__name__}"
                raise TypeError(msg)

    def validate_statement(self, statement: Statement, return_type: ResolvedType) -> None:
        try:
            self._validate_statement(statement, return_type)
        except CompilationError as error:
            if error.location is not None or statement.location is None:
                raise

            msg = str(error)
            raise CompilationError(msg, statement.location) from error

    def validate(self, body: FunctionBody) -> None:
        scope = self.resolver.scope

        # Resolve declared types even if these variables are unused.
        for declaration in (*scope.function.parameters, *body.function_locals):
            self.resolver.resolve_declared_type(declaration.type_ref, scope.class_path)

        return_type = self.resolver.resolve_declared_type(
            scope.function.return_type, scope.class_path
        )

        try:
            for statement in body.statements:
                self.validate_statement(statement, return_type)
        except CompilationError as error:
            msg = f"{scope.class_path}.{scope.function.name} {error}"
            raise CompilationError(msg) from error

    def validate_command_expression(self, expression: Expression) -> None:
        self.validate_expression(expression)

        match expression:
            case UnaryExpression():
                operator = self.resolver.resolve_unary_operator(expression)

            case BinaryExpression():
                operator = self.resolver.resolve_operator(expression)

            case CallExpression():
                return

            case _:
                msg = "Expression has no effect"
                raise CompilationError(msg)

        if not any("out" in parameter.modifiers for parameter in operator.declaration.parameters):
            msg = "Expression has no effect"
            raise CompilationError(msg)

    def validate_call(self, expression: CallExpression) -> None:
        member = self.resolver.resolve_call(expression)
        function = member.declaration
        scope = self.resolver.scope
        path = f"{member.owner_class}.{function.name}"

        if "static" in scope.function.modifiers and "static" not in function.modifiers:
            msg = f"Static function cannot directly call instance function {path}"
            raise CompilationError(msg)

        if (
            "private" in function.modifiers
            and member.owner_class.casefold() != scope.class_path.casefold()
        ):
            msg = f"Cannot access private function {path}"
            raise CompilationError(msg)

        parameters = function.parameters
        arguments = expression.arguments

        if len(arguments) > len(parameters):
            msg = f"{path} accepts {len(parameters)} arguments, got {len(arguments)}"
            raise CompilationError(msg)

        missing = parameters[len(arguments) :]

        if any("optional" not in parameter.modifiers for parameter in missing):
            msg = f"Missing required arguments for {path}"
            raise CompilationError(msg)

        numeric = {TypeCategory.BYTE, TypeCategory.INT, TypeCategory.FLOAT}

        for parameter, argument in zip(parameters[: len(arguments)], arguments, strict=True):
            if argument is None:
                if "optional" not in parameter.modifiers:
                    msg = f"Required parameter {parameter.name!r} of {path} cannot be omitted"
                    raise CompilationError(msg)

                continue
            argument_type = self.validate_expression(argument)
            parameter_type = self.resolver.resolve_declared_type(
                parameter.type_ref, member.owner_class
            )

            if "out" in parameter.modifiers:
                if "const" in parameter.modifiers:
                    msg = f"Const-out arguments for {path} are not implemented yet"
                    raise NotImplementedError(msg)

                self.require_writable(argument)

                if argument_type != parameter_type:
                    msg = (
                        f"Out argument {parameter.name!r} of {path} requires "
                        f"{parameter_type!r}, got {argument_type!r}"
                    )
                    raise CompilationError(msg)

            elif argument_type != parameter_type:
                if (
                    argument_type.category in numeric and parameter_type.category in numeric
                ) or "coerce" in parameter.modifiers:
                    msg = (
                        f"Argument conversion for {parameter.name!r} "
                        f"of {path} is not implemented yet"
                    )
                    raise NotImplementedError(msg)

                msg = (
                    f"Argument {parameter.name!r} of {path} expects "
                    f"{parameter_type!r}, got {argument_type!r}"
                )
                raise CompilationError(msg)

    def validate_parameter_defaults(self, defaults: list[Expression | None]) -> None:
        scope = self.resolver.scope

        for parameter, expression in zip(scope.function.parameters, defaults, strict=True):
            if expression is None:
                continue

            actual = self.validate_expression(expression)
            expected = self.resolver.resolve_declared_type(parameter.type_ref, scope.class_path)

            if actual != expected:
                msg = (
                    f"Default for parameter {parameter.name!r} of "
                    f"{scope.class_path}.{scope.function.name} requires "
                    f"{expected!r}, got {actual!r}; "
                    "default argument conversions are not implemented yet"
                )
                raise NotImplementedError(msg)
