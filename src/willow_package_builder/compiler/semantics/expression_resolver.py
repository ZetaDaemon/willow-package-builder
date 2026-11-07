from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from willow_package_builder.compiler.syntax.declarations import (
    FunctionDeclaration,
    OperatorCategory,
    VariableDeclaration,
)
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
from willow_package_builder.logging import CompilationError, declaration_context
from willow_package_builder.package_config import collect_visible_packages

from .types import ResolvedType, TypeCategory

if TYPE_CHECKING:
    from willow_package_builder.builder.build_context import BuildContext
    from willow_package_builder.compiler.syntax.declarations import (
        OperatorDeclaration,
        TypeReference,
    )
    from willow_package_builder.compiler.syntax.keyword import Keyword
    from willow_package_builder.compiler.syntax.punctuation import Operator
    from willow_package_builder.upackage import FName, ReferencePath

    from .reference_database import ResolvedMember
    from .scope import FunctionScope


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

    def type_of(self, expression: Expression) -> ResolvedType:
        match expression:
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

            case CallExpression():
                function = self.resolve_call(expression)

                return self.resolve_declared_type(
                    function.declaration.return_type, function.owner_class
                )

            case MemberExpression():
                member = self.resolve_member(expression)

                return self.resolve_declared_type(member.declaration.type_ref, member.owner_class)

            case SelfExpression():
                return ResolvedType(TypeCategory.OBJECT, self.scope.class_path)

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

                if left_type != left:
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

    def resolve_call(self, expression: CallExpression) -> ResolvedMember[FunctionDeclaration]:
        match expression.callee:
            case IdentifierExpression():
                return self.context.references.resolve_function(
                    self.scope.class_path, expression.callee.name, self.context.parents
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
