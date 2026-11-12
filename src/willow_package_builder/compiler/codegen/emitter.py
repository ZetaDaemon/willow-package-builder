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
from willow_package_builder.compiler.semantics.expression_resolver import (
    BUILTIN_CALL_SIGNATURES,
    BuiltinMember,
)
from willow_package_builder.compiler.semantics.function_body_validator import FunctionBodyValidator
from willow_package_builder.compiler.semantics.scope import VariableCategory
from willow_package_builder.compiler.semantics.types import TypeCategory
from willow_package_builder.compiler.syntax.declarations import VariableDeclaration
from willow_package_builder.compiler.syntax.expressions import (
    ArrayCountExpression,
    BinaryExpression,
    BooleanExpression,
    CallExpression,
    Expression,
    FloatExpression,
    IdentifierExpression,
    IndexExpression,
    IntegerExpression,
    MemberExpression,
    NameExpression,
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
    ForeachStatement,
    ForStatement,
    IfStatement,
    ReturnStatement,
    Statement,
    WhileStatement,
)
from willow_package_builder.games import get_game
from willow_package_builder.logging import CompilationError, declaration_context
from willow_package_builder.payloads.property_payloads import UArrayPropertyPayload
from willow_package_builder.upackage import RETURN_VALUE_NAME, FName, ReferencePath, UObject

if TYPE_CHECKING:
    from willow_package_builder.builder.classes.prepared_function import PreparedFunction
    from willow_package_builder.compiler.semantics.expression_resolver import ExpressionResolver
    from willow_package_builder.opcode import Opcodes

    from .emission_context import EmissionContext

BYTE_TO_INT_CAST = 0x3A


@dataclass
class FunctionEmitter:
    resolver: ExpressionResolver
    builder: EmissionContext
    function_object: UObject

    _loops: list[LoopBlock] = field(default_factory=list, init=False, repr=False)
    _opcodes: Opcodes = field(default_factory=lambda: get_game().OPCODES, init=False, repr=False)

    def _emit_identifier_expression(
        self, expression: IdentifierExpression, *, array_operand: bool = False
    ) -> Bytecode:
        symbol = self.resolver.scope.resolve_variable(expression.name)

        resolved = self.resolver.resolve_declared_type(
            symbol.declaration.type_ref, symbol.owner_class
        )
        if not array_operand and resolved.category not in (
            TypeCategory.INT,
            TypeCategory.BOOL,
            TypeCategory.FLOAT,
            TypeCategory.STRING,
            TypeCategory.OBJECT,
            TypeCategory.CLASS,
            TypeCategory.BYTE,
            TypeCategory.ENUM,
            TypeCategory.NAME,
            TypeCategory.ARRAY,
            TypeCategory.BYTE,
            TypeCategory.STRUCT,
        ):
            msg = f"Variable bytecode for type {resolved!r} is not supported yet"
            raise NotImplementedError(msg)

        if not array_operand and symbol.declaration.array_dimension != 1:
            msg = f"Fixed array {expression.name!r} requires an element index"
            raise CompilationError(msg)

        script = Bytecode()

        if not array_operand and resolved.category is TypeCategory.BOOL:
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
            script += self.emit_expression(
                expression.left, modifying=ParameterModifier.OUT in operator.parameters[0].modifiers
            )

            if skip_end is not None:
                origin = BytecodeLabel()

                script += self._opcodes.SKIP
                script += BytecodeRelativeJump(origin, skip_end)
                script += origin

            script += self.emit_expression(
                expression.right,
                modifying=ParameterModifier.OUT in operator.parameters[1].modifiers,
            )

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
            raise NotImplementedError(msg)

        with script.native_function(operator.native_index):
            script += self.emit_expression(
                expression.operand,
                modifying=ParameterModifier.OUT in operator.parameters[0].modifiers,
            )

        return script

    def _emit_call_body(self, expression: CallExpression) -> Bytecode:
        member = self.resolver.resolve_call(expression)
        function = member.declaration

        script = Bytecode()

        if function.native_index is not None and function.native_index != 0:
            with script.native_function(function.native_index):
                for argument, parameter in zip(
                    expression.arguments, function.parameters, strict=False
                ):
                    script += self._emit_call_argument(
                        argument, modifying=ParameterModifier.OUT in parameter.modifiers
                    )

            return script

        if (
            FunctionModifier.FINAL in function.modifiers
            or FunctionModifier.STATIC in function.modifiers
        ):
            path = member.owner_class + function.name
            reference = self.builder.function_reference(path)

            script += self._opcodes.FINAL_FUNCTION
            script += BytecodeReference(reference)
        else:
            script += self._opcodes.VIRTUAL_FUNCTION
            script += BytecodeName(function.name)

        for argument, parameter in zip(expression.arguments, function.parameters, strict=False):
            script += self._emit_call_argument(
                argument, modifying=ParameterModifier.OUT in parameter.modifiers
            )

        for _ in function.parameters[len(expression.arguments) :]:
            script += self._opcodes.EMPTY_PARAMETER_VALUE

        script += self._opcodes.END_FUNCTION_PARAMS
        return script

    def _emit_call_expression(self, expression: CallExpression) -> Bytecode:
        builtin_call = self.resolver.resolve_builtin_call(expression)

        if builtin_call is not None:
            builtin, receiver = builtin_call
            return self._emit_builtin_call(expression, builtin, receiver)

        call = self._emit_call_body(expression)

        if not isinstance(expression.callee, MemberExpression):
            return call

        result_property = self._call_return_property(expression)

        receiver = self.emit_expression(expression.callee.object)
        script = Bytecode()

        with script.object_context(receiver, result_property):
            script += call

        return script

    def _emit_member_expression(
        self, expression: MemberExpression, *, array_operand: bool = False, modifying: bool = False
    ) -> Bytecode:
        if self.resolver.resolve_builtin_member(expression) is BuiltinMember.ARRAY_LENGTH:
            script = Bytecode()
            script += self._opcodes.DYNAMIC_ARRAY_LENGTH
            script += self._emit_array_operand(expression.object)
            return script

        member = self.resolver.resolve_member(expression)
        declaration = member.declaration
        resolved = self.resolver.resolve_declared_type(declaration.type_ref, member.owner_class)

        if not array_operand and declaration.array_dimension != 1:
            msg = f"Fixed array {expression.name!r} requires an element index"
            raise CompilationError(msg)

        if not array_operand and resolved.category not in (
            TypeCategory.INT,
            TypeCategory.BOOL,
            TypeCategory.FLOAT,
            TypeCategory.STRING,
            TypeCategory.OBJECT,
            TypeCategory.BYTE,
            TypeCategory.NAME,
            TypeCategory.ARRAY,
            TypeCategory.ENUM,
            TypeCategory.STRUCT,
        ):
            msg = f"Member bytecode for type {resolved!r} is not implemented yet"
            raise NotImplementedError(msg)

        receiver_type = self.resolver.type_of(expression.object)
        if receiver_type.category is TypeCategory.STRUCT:
            struct_path = receiver_type.declaration_path
            if struct_path is None:
                msg = "Struct type has no declaration path"
                raise ValueError(msg)

            context = self.builder.context
            hierarchy = context.references.struct_hierarchy(
                struct_path, context.parents, context.packages
            )
            declaring_struct = next(
                owner + struct.name
                for owner, struct in reversed(hierarchy)
                if any(field is declaration for field in struct.variables)
            )
            reference = self.property_reference(
                member.owner_class, declaration, declaring_struct=declaring_struct
            )

            script = Bytecode()
            script += self._opcodes.STRUCT_MEMBER
            script += BytecodeReference(reference)
            script += BytecodeReference(self.builder.struct_reference(struct_path))
            # Read directly from the struct's storage without marking it modified.
            script += bytes((0, modifying))
            script += self.emit_expression(expression.object, modifying=modifying)
            return script

        reference = self.property_reference(member.owner_class, declaration)
        receiver = self.emit_expression(expression.object)

        script = Bytecode()
        with script.object_context(receiver, reference):
            if not array_operand and resolved.category is TypeCategory.BOOL:
                script += self._opcodes.BOOL_VARIABLE

            script.add_instance_variable(reference)

        return script

    def _emit_array_operand(self, expression: Expression) -> Bytecode:
        match expression:
            case IdentifierExpression():
                return self._emit_identifier_expression(expression, array_operand=True)
            case MemberExpression():
                return self._emit_member_expression(expression, array_operand=True)
            case _:
                msg = "Array operations currently require an array variable or member"
                raise NotImplementedError(msg)

    def _emit_index_expression(self, expression: IndexExpression) -> Bytecode:
        """Emit an indexed read from an array variable or member."""
        element = self.resolver.type_of(expression)
        if element.category not in (
            TypeCategory.INT,
            TypeCategory.FLOAT,
            TypeCategory.STRING,
            TypeCategory.OBJECT,
            TypeCategory.CLASS,
            TypeCategory.BYTE,
            TypeCategory.NAME,
            TypeCategory.STRUCT,
            TypeCategory.ENUM,
            TypeCategory.BOOL,
        ):
            msg = f"Indexed access to {element.category} arrays is not implemented yet"
            raise NotImplementedError(msg)

        array = self._emit_array_operand(expression.array)

        script = Bytecode()
        if self.resolver.array_dimension_of(expression.array) != 1:
            script += self._opcodes.ARRAY_ELEMENT
        else:
            script += self._opcodes.DYNAMIC_ARRAY_ELEMENT

        enum_index = self.resolver.resolve_enum_index(expression)
        if enum_index is None:
            index_type = self.resolver.type_of(expression.index)
            if index_type.category in (TypeCategory.BYTE, TypeCategory.ENUM):
                script += self._opcodes.PRIMITIVE_CAST
                script += bytes((BYTE_TO_INT_CAST,))
            script += self.emit_expression(expression.index)
        else:
            script.add_constant(enum_index)

        script += array
        return script

    def emit_expression(self, expression: Expression, *, modifying: bool = False) -> Bytecode:
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
                return self._emit_member_expression(expression, modifying=modifying)

            case SelfExpression():
                script = Bytecode()
                script += self._opcodes.SELF
                return script

            case IndexExpression():
                return self._emit_index_expression(expression)

            case NameExpression():
                script = Bytecode()
                script += self._opcodes.NAME_CONST
                script += BytecodeName(expression.value)
                return script

            case ArrayCountExpression():
                script = Bytecode()
                script.add_constant(self.resolver.resolve_array_count(expression))
                return script

            case _:
                msg = f"Unsupported expression type: {type(expression).__name__}"
                raise NotImplementedError(msg)

    def property_reference(
        self,
        owner_class: ReferencePath,
        declaration: VariableDeclaration,
        *,
        declaring_struct: ReferencePath | None = None,
    ) -> ReferencePath:
        if declaring_struct is None:
            outer = self.builder.class_object_reference(owner_class)
        else:
            outer = self.builder.struct_reference(declaring_struct)

        if owner_class.outer is None:
            msg = f"Expected fully qualified class, got {owner_class}"
            raise ValueError(msg)
        owner_package = owner_class.outer.name

        if owner_package == self.builder.config.name:
            reference = outer + declaration.name
            return self.builder.package.lookup_object_by_path(reference).reference()

        resolved = self.resolver.resolve_declared_type(declaration.type_ref, owner_class)
        property_class = self.builder.context.references.property_class(resolved)
        class_package, class_name = property_class.path.split()
        if class_package is None:
            msg = f"Expected fully qualified class, got {property_class.path}"
            raise ValueError(msg)

        return self.builder.ensure_import(declaration.name, outer, class_package.name, class_name)

    def variable_reference(self, name: FName) -> ReferencePath:
        symbol = self.resolver.scope.resolve_variable(name)
        declaration = symbol.declaration

        if symbol.category is not VariableCategory.INSTANCE:
            reference = self.function_object.reference() + declaration.name
            return self.builder.package.lookup_object_by_path(reference).reference()

        if not isinstance(declaration, VariableDeclaration):
            msg = f"Instance variable {name!r} has no VariableDeclaration"
            raise TypeError(msg)

        return self.property_reference(symbol.owner_class, declaration)

    def _emit_assignment_statement(
        self, statement: AssignmentStatement, *, modifying: bool = False
    ) -> Bytecode:
        script = Bytecode()
        target_type = self.resolver.type_of(statement.target)

        match target_type.category:
            case TypeCategory.ARRAY:
                if (
                    self.resolver.array_dimension_of(statement.target) != 1
                    or self.resolver.array_dimension_of(statement.value) != 1
                ):
                    msg = "Whole-array assignment currently requires dynamic arrays"
                    raise NotImplementedError(msg)

                script += self._opcodes.LET
                script += self._emit_array_operand(statement.target)
                script += self.emit_expression(statement.value)
                return script

            case TypeCategory.BOOL:
                script += self._opcodes.LET_BOOL

            case _:
                script += self._opcodes.LET

        script += self.emit_expression(statement.target, modifying=True)
        script += self.emit_expression(statement.value)
        return script

    def _emit_return_statement(self, statement: ReturnStatement) -> Bytecode:
        script = Bytecode()
        for loop in reversed(self._loops):
            if loop.iterator:
                script += self._opcodes.ITERATOR_POP
        script += self._opcodes.RETURN

        if statement.value is None:
            script += self._opcodes.NOTHING
        else:
            script += self.emit_expression(statement.value)

        return script

    def _emit_expression_statement(self, statement: ExpressionStatement) -> Bytecode:
        script = Bytecode()
        expression = statement.expression

        if isinstance(expression, CallExpression):
            builtin_call = self.resolver.resolve_builtin_call(expression)
            if builtin_call is not None:
                builtin, receiver = builtin_call
                if builtin is BuiltinMember.ARRAY_SORT:
                    inner = self._sort_result_property(receiver)
                    script += self._opcodes.EAT_RETURN_VALUE
                    script += BytecodeReference(inner)
                    script += self.emit_expression(expression)
                    return script

        result_type = self.resolver.type_of(expression)

        if result_type.category in (TypeCategory.STRING, TypeCategory.ARRAY):
            match expression:
                case CallExpression():
                    property_reference = self._call_return_property(expression)

                case BinaryExpression(left=IdentifierExpression() as target) if (
                    result_type.category is TypeCategory.STRING
                    and self.resolver.type_of(target).category is TypeCategory.STRING
                ):
                    property_reference = self.variable_reference(target.name)

                case _:
                    msg = (
                        f"Discarding this {result_type.category} expression is not implemented yet"
                    )
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

    def _emit_foreach_statement(self, statement: ForeachStatement) -> Bytecode:
        iterator = statement.iterator
        array = self._emit_array_operand(iterator.callee)
        item = iterator.arguments[0]
        index = iterator.arguments[1] if len(iterator.arguments) == 2 else None

        if item is None:
            msg = "Array foreach requires an item output"
            raise CompilationError(msg)

        script = Bytecode()
        item_code = self.emit_expression(item)
        index_code = None if index is None else self.emit_expression(index)

        with script.array_foreach(array, item_code, index_code) as loop:
            self._loops.append(loop)
            try:
                for child in statement.statements:
                    script += self.emit_statement(child)
            finally:
                self._loops.pop()

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

    def _emit_statement(self, statement: Statement) -> Bytecode:
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

            case ForeachStatement():
                return self._emit_foreach_statement(statement)

            case _:
                msg = f"Unsupported statement type: {type(statement).__name__}"
                raise TypeError(msg)

    def emit_statement(self, statement: Statement) -> Bytecode:
        scope = self.resolver.scope
        path = scope.class_path + scope.function.name

        with declaration_context(path, statement.location):
            return self._emit_statement(statement)

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

    def _emit_builtin_call(
        self, expression: CallExpression, builtin: BuiltinMember, receiver: Expression
    ) -> Bytecode:
        opcodes = {
            BuiltinMember.ARRAY_ADD: self._opcodes.DYNAMIC_ARRAY_ADD,
            BuiltinMember.ARRAY_ADD_ITEM: self._opcodes.DYNAMIC_ARRAY_ADD_ITEM,
            BuiltinMember.ARRAY_INSERT: self._opcodes.DYNAMIC_ARRAY_INSERT,
            BuiltinMember.ARRAY_REMOVE: self._opcodes.DYNAMIC_ARRAY_REMOVE,
            BuiltinMember.ARRAY_INSERT_ITEM: self._opcodes.DYNAMIC_ARRAY_INSERT_ITEM,
            BuiltinMember.ARRAY_REMOVE_ITEM: self._opcodes.DYNAMIC_ARRAY_REMOVE_ITEM,
            BuiltinMember.ARRAY_FIND: self._opcodes.DYNAMIC_ARRAY_FIND,
            BuiltinMember.ARRAY_FIND_STRUCT: self._opcodes.DYNAMIC_ARRAY_FIND_STRUCT,
            BuiltinMember.ARRAY_SORT: self._opcodes.DYNAMIC_ARRAY_SORT,
        }
        signature = BUILTIN_CALL_SIGNATURES[builtin]
        arguments = self.resolver.require_builtin_arguments(expression, len(signature.arguments))

        script = Bytecode()
        script += opcodes[builtin]
        script += self._emit_array_operand(receiver)
        end: BytecodeLabel | None = None

        if builtin in (
            BuiltinMember.ARRAY_ADD_ITEM,
            BuiltinMember.ARRAY_INSERT_ITEM,
            BuiltinMember.ARRAY_REMOVE_ITEM,
            BuiltinMember.ARRAY_FIND,
            BuiltinMember.ARRAY_FIND_STRUCT,
            BuiltinMember.ARRAY_SORT,
        ):
            origin = BytecodeLabel()
            end = BytecodeLabel()
            script += BytecodeRelativeJump(origin, end)
            script += origin

        if builtin is BuiltinMember.ARRAY_SORT:
            comparator = self.resolver.resolve_array_sort_comparator(
                self.resolver.type_of(receiver), arguments[0]
            )
            script += self._opcodes.INSTANCE_DELEGATE
            script += BytecodeName(comparator.declaration.name)
        else:
            for argument in arguments:
                script += self.emit_expression(argument)

        script += self._opcodes.END_FUNCTION_PARAMS

        if end is not None:
            script += end

        return script

    def _sort_result_property(self, receiver: Expression) -> ReferencePath:
        match receiver:
            case IdentifierExpression():
                reference = self.variable_reference(receiver.name)

            case MemberExpression():
                member = self.resolver.resolve_member(receiver)
                reference = self.property_reference(member.owner_class, member.declaration)

            case _:
                msg = "Discarding Sort results requires an array variable or member"
                raise NotImplementedError(msg)

        obj = self.builder.package.lookup_object_by_path(reference)
        if not isinstance(obj, UObject) or not isinstance(obj.payload, UArrayPropertyPayload):
            msg = "Discarding Sort results requires an array property exported by this package"
            raise NotImplementedError(msg)

        return obj.payload.inner

    def _call_return_property(self, expression: CallExpression) -> ReferencePath:
        """Resolve the property used to store and clean up a call result."""
        member = self.resolver.resolve_call(expression)
        result_type = self.resolver.resolve_declared_type(
            member.declaration.return_type, member.owner_class
        )

        if result_type.category is TypeCategory.VOID:
            return ReferencePath()

        path = member.owner_class + member.declaration.name
        function_reference = self.builder.function_reference(path)
        owner_package = member.owner_class.get_outer().name

        if owner_package == self.builder.config.name:
            reference = function_reference + RETURN_VALUE_NAME
            return self.builder.package.lookup_object_by_path(reference).reference()

        property_class = self.builder.context.references.property_class(result_type)
        class_package, class_name = property_class.path.split(require_outer=True)
        return self.builder.ensure_import(
            RETURN_VALUE_NAME, function_reference, class_package.name, class_name
        )

    def _emit_call_argument(
        self, argument: Expression | None, *, modifying: bool = False
    ) -> Bytecode:
        if argument is None:
            script = Bytecode()
            script += self._opcodes.EMPTY_PARAMETER_VALUE
            return script

        if self.resolver.array_dimension_of(argument) != 1:
            return self._emit_array_operand(argument)

        return self.emit_expression(argument, modifying=modifying)
