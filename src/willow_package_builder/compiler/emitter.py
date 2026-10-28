from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from willow_package_builder.bytecode import Bytecode, BytecodeReference, LoopBlock, ScriptOpcode
from willow_package_builder.logging import CompilationError
from willow_package_builder.upackage import FName, ReferencePath, UObject

from .declarations import VariableDeclaration
from .expressions import BinaryExpression, Expression, IdentifierExpression, IntegerExpression
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
from .types import TypeType
from .validation import FunctionBodyValidator

if TYPE_CHECKING:
    from .expression_resolver import ExpressionResolver
    from .package_builder import PackageBuilder


@dataclass
class FunctionEmitter:
    resolver: ExpressionResolver
    builder: PackageBuilder
    function_object: UObject

    _loops: list[LoopBlock] = field(default_factory=list, init=False, repr=False)

    def emit_expression(self, expression: Expression) -> Bytecode:
        """Convert an expression into bytecode."""
        script = Bytecode()

        match expression:
            case IntegerExpression():
                script += expression.value
                return script

            case IdentifierExpression():
                symbol = self.resolver.scope.resolve_variable(expression.name)

                resolved = self.resolver.resolve_declared_type(
                    symbol.declaration.type_ref, symbol.owner_class
                )
                if resolved.type is not TypeType.INT:
                    msg = f"Variable bytecode for type {resolved!r} is not supported yet"
                    raise CompilationError(msg)

                if (
                    isinstance(symbol.declaration, VariableDeclaration)
                    and symbol.declaration.array_dimension != 1
                ):
                    msg = f"Fixed array {expression.name!r} requires an element index"
                    raise CompilationError(msg)

                reference = self.variable_reference(expression.name)

                if symbol.type is VariableType.INSTANCE:
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
                    raise CompilationError(msg)

                for parameter in operator.parameters:
                    if "out" in parameter.modifiers or "skip" in parameter.modifiers:
                        msg = (
                            f"Operator {operator.name!r} requires unsupported "
                            "out or skip argument handling"
                        )
                        raise CompilationError(msg)

                with script.native_function(operator.native_index):
                    script += self.emit_expression(expression.left)
                    script += self.emit_expression(expression.right)

                return script

            case _:
                msg = f"Unsupported expression type: {type(expression).__name__}"
                raise TypeError(msg)

    def variable_reference(self, name: str) -> ReferencePath:
        symbol = self.resolver.scope.resolve_variable(name)
        declaration = symbol.declaration

        if symbol.type is not VariableType.INSTANCE:
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

        return self.builder.ensure_import(
            name=declaration.name, outer=outer, class_package=class_package, class_name=class_name
        )

    def emit_statement(self, statement: Statement) -> Bytecode:
        """Convert a statement into bytecode."""
        script = Bytecode()

        match statement:
            case EmptyStatement():
                return script

            case AssignmentStatement():
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
                script += self.emit_expression(statement.expression)
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

            case _:
                msg = f"Unsupported statement type: {type(statement).__name__}"
                raise TypeError(msg)

    def emit_body(self, body: FunctionBody) -> Bytecode:
        FunctionBodyValidator(self.resolver).validate(body)

        return_type = self.resolver.resolve_declared_type(
            self.resolver.scope.function.return_type, self.resolver.scope.class_path
        )

        always_returns = self.statements_return(body.statements)

        if return_type.type is not TypeType.VOID and not always_returns:
            msg = "Non-void function does not return a value on every path"
            raise CompilationError(msg)

        script = Bytecode()

        for statement in body.statements:
            script += self.emit_statement(statement)

        if not always_returns:
            script += ScriptOpcode.RETURN
            script += ScriptOpcode.NOTHING

        script += ScriptOpcode.END_OF_SCRIPT
        return script

    def statements_return(self, statements: list[Statement]) -> bool:
        for statement in statements:
            if isinstance(statement, ReturnStatement):
                return True

            if (
                isinstance(statement, IfStatement)
                and statement.else_statements is not None
                and self.statements_return(statement.then_statements)
                and self.statements_return(statement.else_statements)
            ):
                return True

        return False
