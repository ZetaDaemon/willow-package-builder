from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Literal

from willow_package_builder.compiler.semantics.reference_database import PRIMITIVE_TYPES
from willow_package_builder.compiler.syntax.declarations import (
    FunctionDeclaration,
    OperatorCategory,
    ParameterDeclaration,
    TypeReference,
    VariableDeclaration,
)
from willow_package_builder.compiler.syntax.expressions import (
    ArrayCountExpression,
    BinaryExpression,
    BooleanExpression,
    CallExpression,
    CastExpression,
    ClassLiteralExpression,
    ConditionalExpression,
    EnumMemberExpression,
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
from willow_package_builder.compiler.syntax.lexer import Token, TokenCategory
from willow_package_builder.compiler.syntax.modifiers import FunctionModifier, ParameterModifier
from willow_package_builder.compiler.syntax.punctuation import Operator
from willow_package_builder.games import get_game
from willow_package_builder.logging import (
    CompilationError,
    UnknownPropertyError,
    declaration_context,
)
from willow_package_builder.package_config import collect_visible_packages
from willow_package_builder.upackage import (
    CORE_OBJECT_PATH,
    CORE_VECTOR_PATH,
    ENGINE_ACTOR_PATH,
    FName,
    ReferencePath,
)

from .reference_database import ResolvedMember
from .types import ResolvedType, TypeCategory

if TYPE_CHECKING:
    from willow_package_builder.builder.build_context import BuildContext
    from willow_package_builder.compiler.syntax.declarations import OperatorDeclaration
    from willow_package_builder.compiler.syntax.keyword import Keyword
    from willow_package_builder.compiler.syntax.statements import AssignmentStatement
    from willow_package_builder.opcode import Opcode

    from .scope import FunctionScope


class BuiltinMember(Enum):
    ARRAY_LENGTH = auto()
    ARRAY_ADD = auto()
    ARRAY_ADD_ITEM = auto()
    ARRAY_INSERT = auto()
    ARRAY_REMOVE = auto()
    ARRAY_INSERT_ITEM = auto()
    ARRAY_REMOVE_ITEM = auto()
    ARRAY_FIND = auto()
    ARRAY_FIND_STRUCT = auto()
    ARRAY_SORT = auto()


BUILTIN_MEMBERS = {
    (TypeCategory.ARRAY, FName("Length")): BuiltinMember.ARRAY_LENGTH,
    (TypeCategory.ARRAY, FName("Add")): BuiltinMember.ARRAY_ADD,
    (TypeCategory.ARRAY, FName("AddItem")): BuiltinMember.ARRAY_ADD_ITEM,
    (TypeCategory.ARRAY, FName("Insert")): BuiltinMember.ARRAY_INSERT,
    (TypeCategory.ARRAY, FName("Remove")): BuiltinMember.ARRAY_REMOVE,
    (TypeCategory.ARRAY, FName("InsertItem")): BuiltinMember.ARRAY_INSERT_ITEM,
    (TypeCategory.ARRAY, FName("RemoveItem")): BuiltinMember.ARRAY_REMOVE_ITEM,
    (TypeCategory.ARRAY, FName("Find")): BuiltinMember.ARRAY_FIND,
    (TypeCategory.ARRAY, FName("Sort")): BuiltinMember.ARRAY_SORT,
}

STATIC_MEMBER_NAME = FName("static")


@dataclass(frozen=True)
class BuiltinCallSignature:
    """A call signature; None in the arguments denotes the array element type."""

    result: TypeCategory | None
    arguments: tuple[TypeCategory | None, ...]
    mutates_receiver: bool = field(default=True, kw_only=True)


BUILTIN_CALL_SIGNATURES = {
    BuiltinMember.ARRAY_ADD: BuiltinCallSignature(TypeCategory.INT, (TypeCategory.INT,)),
    BuiltinMember.ARRAY_ADD_ITEM: BuiltinCallSignature(TypeCategory.INT, (None,)),
    BuiltinMember.ARRAY_INSERT: BuiltinCallSignature(
        TypeCategory.VOID, (TypeCategory.INT, TypeCategory.INT)
    ),
    BuiltinMember.ARRAY_REMOVE: BuiltinCallSignature(
        TypeCategory.VOID, (TypeCategory.INT, TypeCategory.INT)
    ),
    BuiltinMember.ARRAY_INSERT_ITEM: BuiltinCallSignature(
        TypeCategory.INT, (TypeCategory.INT, None)
    ),
    BuiltinMember.ARRAY_REMOVE_ITEM: BuiltinCallSignature(TypeCategory.INT, (None,)),
    BuiltinMember.ARRAY_FIND: BuiltinCallSignature(
        TypeCategory.INT, (None,), mutates_receiver=False
    ),
    BuiltinMember.ARRAY_FIND_STRUCT: BuiltinCallSignature(
        TypeCategory.INT, (TypeCategory.NAME, None), mutates_receiver=False
    ),
    BuiltinMember.ARRAY_SORT: BuiltinCallSignature(None, (TypeCategory.DELEGATE,)),
}


@dataclass
class ExpressionResolver:
    context: BuildContext
    scope: FunctionScope

    _visibility: dict[FName, set[FName]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._visibility = {
            config.name: collect_visible_packages(config, self.context.packages)
            for config in self.context.packages
        }

    def resolve_declared_type(
        self, type_ref: TypeReference | None, owner_class: ReferencePath
    ) -> ResolvedType:
        if owner_class.outer is None:
            msg = f"Expected fully qualified class, got {owner_class}"
            raise ValueError(msg)
        package_name = owner_class.outer.name

        return self.context.references.resolve_type(
            type_ref, owner_class, self._visibility[package_name], self.context.parents
        )

    def resolve_operator(self, expression: BinaryExpression) -> ResolvedMember[OperatorDeclaration]:
        left = self.type_of(expression.left)
        right = self.type_of(expression.right)
        if self.scope.class_path.outer is None:
            msg = f"Expected fully qualified class, got {self.scope.class_path}"
            raise ValueError(msg)
        package_name = self.scope.class_path.outer.name

        return self.context.references.resolve_binary_operator(
            expression.operator,
            left,
            right,
            self.scope.class_path,
            self._visibility[package_name],
            self.context.parents,
        )

    def primitive_cast_selector(self, source: ResolvedType, target: ResolvedType) -> Opcode | None:
        selectors = get_game().PRIMITIVE_CAST_SELECTORS

        match source.category:
            case TypeCategory.FLOAT:
                match target.category:
                    case TypeCategory.INT:
                        return selectors.FLOAT_TO_INT
                    case TypeCategory.BYTE:
                        return selectors.FLOAT_TO_BYTE
                    case TypeCategory.BOOL:
                        return selectors.FLOAT_TO_BOOL
                    case _:
                        pass

            case TypeCategory.INT:
                match target.category:
                    case TypeCategory.FLOAT:
                        return selectors.INT_TO_FLOAT
                    case TypeCategory.BYTE:
                        return selectors.INT_TO_BYTE
                    case TypeCategory.BOOL:
                        return selectors.INT_TO_BOOL
                    case _:
                        pass

            case TypeCategory.BYTE:
                match target.category:
                    case TypeCategory.FLOAT:
                        return selectors.BYTE_TO_FLOAT
                    case TypeCategory.INT:
                        return selectors.BYTE_TO_INT
                    case TypeCategory.BOOL:
                        return selectors.BYTE_TO_BOOL
                    case _:
                        pass

            case TypeCategory.BOOL:
                match target.category:
                    case TypeCategory.FLOAT:
                        return selectors.BOOL_TO_FLOAT
                    case TypeCategory.INT:
                        return selectors.BOOL_TO_INT
                    case TypeCategory.BYTE:
                        return selectors.BOOL_TO_BYTE
                    case _:
                        pass

            case _:
                pass

        return None

    def parameter_cast_selector(
        self, expression: Expression, parameter: ParameterDeclaration, owner: ReferencePath
    ) -> Opcode | None:
        if (
            ParameterModifier.OUT in parameter.modifiers
            or parameter.array_dimension != 1
            or self.array_dimension_of(expression) != 1
        ):
            return None

        source = self.type_of(expression)
        target = self.resolve_declared_type(parameter.type_ref, owner)

        if ParameterModifier.COERCE in parameter.modifiers:
            return self.primitive_cast_selector(source, target)

        return self.implicit_numeric_cast_selector(source, target)

    def implicit_numeric_cast_selector(
        self, source: ResolvedType, target: ResolvedType
    ) -> Opcode | None:
        numeric = (TypeCategory.BYTE, TypeCategory.INT, TypeCategory.FLOAT)
        if source.category in numeric and target.category in numeric:
            return self.primitive_cast_selector(source, target)

        return None

    def assignment_cast_selector(self, statement: AssignmentStatement) -> Opcode | None:
        if (
            self.array_dimension_of(statement.target) != 1
            or self.array_dimension_of(statement.value) != 1
        ):
            return None

        return self.implicit_numeric_cast_selector(
            self.type_of(statement.value), self.type_of(statement.target)
        )

    def resolve_return_cast(
        self, expression: Expression, source: ResolvedType, target: ResolvedType
    ) -> Opcode | None:
        if self.array_dimension_of(expression) == 1:
            if self.accepts_value_type(target, source):
                return None

            selector = self.implicit_numeric_cast_selector(source, target)
            if selector is not None:
                return selector

        msg = f"Return type mismatch: expected {target}, got {source}"
        raise CompilationError(msg)

    def is_object_cast_target(self, name: FName) -> bool:
        class_path = self.scope.class_path
        references = self.context.references

        for _, declaration in references.iter_class_hierarchy(class_path, self.context.parents):
            if any(function.name == name for function in declaration.functions):
                return False

        package = class_path.get_outer().name
        return any(
            ReferencePath(package_name) + name in references.classes
            for package_name in self._visibility[package] | {package}
        )

    def resolve_object_cast(self, expression: CastExpression) -> ReferencePath:
        target = self.resolve_declared_type(expression.target, self.scope.class_path)
        source = self.type_of(expression.operand)

        if (
            target.category is not TypeCategory.OBJECT
            or target.declaration_path is None
            or source.category is not TypeCategory.OBJECT
            or self.array_dimension_of(expression.operand) != 1
        ):
            msg = f"Object cast requires a scalar object operand and a class target: {target!r}"
            raise CompilationError(msg)

        return target.declaration_path

    def resolve_primitive_cast(
        self, expression: CastExpression
    ) -> tuple[ResolvedType, Opcode | None]:
        source = self.type_of(expression.operand)
        target = self.resolve_declared_type(expression.target, self.scope.class_path)

        if self.array_dimension_of(expression.operand) != 1:
            msg = "A primitive cast requires a scalar operand"
            raise CompilationError(msg)

        if source == target:
            return target, None

        selector = self.primitive_cast_selector(source, target)
        if selector is None:
            msg = f"Casting {source.category} to {target.category} is not implemented yet"
            raise NotImplementedError(msg)

        return target, selector

    def resolve_qualified_enum_member(
        self, enum_name: FName, member_name: FName
    ) -> EnumMemberExpression | None:
        try:
            self.scope.resolve_variable(enum_name)
        except UnknownPropertyError:
            pass
        else:
            return None

        references = self.context.references
        parents = self.context.parents
        resolved = references.find_member_type(self.scope.class_path, enum_name, parents)
        if resolved is None or resolved.category is not TypeCategory.ENUM:
            return None

        path = resolved.declaration_path
        if path is None:
            msg = f"Enum {enum_name} has no declaration path"
            raise ValueError(msg)

        owner, name = path.split(require_outer=True)
        enum = references.resolve_enum(owner, name, parents).declaration
        if member_name not in enum.members:
            msg = f"Unknown enum member {member_name} in {path}"
            raise CompilationError(msg)

        return EnumMemberExpression(path, enum.members.index(member_name))

    def resolve_enum_member_hint(
        self, name: FName, enum_path: ReferencePath
    ) -> EnumMemberExpression | None:
        try:
            self.scope.resolve_variable(name)
        except UnknownPropertyError:
            pass
        else:
            return None

        owner, enum_name = enum_path.split(require_outer=True)
        enum = self.context.references.resolve_enum(
            owner, enum_name, self.context.parents
        ).declaration
        if name not in enum.members:
            return None

        return EnumMemberExpression(enum_path, enum.members.index(name))

    def resolve_integer_constant(self, name: FName) -> IntegerExpression | None:
        try:
            self.scope.resolve_variable(name)
        except UnknownPropertyError:
            pass
        else:
            return None

        for owner, declaration in self.context.references.iter_class_hierarchy(
            self.scope.class_path, self.context.parents
        ):
            for constant in declaration.constants:
                if constant.name != name:
                    continue

                match constant.value_tokens:
                    case [Token(category=TokenCategory.INTEGER) as value]:
                        return IntegerExpression(int(value))

                    case [sign, Token(category=TokenCategory.INTEGER) as value] if (
                        sign == Operator.SUBTRACT
                    ):
                        return IntegerExpression(-int(value))

                msg = f"Constant {owner + name} must be an integer literal in function expressions"
                raise NotImplementedError(msg)

        return None

    def resolve_bare_enum_member(self, name: FName) -> EnumMemberExpression | None:
        try:
            self.scope.resolve_variable(name)
        except UnknownPropertyError:
            pass
        else:
            return None

        for owner, declaration in self.context.references.iter_class_hierarchy(
            self.scope.class_path, self.context.parents
        ):
            matches = [enum for enum in declaration.enums if name in enum.members]
            if len(matches) > 1:
                msg = f"Ambiguous enum member {name} on {owner}"
                raise CompilationError(msg)

            if matches:
                enum = matches[0]
                return EnumMemberExpression(owner + enum.name, enum.members.index(name))

        return None

    def type_of(self, expression: Expression) -> ResolvedType:
        match expression:
            case ClassLiteralExpression(path=path):
                target = ResolvedType(TypeCategory.OBJECT, self.resolve_class_literal(path))
                return ResolvedType(TypeCategory.CLASS, arguments=(target,))

            case NewExpression():
                target = self.resolve_class_literal(expression.object_class.path)
                outer = self.type_of(expression.outer)
                references = self.context.references
                parents = self.context.parents

                if (
                    outer.category is not TypeCategory.OBJECT
                    or outer.declaration_path is None
                    or self.array_dimension_of(expression.outer) != 1
                ):
                    msg = "new requires a scalar object as its outer"
                    raise CompilationError(msg)

                if ENGINE_ACTOR_PATH in references.classes and references.is_subclass(
                    target, ENGINE_ACTOR_PATH, parents
                ):
                    msg = f"Use Spawn to construct actor class {target}"
                    raise CompilationError(msg)

                if references.classes[target].is_abstract:
                    msg = f"Cannot construct abstract class {target}"
                    raise CompilationError(msg)

                within = references.resolve_within_class(target, parents, self.context.packages)
                if not references.is_subclass(outer.declaration_path, within, parents):
                    msg = f"new {target} requires an outer of type {within}, got {outer}"
                    raise CompilationError(msg)

                return ResolvedType(TypeCategory.OBJECT, target)

            case IntegerExpression():
                return ResolvedType(TypeCategory.INT)

            case BooleanExpression():
                return ResolvedType(TypeCategory.BOOL)

            case FloatExpression():
                return ResolvedType(TypeCategory.FLOAT)

            case StringExpression():
                return ResolvedType(TypeCategory.STRING)

            case IdentifierExpression():
                symbol = self.scope.resolve_variable(expression.name)
                return self.resolve_declared_type(symbol.declaration.type_ref, symbol.owner_class)

            case BinaryExpression():
                operator = self.resolve_operator(expression)

                return self.resolve_declared_type(
                    operator.declaration.return_type, operator.owner_class
                )

            case UnaryExpression():
                operator = self.resolve_unary_operator(expression)

                return self.resolve_declared_type(
                    operator.declaration.return_type, operator.owner_class
                )

            case CastExpression():
                if expression.target.name not in PRIMITIVE_TYPES:
                    return ResolvedType(TypeCategory.OBJECT, self.resolve_object_cast(expression))

                target, _ = self.resolve_primitive_cast(expression)
                return target

            case CallExpression():
                builtin_call = self.resolve_builtin_call(expression)

                if builtin_call is not None:
                    member, receiver = builtin_call
                    result = BUILTIN_CALL_SIGNATURES[member].result
                    if result is None:
                        return self.type_of(receiver).arguments[0]

                    return ResolvedType(result)

                function = self.resolve_call(expression)

                return self.resolve_declared_type(
                    function.declaration.return_type, function.owner_class
                )

            case MemberExpression():
                if self.resolve_builtin_member(expression) is BuiltinMember.ARRAY_LENGTH:
                    return ResolvedType(TypeCategory.INT)

                member = self.resolve_member(expression)

                return self.resolve_declared_type(member.declaration.type_ref, member.owner_class)

            case SelfExpression():
                return ResolvedType(TypeCategory.OBJECT, self.scope.class_path)

            case NoneExpression():
                return ResolvedType(TypeCategory.OBJECT, CORE_OBJECT_PATH)

            case IndexExpression():
                if self.resolve_enum_index(expression) is None and (
                    self.array_dimension_of(expression.index) != 1
                    or self.type_of(expression.index).category
                    not in (TypeCategory.INT, TypeCategory.BYTE, TypeCategory.ENUM)
                ):
                    msg = "Array index must be a scalar int, byte, or enum"
                    raise CompilationError(msg)

                array_type = self.type_of(expression.array)

                if self.array_dimension_of(expression.array) != 1:
                    # A fixed array's declared type is already its element type.
                    return array_type

                if array_type.category is TypeCategory.ARRAY:
                    return array_type.arguments[0]

                msg = "Cannot index a value that is not an array"
                raise CompilationError(msg)

            case NameExpression():
                return ResolvedType(TypeCategory.NAME)

            case ArrayCountExpression():
                self.resolve_array_count(expression)
                return ResolvedType(TypeCategory.INT)

            case EnumMemberExpression(enum_path=path):
                return ResolvedType(TypeCategory.ENUM, path)

            case ConditionalExpression():
                condition_type = self.type_of(expression.condition)
                if condition_type.category is not TypeCategory.BOOL:
                    msg = "Conditional expression requires a bool condition"
                    raise CompilationError(msg)

                true_type = self.type_of(expression.when_true)
                false_type = self.type_of(expression.when_false)

                if (
                    isinstance(expression.when_true, NoneExpression)
                    and false_type.category is TypeCategory.OBJECT
                ):
                    return false_type

                if (
                    isinstance(expression.when_false, NoneExpression)
                    and true_type.category is TypeCategory.OBJECT
                ):
                    return true_type

                if true_type != false_type:
                    msg = f"Conditional branches must match, got {true_type!r} and {false_type!r}"
                    raise CompilationError(msg)

                return true_type

            case VectorExpression():
                return ResolvedType(TypeCategory.STRUCT, CORE_VECTOR_PATH)

            case _:
                msg = f"Unsupported expression type: {type(expression).__name__}"
                raise NotImplementedError(msg)

    def binary_precedence(self, name: Operator | Keyword, left: ResolvedType) -> int | None:
        precedences: set[int] = set()

        # A declaration on a derived class takes priority over an inherited
        # declaration with the same operand types.
        seen_right_types: set[ResolvedType] = set()

        for owner, declaration in self.context.references.iter_class_hierarchy(
            self.scope.class_path, self.context.parents
        ):
            for operator in declaration.operators:
                if operator.op_category is not OperatorCategory.BINARY or operator.name != name:
                    continue

                left_type = self.resolve_declared_type(operator.parameters[0].type_ref, owner)

                if (
                    self.context.references.binary_operand_cost(
                        name,
                        left,
                        left_type,
                        out=ParameterModifier.OUT in operator.parameters[0].modifiers,
                    )
                    is None
                ):
                    continue

                right_type = self.resolve_declared_type(operator.parameters[1].type_ref, owner)

                if right_type in seen_right_types:
                    continue

                seen_right_types.add(right_type)

                if operator.precedence is None:
                    msg = f"Binary operator {name!r} on {owner} has no precedence"
                    raise CompilationError(msg)

                precedences.add(operator.precedence)

        if not precedences:
            return None

        if len(precedences) > 1:
            msg = (
                f"Cannot determine precedence for {name!r} from "
                f"left operand type {left!r}; right-dependent precedence "
                "is not supported yet"
            )
            raise NotImplementedError(msg)

        return next(iter(precedences))

    def resolve_unary_operator(
        self, expression: UnaryExpression
    ) -> ResolvedMember[OperatorDeclaration]:
        operand = self.type_of(expression.operand)
        if self.scope.class_path.outer is None:
            msg = f"Expected fully qualified class, got {self.scope.class_path}"
            raise ValueError(msg)
        package_name = self.scope.class_path.outer.name

        return self.context.references.resolve_unary_operator(
            expression.operator,
            expression.op_category,
            operand,
            self.scope.class_path,
            self._visibility[package_name],
            self.context.parents,
        )

    def has_unary_operator(
        self,
        name: Operator | Keyword,
        category: Literal[OperatorCategory.PREFIX, OperatorCategory.POSTFIX],
    ) -> bool:

        for _, declaration in self.context.references.iter_class_hierarchy(
            self.scope.class_path, self.context.parents
        ):
            if any(
                operator.op_category is category and operator.name == name
                for operator in declaration.operators
            ):
                return True

        return False

    def resolve_class_literal(self, path: ReferencePath) -> ReferencePath:
        package_name = self.scope.class_path.get_outer().name
        return self.context.references.resolve_class_path(
            path, package_name, self._visibility[package_name]
        )

    def resolve_static_call_class(self, expression: CallExpression) -> ReferencePath | None:
        match expression.callee:
            case MemberExpression(
                object=MemberExpression(object=ClassLiteralExpression(path=path), name=qualifier)
            ) if qualifier == STATIC_MEMBER_NAME:
                return self.resolve_class_literal(path)

            case _:
                return None

    def resolve_state_function(self, name: FName) -> ResolvedMember[FunctionDeclaration] | None:
        state_name = self.scope.state_name
        if state_name is None:
            return None

        for owner, declaration in self.context.references.iter_class_hierarchy(
            self.scope.class_path, self.context.parents
        ):
            for state in declaration.states:
                if state.name != state_name:
                    continue

                for function in state.functions:
                    if function.name == name:
                        if (
                            FunctionModifier.FINAL in function.modifiers
                            or FunctionModifier.STATIC in function.modifiers
                        ):
                            msg = f"Direct calls to state functions are not supported: {owner + state.name + name}"
                            raise NotImplementedError(msg)

                        return ResolvedMember(owner, function)

        return None

    def resolve_unqualified_super(self, name: FName) -> ResolvedMember[FunctionDeclaration]:
        class_path = self.scope.class_path
        state_name = self.scope.state_name
        parents = self.context.parents
        references = self.context.references
        parent = parents[class_path]

        if state_name is not None:
            class_scope = class_path

            if parent is not None:
                for owner, declaration in references.iter_class_hierarchy(parent, parents):
                    for state in declaration.states:
                        if state.name != state_name:
                            continue

                        if class_scope == class_path:
                            class_scope = owner

                        for function in state.functions:
                            if function.name == name:
                                return ResolvedMember(owner, function, state_name=state.name)

            return references.resolve_function(class_scope, name, parents)

        if parent is None:
            msg = f"Cannot call super.{name} because {class_path} has no superclass"
            raise CompilationError(msg)

        return references.resolve_function(parent, name, parents)

    def resolve_call(self, expression: CallExpression) -> ResolvedMember[FunctionDeclaration]:
        static_class = self.resolve_static_call_class(expression)
        if static_class is not None and isinstance(expression.callee, MemberExpression):
            member = self.context.references.resolve_function(
                static_class, expression.callee.name, self.context.parents
            )
            if FunctionModifier.STATIC not in member.declaration.modifiers:
                msg = f"{static_class}.{member.declaration.name} is not static"
                raise CompilationError(msg)

            return member

        match expression.callee:
            case GlobalExpression(name=name):
                return self.context.references.resolve_function(
                    self.scope.class_path, name, self.context.parents
                )

            case SuperExpression(ancestor=None, name=name):
                return self.resolve_unqualified_super(name)

            case SuperExpression(ancestor=ancestor, name=name):
                class_path = self.scope.class_path
                parent = self.context.parents[class_path]
                references = self.context.references

                while parent is not None:
                    if parent.name == ancestor:
                        return references.resolve_function(parent, name, self.context.parents)

                    parent = self.context.parents[parent]

                msg = f"{ancestor} is not a superclass of {class_path}"
                raise CompilationError(msg)

            case IdentifierExpression(name=name):
                state_function = self.resolve_state_function(name)
                if state_function is not None:
                    return state_function

                return self.context.references.resolve_function(
                    self.scope.class_path, name, self.context.parents
                )

            case MemberExpression():
                receiver = self.type_of(expression.callee.object)

                if receiver.category is not TypeCategory.OBJECT:
                    msg = f"Function calls on {receiver.category.value} are not implemented yet"
                    raise NotImplementedError(msg)

                if receiver.declaration_path is None:
                    msg = "Object type has no declaring class"
                    raise ValueError(msg)

                return self.context.references.resolve_function(
                    receiver.declaration_path, expression.callee.name, self.context.parents
                )

            case _:
                msg = "This function-call target is not implemented yet"
                raise NotImplementedError(msg)

    def resolve_member(self, expression: MemberExpression) -> ResolvedMember[VariableDeclaration]:
        receiver = self.type_of(expression.object)
        if receiver.category is TypeCategory.STRUCT:
            struct_path = receiver.declaration_path
            if struct_path is None:
                msg = "Struct type has no declaration path"
                raise ValueError(msg)

            package_name = struct_path.get_outer().get_outer().name
            return self.context.references.resolve_struct_variable(
                struct_path, expression.name, self.context.parents, self._visibility[package_name]
            )

        if receiver.category is not TypeCategory.OBJECT:
            msg = f"Member access for {receiver.category.value} is not implemented yet"
            raise NotImplementedError(msg)

        if receiver.declaration_path is None:
            msg = "Object type has no declaring class"
            raise ValueError(msg)

        return self.context.references.resolve_variable(
            receiver.declaration_path, expression.name, self.context.parents
        )

    def resolve_local_array_dimension(self, declaration: VariableDeclaration) -> None:
        name = declaration.array_dimension_name

        if name is None:
            return

        class_path = self.scope.class_path
        if class_path.outer is None:
            msg = f"Expected fully qualified class, got {class_path}"
            raise ValueError(msg)

        package_name = class_path.outer.name

        owner = class_path
        path = owner + self.scope.function.name + declaration.name

        with declaration_context(path, declaration.location):
            declaration.array_dimension = self.context.references.resolve_array_dimension(
                name, class_path, self._visibility[package_name], self.context.parents
            )

    def array_dimension_of(self, expression: Expression) -> int:
        """Return the declared fixed-array dimension, or 1 for other expressions."""
        match expression:
            case IdentifierExpression():
                declaration = self.scope.resolve_variable(expression.name).declaration
                return declaration.array_dimension

            case MemberExpression():
                if self.resolve_builtin_member(expression) is BuiltinMember.ARRAY_LENGTH:
                    return 1

                return self.resolve_member(expression).declaration.array_dimension

            case _:
                return 1

    def resolve_array_count(self, expression: ArrayCountExpression) -> int:
        """Get the fixed array's compile-time element count."""
        dimension = self.array_dimension_of(expression.array)

        if dimension <= 1:
            msg = "ArrayCount requires a fixed array"
            raise CompilationError(msg)

        return dimension

    def resolve_builtin_member(self, expression: MemberExpression) -> BuiltinMember | None:
        """Resolve a built-in member by receiver type and name."""
        receiver = expression.object
        category = self.type_of(receiver).category
        member = BUILTIN_MEMBERS.get((category, expression.name))

        if member is not None and self.array_dimension_of(receiver) == 1:
            return member

        return None

    def resolve_builtin_call(
        self, expression: CallExpression
    ) -> tuple[BuiltinMember, Expression] | None:
        callee = expression.callee

        if not isinstance(callee, MemberExpression):
            return None

        if self.resolve_static_call_class(expression) is not None:
            return None

        member = self.resolve_builtin_member(callee)

        if member is None:
            return None

        if member is BuiltinMember.ARRAY_FIND and len(expression.arguments) == len(
            BUILTIN_CALL_SIGNATURES[BuiltinMember.ARRAY_FIND_STRUCT].arguments
        ):
            member = BuiltinMember.ARRAY_FIND_STRUCT

        if member not in BUILTIN_CALL_SIGNATURES:
            msg = f"Built-in member {callee.name} is not callable"
            raise CompilationError(msg)

        return member, callee.object

    @staticmethod
    def require_builtin_arguments(expression: CallExpression, arity: int) -> list[Expression]:
        arguments = [argument for argument in expression.arguments if argument is not None]

        if len(expression.arguments) != arity or len(arguments) != arity:
            msg = f"Built-in call requires {arity} arguments without omissions"
            raise CompilationError(msg)

        return arguments

    def resolve_array_sort_comparator(
        self, array_type: ResolvedType, comparator: Expression
    ) -> ResolvedMember[FunctionDeclaration]:
        """Resolve a named comparison function for a dynamic array."""
        if not isinstance(comparator, IdentifierExpression):
            msg = "Sort currently requires a comparison function name"
            raise NotImplementedError(msg)

        member = self.context.references.resolve_function(
            self.scope.class_path, comparator.name, self.context.parents
        )
        function = member.declaration
        element_type = array_type.arguments[0]
        return_type = self.resolve_declared_type(function.return_type, member.owner_class)

        if len(function.parameters) != 2 or return_type.category is not TypeCategory.INT:
            msg = f"Sort comparator {comparator.name} must take two arguments and return int"
            raise CompilationError(msg)

        for parameter in function.parameters:
            parameter_type = self.resolve_declared_type(parameter.type_ref, member.owner_class)
            if parameter.array_dimension != 1 or parameter_type != element_type:
                msg = f"Sort comparator parameter {parameter.name} must have type {element_type!r}"
                raise CompilationError(msg)

        return member

    def resolve_struct_find_field_type(
        self, array_type: ResolvedType, field: Expression
    ) -> ResolvedType:
        """Resolve the scalar field selected by a two-argument array search."""
        element = array_type.arguments[0]
        struct_path = element.declaration_path

        if element.category is not TypeCategory.STRUCT or struct_path is None:
            msg = "Find(FieldName, Value) requires an array of structs"
            raise CompilationError(msg)

        if not isinstance(field, NameExpression):
            msg = "Struct Find requires a name literal as its first argument"
            raise CompilationError(msg)

        package_name = struct_path.get_outer().get_outer().name
        member = self.context.references.resolve_struct_variable(
            struct_path, field.value, self.context.parents, self._visibility[package_name]
        )

        if member.declaration.array_dimension != 1:
            msg = f"Struct Find on fixed array field {field.value} is not implemented yet"
            raise NotImplementedError(msg)

        return self.resolve_declared_type(member.declaration.type_ref, member.owner_class)

    def resolve_enum_index(self, expression: IndexExpression) -> int | None:
        """Resolve a bare enum member used to index an enum-sized array."""
        index = expression.index
        if not isinstance(index, IdentifierExpression):
            return None

        # Preserve ordinary variable lookup, including locals and parameters.
        try:
            self.scope.resolve_variable(index.name)
        except UnknownPropertyError:
            pass
        else:
            return None

        match expression.array:
            case IdentifierExpression(name=name):
                symbol = self.scope.resolve_variable(name)
                declaration = symbol.declaration
                owner = symbol.owner_class

            case MemberExpression() as array:
                member = self.resolve_member(array)
                declaration = member.declaration
                owner = member.owner_class

            case _:
                return None

        dimension_name = declaration.array_dimension_name
        if dimension_name is None:
            return None

        if (
            self.context.references.find_array_dimension_constant(
                dimension_name, owner, self.context.parents
            )
            is not None
        ):
            return None

        enum_type = self.resolve_declared_type(TypeReference(dimension_name), owner)
        enum_path = enum_type.declaration_path
        if enum_type.category is not TypeCategory.ENUM or enum_path is None:
            return None

        enum_owner, enum_name = enum_path.split(require_outer=True)
        enum = self.context.references.resolve_enum(
            enum_owner, enum_name, self.context.parents
        ).declaration

        if index.name not in enum.members:
            msg = f"Unknown enum member {index.name!r} in {enum_path}"
            raise CompilationError(msg)

        return enum.members.index(index.name)

    def accepts_value_type(self, expected: ResolvedType, actual: ResolvedType) -> bool:
        if expected == actual:
            return True

        if expected.category is TypeCategory.CLASS and actual.category is TypeCategory.CLASS:
            if len(expected.arguments) != 1 or len(actual.arguments) != 1:
                return False

            return self.accepts_value_type(expected.arguments[0], actual.arguments[0])

        if (
            expected.category is not TypeCategory.OBJECT
            or actual.category is not TypeCategory.OBJECT
        ):
            return False

        if expected.declaration_path is None or actual.declaration_path is None:
            return False

        context = self.context
        return context.references.is_subclass(
            actual.declaration_path, expected.declaration_path, context.parents
        )
