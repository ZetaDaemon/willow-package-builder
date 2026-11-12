from dataclasses import dataclass
from typing import TYPE_CHECKING

from willow_package_builder.compiler.semantics.expression_resolver import (
    BUILTIN_CALL_SIGNATURES,
    BuiltinMember,
)
from willow_package_builder.compiler.syntax.declarations import (
    ParameterDeclaration,
    VariableDeclaration,
)
from willow_package_builder.compiler.syntax.expressions import (
    ArrayCountExpression,
    BinaryExpression,
    CallExpression,
    Expression,
    IdentifierExpression,
    IndexExpression,
    MemberExpression,
    SelfExpression,
    UnaryExpression,
)
from willow_package_builder.compiler.syntax.modifiers import (
    FunctionModifier,
    ParameterModifier,
    VariableModifier,
)
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
from willow_package_builder.logging import CompilationError, declaration_context
from willow_package_builder.upackage import CORE_OBJECT_PATH

from .scope import VariableCategory
from .types import ResolvedType, TypeCategory

if TYPE_CHECKING:
    from willow_package_builder.upackage import ReferencePath

    from .expression_resolver import ExpressionResolver


@dataclass
class FunctionBodyValidator:
    resolver: ExpressionResolver

    def require_writable(self, expression: Expression) -> None:
        match expression:
            case IdentifierExpression():
                symbol = self.resolver.scope.resolve_variable(expression.name)
                declaration = symbol.declaration
                owner = symbol.owner_class

            case MemberExpression():
                self.validate_expression(expression)
                if self.resolver.type_of(expression.object).category is TypeCategory.STRUCT:
                    self.require_writable(expression.object)

                member = self.resolver.resolve_member(expression)
                declaration = member.declaration
                owner = member.owner_class

            case IndexExpression():
                self.validate_expression(expression)
                self.require_writable(expression.array)
                return

            case _:
                msg = "Assignment destination must be a writable variable"
                raise CompilationError(msg)

        match declaration:
            case ParameterDeclaration():
                is_const = ParameterModifier.CONST in declaration.modifiers

            case VariableDeclaration():
                is_const = VariableModifier.CONST in declaration.modifiers

        if is_const:
            msg = f"Cannot assign to const variable {owner}.{declaration.name}"
            raise CompilationError(msg)

        if (
            VariableModifier.PRIVATE_WRITE in declaration.modifiers
            and owner != self.resolver.scope.class_path
        ):
            msg = f"Cannot modify privatewrite variable {owner}.{declaration.name}"
            raise CompilationError(msg)

        if (
            isinstance(declaration, VariableDeclaration)
            and VariableModifier.PROTECTED_WRITE in declaration.modifiers
        ):
            current_class = self.resolver.scope.class_path
            allowed = any(
                ancestor == owner
                for ancestor, _ in self.resolver.context.references.iter_class_hierarchy(
                    current_class, self.resolver.context.parents
                )
            )

            if not allowed:
                msg = f"Cannot modify protectedwrite variable {owner}.{declaration.name}"
                raise CompilationError(msg)

    def validate_expression(self, expression: Expression) -> ResolvedType:
        match expression:
            case IdentifierExpression():
                symbol = self.resolver.scope.resolve_variable(expression.name)
                self.validate_variable_access(symbol.declaration, symbol.owner_class)

                if (
                    FunctionModifier.STATIC in self.resolver.scope.function.modifiers
                    and symbol.category is VariableCategory.INSTANCE
                ):
                    msg = (
                        "Static function cannot directly access "
                        f"instance variable {expression.name!r}"
                    )
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
                    if ParameterModifier.OUT in parameter.modifiers:
                        self.require_writable(argument)

            case UnaryExpression():
                self.validate_expression(expression.operand)

                operator = self.resolver.resolve_unary_operator(expression)
                parameter = operator.declaration.parameters[0]

                if ParameterModifier.OUT in parameter.modifiers:
                    self.require_writable(expression.operand)

            case CallExpression():
                self.validate_call(expression)

            case MemberExpression():
                self.validate_expression(expression.object)

                if (
                    self.resolver.resolve_builtin_member(expression)
                    is not BuiltinMember.ARRAY_LENGTH
                ):
                    member = self.resolver.resolve_member(expression)
                    self.validate_variable_access(member.declaration, member.owner_class)

            case SelfExpression():
                if FunctionModifier.STATIC in self.resolver.scope.function.modifiers:
                    msg = "Cannot use self in a static function"
                    raise CompilationError(msg)

            case IndexExpression():
                self.validate_expression(expression.array)
                if self.resolver.resolve_enum_index(expression) is None:
                    self.validate_expression(expression.index)

            case ArrayCountExpression():
                self.validate_expression(expression.array)

            case _:
                pass

        return self.resolver.type_of(expression)

    def _validate_statement(self, statement: Statement, return_type: ResolvedType) -> None:
        match statement:
            case EmptyStatement():
                return

            case AssignmentStatement():
                target = statement.target

                if (
                    isinstance(target, MemberExpression)
                    and self.resolver.resolve_builtin_member(target) is BuiltinMember.ARRAY_LENGTH
                ):
                    self.require_writable(target.object)
                else:
                    self.require_writable(target)

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

            case ForeachStatement():
                self.validate_foreach(statement, return_type)
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
        scope = self.resolver.scope
        owner = scope.class_path
        path = owner + scope.function.name

        with declaration_context(path, statement.location):
            self._validate_statement(statement, return_type)

    def validate(self, body: FunctionBody) -> None:
        scope = self.resolver.scope
        owner = scope.class_path
        function_path = owner + scope.function.name

        with declaration_context(function_path, scope.function.location):
            # Resolve declared types even when the variables are unused.
            for declaration in (*scope.function.parameters, *body.function_locals):
                path = function_path + declaration.name

                with declaration_context(path, declaration.location):
                    self.resolver.resolve_declared_type(declaration.type_ref, scope.class_path)

            return_type = self.resolver.resolve_declared_type(
                scope.function.return_type, scope.class_path
            )

            for statement in body.statements:
                self.validate_statement(statement, return_type)

    def validate_command_expression(self, expression: Expression) -> None:
        self.validate_expression(expression)

        match expression:
            case UnaryExpression():
                operator = self.resolver.resolve_unary_operator(expression)

            case BinaryExpression():
                operator = self.resolver.resolve_operator(expression)

            case CallExpression():
                match self.resolver.resolve_builtin_call(expression):
                    case ((BuiltinMember.ARRAY_FIND | BuiltinMember.ARRAY_FIND_STRUCT), _):
                        msg = "Array Find result must be used"
                        raise CompilationError(msg)

                    case _:
                        pass

                return

            case _:
                msg = "Expression has no effect"
                raise CompilationError(msg)

        if not any(
            ParameterModifier.OUT in parameter.modifiers
            for parameter in operator.declaration.parameters
        ):
            msg = "Expression has no effect"
            raise CompilationError(msg)

    def validate_call(self, expression: CallExpression) -> None:
        builtin_call = self.resolver.resolve_builtin_call(expression)

        if builtin_call is not None:
            builtin, receiver = builtin_call
            receiver_type = self.validate_expression(receiver)

            signature = BUILTIN_CALL_SIGNATURES[builtin]

            if signature.mutates_receiver:
                self.require_writable(receiver)

            arguments = self.resolver.require_builtin_arguments(
                expression, len(signature.arguments)
            )

            if builtin is BuiltinMember.ARRAY_SORT:
                self.resolver.resolve_array_sort_comparator(receiver_type, arguments[0])
                return

            if builtin is BuiltinMember.ARRAY_FIND_STRUCT:
                field, _ = arguments
                expected_types = (
                    ResolvedType(TypeCategory.NAME),
                    self.resolver.resolve_struct_find_field_type(receiver_type, field),
                )
            else:
                expected_types = tuple(
                    receiver_type.arguments[0] if category is None else ResolvedType(category)
                    for category in signature.arguments
                )

            for argument, expected in zip(arguments, expected_types, strict=True):
                actual = self.validate_expression(argument)

                if actual != expected:
                    msg = f"Array {builtin.name} expects {expected!r}, got {actual!r}"
                    raise CompilationError(msg)

            return

        member = self.resolver.resolve_call(expression)
        function = member.declaration

        scope = self.resolver.scope
        path = member.owner_class + function.name

        match expression.callee:
            case MemberExpression():
                self.validate_expression(expression.callee.object)

            case IdentifierExpression():
                if (
                    FunctionModifier.STATIC in scope.function.modifiers
                    and FunctionModifier.STATIC not in function.modifiers
                ):
                    msg = f"Static function cannot directly call instance function {path}"
                    raise CompilationError(msg)

            case _:
                pass

        if (
            FunctionModifier.PRIVATE in function.modifiers
            and member.owner_class != scope.class_path
        ):
            msg = f"Cannot access private function {path}"
            raise CompilationError(msg)

        if FunctionModifier.PROTECTED in function.modifiers and not self.can_access_protected(
            member.owner_class
        ):
            msg = f"Cannot access protected function {path}"
            raise CompilationError(msg)

        parameters = function.parameters
        arguments = expression.arguments

        if len(arguments) > len(parameters):
            msg = f"{path} accepts {len(parameters)} arguments, got {len(arguments)}"
            raise CompilationError(msg)

        missing = parameters[len(arguments) :]

        if any(ParameterModifier.OPTIONAL not in parameter.modifiers for parameter in missing):
            msg = f"Missing required arguments for {path}"
            raise CompilationError(msg)

        numeric = {TypeCategory.BYTE, TypeCategory.INT, TypeCategory.FLOAT}

        for parameter, argument in zip(parameters[: len(arguments)], arguments, strict=True):
            if argument is None:
                if ParameterModifier.OPTIONAL not in parameter.modifiers:
                    msg = f"Required parameter {parameter.name!r} of {path} cannot be omitted"
                    raise CompilationError(msg)

                continue
            argument_type = self.validate_expression(argument)

            dimension = self.resolver.array_dimension_of(argument)

            if dimension != parameter.array_dimension:
                msg = (
                    f"Argument {parameter.name!r} of {path} requires array dimension "
                    f"{parameter.array_dimension}, got {dimension}"
                )
                raise CompilationError(msg)

            parameter_type = self.resolver.resolve_declared_type(
                parameter.type_ref, member.owner_class
            )

            if ParameterModifier.OUT in parameter.modifiers:
                if ParameterModifier.CONST in parameter.modifiers:
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
                ) or ParameterModifier.COERCE in parameter.modifiers:
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

    def validate_variable_access(
        self, declaration: ParameterDeclaration | VariableDeclaration, owner: ReferencePath
    ) -> None:
        if not isinstance(declaration, VariableDeclaration):
            return

        current = self.resolver.scope.class_path

        if VariableModifier.PRIVATE in declaration.modifiers and current != owner:
            msg = f"Cannot access private variable {owner}.{declaration.name}"
            raise CompilationError(msg)

        if VariableModifier.PROTECTED in declaration.modifiers and not self.can_access_protected(
            owner
        ):
            msg = f"Cannot access protected variable {owner}.{declaration.name}"
            raise CompilationError(msg)

    def can_access_protected(self, owner: ReferencePath) -> bool:
        references = self.resolver.context.references
        parents = self.resolver.context.parents
        packages = self.resolver.context.packages
        current = self.resolver.scope.class_path
        visited: set[ReferencePath] = set()

        while current != CORE_OBJECT_PATH:
            key = current

            if key in visited:
                msg = f"Circular within hierarchy at {current}"
                raise CompilationError(msg)

            visited.add(key)

            if references.is_subclass(current, owner, parents):
                return True

            current = references.resolve_within_class(current, parents, packages)

        return references.is_subclass(current, owner, parents)

    def validate_foreach(self, statement: ForeachStatement, return_type: ResolvedType) -> None:
        iterator = statement.iterator
        array = iterator.callee
        array_type = self.validate_expression(array)

        if (
            array_type.category is not TypeCategory.ARRAY
            or self.resolver.array_dimension_of(array) != 1
        ):
            msg = "foreach currently requires a dynamic array"
            raise CompilationError(msg)

        arguments = iterator.arguments
        if not 1 <= len(arguments) <= 2 or arguments[0] is None:
            msg = "Array foreach requires an item output and accepts an optional index output"
            raise CompilationError(msg)

        item = arguments[0]
        index = arguments[1] if len(arguments) == 2 else None
        outputs = [(item, array_type.arguments[0])]

        if index is not None:
            outputs.append((index, ResolvedType(TypeCategory.INT)))

        for output, expected in outputs:
            self.require_writable(output)
            actual = self.validate_expression(output)

            if actual != expected or self.resolver.array_dimension_of(output) != 1:
                msg = f"Array foreach output must be a single value of type {expected!r}"
                raise CompilationError(msg)

        for child in statement.statements:
            self.validate_statement(child, return_type)
