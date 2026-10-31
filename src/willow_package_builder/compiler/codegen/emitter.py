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
from willow_package_builder.compiler.builder.prepared_function import PreparedFunction
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
    StringExpression,
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
from willow_package_builder.opcode import ScriptOpcode
from willow_package_builder.upackage import FName, ReferencePath, UObject

if TYPE_CHECKING:
    from willow_package_builder.compiler.semantics.expression_resolver import ExpressionResolver

    from .emission_context import EmissionContext


@dataclass
class FunctionEmitter:
    resolver: ExpressionResolver
    builder: EmissionContext
    function_object: UObject

    _loops: list[LoopBlock] = field(default_factory=list, init=False, repr=False)

    def emit_expression(self, expression: Expression) -> Bytecode:
        """Convert an expression into bytecode."""
        script = Bytecode()

        match expression:
            case BooleanExpression():
                script += ScriptOpcode.TRUE if expression.value else ScriptOpcode.FALSE
                return script

            case IntegerExpression():
                script.add_constant(expression.value)
                return script

            case FloatExpression():
                script.add_constant(expression.value)
                return script

            case StringExpression():
                script.add_constant(expression.value)
                return script

            case IdentifierExpression():
                symbol = self.resolver.scope.resolve_variable(expression.name)

                resolved = self.resolver.resolve_declared_type(
                    symbol.declaration.type_ref, symbol.owner_class
                )
                if resolved.category not in (
                    TypeCategory.INT,
                    TypeCategory.BOOL,
                    TypeCategory.FLOAT,
                    TypeCategory.STRING,
                ):
                    msg = f"Variable bytecode for type {resolved!r} is not supported yet"
                    raise NotImplementedError(msg)

                if (
                    isinstance(symbol.declaration, VariableDeclaration)
                    and symbol.declaration.array_dimension != 1
                ):
                    msg = f"Fixed array {expression.name!r} requires an element index"
                    raise CompilationError(msg)

                if resolved.category is TypeCategory.BOOL:
                    script += ScriptOpcode.BOOL_VARIABLE

                reference = self.variable_reference(expression.name)

                if symbol.category is VariableCategory.INSTANCE:
                    script.add_instance_variable(reference)
                elif "out" in symbol.declaration.modifiers:
                    script += ScriptOpcode.OUT_VARIABLE
                    script += BytecodeReference(reference)
                else:
                    script.add_local_variable(reference)

                return script

            case BinaryExpression():
                member = self.resolver.resolve_operator(expression)
                operator = member.declaration

                if operator.native_index is None or operator.native_index == 0:
                    msg = (
                        f"Scripted operator calls are not supported yet: "
                        f"{member.owner_class}.{operator.name}"
                    )
                    raise NotImplementedError(msg)

                if "skip" in operator.parameters[0].modifiers:
                    msg = "Skipping the first operator argument is not implemented"
                    raise NotImplementedError(msg)

                skip_end = BytecodeLabel() if "skip" in operator.parameters[1].modifiers else None

                with script.native_function(operator.native_index):
                    script += self.emit_expression(expression.left)

                    if skip_end is not None:
                        origin = BytecodeLabel()

                        script += ScriptOpcode.SKIP
                        script += BytecodeRelativeJump(origin, skip_end)
                        script += origin

                    script += self.emit_expression(expression.right)

                # Must follow END_FUNCTION_PARAMS emitted by the context manager.
                if skip_end is not None:
                    script += skip_end

                return script

            case UnaryExpression():
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

            case CallExpression():
                member = self.resolver.resolve_call(expression)
                function = member.declaration

                if function.native_index is not None and function.native_index != 0:
                    with script.native_function(function.native_index):
                        for argument in expression.arguments:
                            if argument is None:
                                script += ScriptOpcode.EMPTY_PARAMETER_VALUE
                            else:
                                script += self.emit_expression(argument)

                    return script

                if "final" in function.modifiers or "static" in function.modifiers:
                    path = f"{member.owner_class}.{function.name}"
                    reference = self.builder.function_reference(path)

                    script += ScriptOpcode.FINAL_FUNCTION
                    script += BytecodeReference(reference)
                else:
                    script += ScriptOpcode.VIRTUAL_FUNCTION
                    script += BytecodeName(FName(function.name))

                for argument in expression.arguments:
                    if argument is None:
                        script += ScriptOpcode.EMPTY_PARAMETER_VALUE
                    else:
                        script += self.emit_expression(argument)

                for _ in function.parameters[len(expression.arguments) :]:
                    script += ScriptOpcode.EMPTY_PARAMETER_VALUE

                script += ScriptOpcode.END_FUNCTION_PARAMS
                return script

            case _:
                msg = f"Unsupported expression type: {type(expression).__name__}"
                raise TypeError(msg)

    def variable_reference(self, name: str) -> ReferencePath:
        symbol = self.resolver.scope.resolve_variable(name)
        declaration = symbol.declaration

        if symbol.category is not VariableCategory.INSTANCE:
            reference = self.function_object.reference() + FName(declaration.name)
            return self.builder.package.lookup_object_by_path(reference).reference()

        outer = self.builder.class_object_reference(symbol.owner_class)
        owner_package = symbol.owner_class.partition(".")[0]

        if owner_package.casefold() == self.builder.config.name.casefold():
            reference = outer + FName(declaration.name)
            return self.builder.package.lookup_object_by_path(reference).reference()

        resolved = self.resolver.resolve_declared_type(declaration.type_ref, symbol.owner_class)

        property_class = self.builder.context.references.property_class(resolved)
        class_package, _, class_name = property_class.path.partition(".")

        return self.builder.ensure_import(declaration.name, outer, class_package, class_name)

    def emit_statement(self, statement: Statement) -> Bytecode:
        """Convert a statement into bytecode."""
        script = Bytecode()

        match statement:
            case EmptyStatement():
                return script

            case AssignmentStatement():
                target_type = self.resolver.type_of(statement.target)

                if target_type.category is TypeCategory.BOOL:
                    script += ScriptOpcode.LET_BOOL
                else:
                    script += ScriptOpcode.LET

                script += self.emit_expression(statement.target)
                script += self.emit_expression(statement.value)
                return script

            case ReturnStatement():
                script += ScriptOpcode.RETURN

                if statement.value is None:
                    script += ScriptOpcode.NOTHING
                else:
                    script += self.emit_expression(statement.value)

                return script

            case ExpressionStatement():
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

                    script += ScriptOpcode.EAT_RETURN_VALUE
                    script += BytecodeReference(property_reference)

                script += self.emit_expression(expression)
                return script

            case IfStatement():
                condition = self.emit_expression(statement.condition)

                with script.if_statement(condition) as branch:
                    for child in statement.then_statements:
                        script += self.emit_statement(child)

                    if statement.else_statements is not None:
                        with branch.else_statement():
                            for child in statement.else_statements:
                                script += self.emit_statement(child)

                return script

            case WhileStatement():
                condition = self.emit_expression(statement.condition)

                with script.while_statement(condition) as loop:
                    self._loops.append(loop)

                    try:
                        for child in statement.statements:
                            script += self.emit_statement(child)
                    finally:
                        self._loops.pop()

                return script

            case BreakStatement():
                if not self._loops:
                    msg = "Break statement must be inside a loop"
                    raise CompilationError(msg)

                script += self._loops[-1].break_statement()
                return script

            case ContinueStatement():
                if not self._loops:
                    msg = "Continue statement must be inside a loop"
                    raise CompilationError(msg)

                script += self._loops[-1].continue_statement()
                return script

            case ForStatement():
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

            case DoUntilStatement():
                condition = self.emit_expression(statement.condition)

                with script.do_until_statement(condition) as loop:
                    self._loops.append(loop)

                    try:
                        for child in statement.statements:
                            script += self.emit_statement(child)
                    finally:
                        self._loops.pop()

                return script

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
            if "optional" not in parameter.modifiers:
                continue

            if default is None:
                script += ScriptOpcode.NOTHING
            else:
                with script.default_parameter():
                    script += self.emit_expression(default)

        for statement in body.statements:
            script += self.emit_statement(statement)

        if not always_returns:
            script += ScriptOpcode.RETURN
            script += ScriptOpcode.NOTHING

        script += ScriptOpcode.END_OF_SCRIPT
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
