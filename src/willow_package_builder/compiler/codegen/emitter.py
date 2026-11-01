from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from willow_package_builder.bytecode import (
    Bytecode,
    BytecodeLabel,
    BytecodeName,
    BytecodeReference,
    BytecodeRelativeJump,
    LoopBlock,
)
from willow_package_builder.compiler.semantics.function_body_validator import FunctionBodyValidator
from willow_package_builder.compiler.semantics.scope import VariableCategory
from willow_package_builder.compiler.semantics.types import TypeCategory
from willow_package_builder.compiler.syntax.declarations import VariableDeclaration
from willow_package_builder.compiler.syntax.expressions import (
    BinaryExpression,
    BooleanExpression,
    CallExpression,
    Expression,
    FloatExpression,
    IdentifierExpression,
    IntegerExpression,
    MemberExpression,
    SelfExpression,
    StringExpression,
    UnaryExpression,
)
from willow_package_builder.compiler.syntax.modifiers import FunctionModifier, ParameterModifier
from willow_package_builder.compiler.syntax.statements import (
    AssignmentStatement,
    BreakStatement,
    ContinueStatement,
    DoUntilStatement,
    EmptyStatement,
    ExpressionStatement,
    ForStatement,
    IfStatement,
    ReturnStatement,
    Statement,
    WhileStatement,
)
from willow_package_builder.games import get_game
from willow_package_builder.logging import CompilationError
from willow_package_builder.upackage import FName, ReferencePath, UObject

if TYPE_CHECKING:
    from willow_package_builder.builder.prepared_function import PreparedFunction
    from willow_package_builder.compiler.semantics.expression_resolver import ExpressionResolver
    from willow_package_builder.opcode import Opcodes

    from .emission_context import EmissionContext


@dataclass
class FunctionEmitter:
    resolver: ExpressionResolver
    builder: EmissionContext
    function_object: UObject

    _loops: list[LoopBlock] = field(default_factory=list, init=False, repr=False)
    _opcodes: Opcodes = field(default_factory=lambda: get_game().OPCODES, init=False, repr=False)

    def _emit_identifier_expression(self, expression: IdentifierExpression) -> Bytecode:
        symbol = self.resolver.scope.resolve_variable(expression.name)

        resolved = self.resolver.resolve_declared_type(
            symbol.declaration.type_ref, symbol.owner_class
        )
        if resolved.category not in (
            TypeCategory.INT,
            TypeCategory.BOOL,
            TypeCategory.FLOAT,
            TypeCategory.STRING,
            TypeCategory.OBJECT,
        ):
            msg = f"Variable bytecode for type {resolved!r} is not supported yet"
            raise NotImplementedError(msg)

        if (
            isinstance(symbol.declaration, VariableDeclaration)
            and symbol.declaration.array_dimension != 1
        ):
            msg = f"Fixed array {expression.name!r} requires an element index"
            raise CompilationError(msg)

        script = Bytecode()

        if resolved.category is TypeCategory.BOOL:
            script += self._opcodes.BOOL_VARIABLE

        reference = self.variable_reference(expression.name)

        if symbol.category is VariableCategory.INSTANCE:
            script.add_instance_variable(reference)
        elif ParameterModifier.OUT in symbol.declaration.modifiers:
            script += self._opcodes.OUT_VARIABLE
            script += BytecodeReference(reference)
        else:
            script.add_local_variable(reference)

        return script

    def _emit_binary_expression(self, expression: BinaryExpression) -> Bytecode:
        member = self.resolver.resolve_operator(expression)
        operator = member.declaration

        if operator.native_index is None or operator.native_index == 0:
            msg = (
                f"Scripted operator calls are not supported yet: "
                f"{member.owner_class}.{operator.name}"
            )
            raise NotImplementedError(msg)

        if ParameterModifier.SKIP in operator.parameters[0].modifiers:
            msg = "Skipping the first operator argument is not implemented"
            raise NotImplementedError(msg)

        skip_end = (
            BytecodeLabel() if ParameterModifier.SKIP in operator.parameters[1].modifiers else None
        )

        script = Bytecode()

        with script.native_function(operator.native_index):
            script += self.emit_expression(expression.left)

            if skip_end is not None:
                origin = BytecodeLabel()

                script += self._opcodes.SKIP
                script += BytecodeRelativeJump(origin, skip_end)
                script += origin

            script += self.emit_expression(expression.right)

        # Must follow END_FUNCTION_PARAMS emitted by the context manager.
        if skip_end is not None:
            script += skip_end

        return script

    def _emit_unary_expression(self, expression: UnaryExpression) -> Bytecode:
        script = Bytecode()
        member = self.resolver.resolve_unary_operator(expression)
        operator = member.declaration

        if operator.native_index is None or operator.native_index == 0:
            msg = (
                "Scripted unary operator calls are not supported yet: "
                f"{member.owner_class}.{operator.name}"
            )
            raise CompilationError(msg)

        with script.native_function(operator.native_index):
            script += self.emit_expression(expression.operand)

        return script

    def _emit_call_body(self, expression: CallExpression) -> Bytecode:
        member = self.resolver.resolve_call(expression)
        function = member.declaration

        script = Bytecode()

        if function.native_index is not None and function.native_index != 0:
            with script.native_function(function.native_index):
                for argument in expression.arguments:
                    if argument is None:
                        script += self._opcodes.EMPTY_PARAMETER_VALUE
                    else:
                        script += self.emit_expression(argument)

            return script

        if (
            FunctionModifier.FINAL in function.modifiers
            or FunctionModifier.STATIC in function.modifiers
        ):
            path = f"{member.owner_class}.{function.name}"
            reference = self.builder.function_reference(path)

            script += self._opcodes.FINAL_FUNCTION
            script += BytecodeReference(reference)
        else:
            script += self._opcodes.VIRTUAL_FUNCTION
            script += BytecodeName(FName(function.name))

        for argument in expression.arguments:
            if argument is None:
                script += self._opcodes.EMPTY_PARAMETER_VALUE
            else:
                script += self.emit_expression(argument)

        for _ in function.parameters[len(expression.arguments) :]:
            script += self._opcodes.EMPTY_PARAMETER_VALUE

        script += self._opcodes.END_FUNCTION_PARAMS
        return script

    def _emit_call_expression(self, expression: CallExpression) -> Bytecode:
        call = self._emit_call_body(expression)

        if not isinstance(expression.callee, MemberExpression):
            return call

        member = self.resolver.resolve_call(expression)
        function = member.declaration
        result_type = self.resolver.resolve_declared_type(function.return_type, member.owner_class)

        result_property = ReferencePath()

        if result_type.category is not TypeCategory.VOID:
            path = f"{member.owner_class}.{function.name}"
            function_reference = self.builder.function_reference(path)
            owner_package = member.owner_class.partition(".")[0]

            if owner_package.casefold() == self.builder.config.name.casefold():
                reference = function_reference + FName("ReturnValue")
                result_property = self.builder.package.lookup_object_by_path(reference).reference()
            else:
                property_class = self.builder.context.references.property_class(result_type)
                class_package, _, class_name = property_class.path.partition(".")

                result_property = self.builder.ensure_import(
                    "ReturnValue", function_reference, class_package, class_name
                )

        receiver = self.emit_expression(expression.callee.object)
        script = Bytecode()

        with script.object_context(receiver, result_property):
            script += call

        return script

    def _emit_member_expression(self, expression: MemberExpression) -> Bytecode:
        member = self.resolver.resolve_member(expression)
        declaration = member.declaration
        resolved = self.resolver.resolve_declared_type(declaration.type_ref, member.owner_class)

        if declaration.array_dimension != 1:
            msg = f"Fixed array {expression.name!r} requires an element index"
            raise CompilationError(msg)

        if resolved.category not in (
            TypeCategory.INT,
            TypeCategory.BOOL,
            TypeCategory.FLOAT,
            TypeCategory.STRING,
            TypeCategory.OBJECT,
        ):
            msg = f"Member bytecode for type {resolved!r} is not implemented yet"
            raise NotImplementedError(msg)

        reference = self.property_reference(member.owner_class, declaration)
        receiver = self.emit_expression(expression.object)

        script = Bytecode()
        with script.object_context(receiver, reference):
            if resolved.category is TypeCategory.BOOL:
                script += self._opcodes.BOOL_VARIABLE

            script.add_instance_variable(reference)

        return script

    def emit_expression(self, expression: Expression) -> Bytecode:
        """Convert an expression into bytecode."""
        match expression:
            case BooleanExpression() | IntegerExpression() | FloatExpression() | StringExpression():
                script = Bytecode()
                script.add_constant(expression.value)
                return script

            case IdentifierExpression():
                return self._emit_identifier_expression(expression)

            case BinaryExpression():
                return self._emit_binary_expression(expression)

            case UnaryExpression():
                return self._emit_unary_expression(expression)

            case CallExpression():
                return self._emit_call_expression(expression)

            case MemberExpression():
                return self._emit_member_expression(expression)

            case SelfExpression():
                script = Bytecode()
                script += self._opcodes.SELF
                return script

            case _:
                msg = f"Unsupported expression type: {type(expression).__name__}"
                raise NotImplementedError(msg)

    def property_reference(
        self, owner_class: str, declaration: VariableDeclaration
    ) -> ReferencePath:
        outer = self.builder.class_object_reference(owner_class)
        owner_package = owner_class.partition(".")[0]

        if owner_package.casefold() == self.builder.config.name.casefold():
            reference = outer + FName(declaration.name)
            return self.builder.package.lookup_object_by_path(reference).reference()

        resolved = self.resolver.resolve_declared_type(declaration.type_ref, owner_class)
        property_class = self.builder.context.references.property_class(resolved)
        class_package, _, class_name = property_class.path.partition(".")

        return self.builder.ensure_import(declaration.name, outer, class_package, class_name)

    def variable_reference(self, name: str) -> ReferencePath:
        symbol = self.resolver.scope.resolve_variable(name)
        declaration = symbol.declaration

        if symbol.category is not VariableCategory.INSTANCE:
            reference = self.function_object.reference() + FName(declaration.name)
            return self.builder.package.lookup_object_by_path(reference).reference()

        if not isinstance(declaration, VariableDeclaration):
            msg = f"Instance variable {name!r} has no VariableDeclaration"
            raise TypeError(msg)

        return self.property_reference(symbol.owner_class, declaration)

    def _emit_assignment_statement(self, statement: AssignmentStatement) -> Bytecode:
        script = Bytecode()
        target_type = self.resolver.type_of(statement.target)

        if target_type.category is TypeCategory.BOOL:
            script += self._opcodes.LET_BOOL
        else:
            script += self._opcodes.LET

        script += self.emit_expression(statement.target)
        script += self.emit_expression(statement.value)
        return script

    def _emit_return_statement(self, statement: ReturnStatement) -> Bytecode:
        script = Bytecode()
        script += self._opcodes.RETURN

        if statement.value is None:
            script += self._opcodes.NOTHING
        else:
            script += self.emit_expression(statement.value)

        return script

    def _emit_expression_statement(self, statement: ExpressionStatement) -> Bytecode:
        script = Bytecode()
        expression = statement.expression
        result_type = self.resolver.type_of(expression)

        if result_type.category is TypeCategory.STRING:
            match expression:
                case BinaryExpression(left=IdentifierExpression() as target):
                    target_type = self.resolver.type_of(target)

                    if target_type.category is not TypeCategory.STRING:
                        msg = "Discarding this string expression is not implemented yet"
                        raise NotImplementedError(msg)

                    property_reference = self.variable_reference(target.name)

                case CallExpression():
                    member = self.resolver.resolve_call(expression)
                    function = member.declaration
                    path = f"{member.owner_class}.{function.name}"
                    function_reference = self.builder.function_reference(path)
                    return_reference = function_reference + FName("ReturnValue")

                    owner_package = member.owner_class.partition(".")[0]

                    if owner_package.casefold() == self.builder.config.name.casefold():
                        property_reference = self.builder.package.lookup_object_by_path(
                            return_reference
                        ).reference()
                    else:
                        property_reference = self.builder.ensure_import(
                            "ReturnValue", function_reference, "Core", "StrProperty"
                        )

                case _:
                    msg = "Discarding this string expression is not implemented yet"
                    raise NotImplementedError(msg)

            script += self._opcodes.EAT_RETURN_VALUE
            script += BytecodeReference(property_reference)

        script += self.emit_expression(expression)
        return script

    def _emit_if_statement(self, statement: IfStatement) -> Bytecode:
        script = Bytecode()
        condition = self.emit_expression(statement.condition)

        with script.if_statement(condition) as branch:
            for child in statement.then_statements:
                script += self.emit_statement(child)

            if statement.else_statements is not None:
                with branch.else_statement():
                    for child in statement.else_statements:
                        script += self.emit_statement(child)

        return script

    def _emit_while_statement(self, statement: WhileStatement) -> Bytecode:
        script = Bytecode()
        condition = self.emit_expression(statement.condition)

        with script.while_statement(condition) as loop:
            self._loops.append(loop)

            try:
                for child in statement.statements:
                    script += self.emit_statement(child)
            finally:
                self._loops.pop()

        return script

    def _emit_break_statement(self) -> Bytecode:
        script = Bytecode()
        if not self._loops:
            msg = "Break statement must be inside a loop"
            raise CompilationError(msg)

        script += self._loops[-1].break_statement()
        return script

    def _emit_continue_statement(self) -> Bytecode:
        script = Bytecode()
        if not self._loops:
            msg = "Continue statement must be inside a loop"
            raise CompilationError(msg)

        script += self._loops[-1].continue_statement()
        return script

    def _emit_for_statement(self, statement: ForStatement) -> Bytecode:
        script = Bytecode()
        initializer = self.emit_statement(statement.initializer)
        condition = self.emit_expression(statement.condition)
        increment = self.emit_statement(statement.increment)

        with script.for_statement(initializer, condition, increment) as loop:
            self._loops.append(loop)

            try:
                for child in statement.statements:
                    script += self.emit_statement(child)
            finally:
                self._loops.pop()

        return script

    def _emit_do_until_statement(self, statement: DoUntilStatement) -> Bytecode:
        script = Bytecode()
        condition = self.emit_expression(statement.condition)

        with script.do_until_statement(condition) as loop:
            self._loops.append(loop)

            try:
                for child in statement.statements:
                    script += self.emit_statement(child)
            finally:
                self._loops.pop()

        return script

    def emit_statement(self, statement: Statement) -> Bytecode:
        """Convert a statement into bytecode."""
        match statement:
            case EmptyStatement():
                return Bytecode()

            case AssignmentStatement():
                return self._emit_assignment_statement(statement)

            case ReturnStatement():
                return self._emit_return_statement(statement)

            case ExpressionStatement():
                return self._emit_expression_statement(statement)

            case IfStatement():
                return self._emit_if_statement(statement)

            case WhileStatement():
                return self._emit_while_statement(statement)

            case BreakStatement():
                return self._emit_break_statement()

            case ContinueStatement():
                return self._emit_continue_statement()

            case ForStatement():
                return self._emit_for_statement(statement)

            case DoUntilStatement():
                return self._emit_do_until_statement(statement)

            case _:
                msg = f"Unsupported statement type: {type(statement).__name__}"
                raise TypeError(msg)

    def emit_body(self, function: PreparedFunction) -> Bytecode:
        body = function.body

        FunctionBodyValidator(self.resolver).validate(body)

        return_type = self.resolver.resolve_declared_type(
            self.resolver.scope.function.return_type, self.resolver.scope.class_path
        )

        always_returns = self.statements_return(body.statements)

        if return_type.category is not TypeCategory.VOID and not always_returns:
            msg = "Non-void function does not return a value on every path"
            raise CompilationError(msg)

        script = Bytecode()

        for parameter, default in zip(
            self.resolver.scope.function.parameters, function.parameter_defaults, strict=True
        ):
            if ParameterModifier.OPTIONAL not in parameter.modifiers:
                continue

            if default is None:
                script += self._opcodes.NOTHING
            else:
                with script.default_parameter():
                    script += self.emit_expression(default)

        for statement in body.statements:
            script += self.emit_statement(statement)

        if not always_returns:
            script += self._opcodes.RETURN
            script += self._opcodes.NOTHING

        script += self._opcodes.END_OF_SCRIPT
        return script

    def statements_return(self, statements: list[Statement]) -> bool:
        for statement in statements:
            match statement:
                case ReturnStatement():
                    return True

                case IfStatement():
                    if (
                        statement.else_statements is not None
                        and self.statements_return(statement.then_statements)
                        and self.statements_return(statement.else_statements)
                    ):
                        return True

                case _:
                    pass

        return False
