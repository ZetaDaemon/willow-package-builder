from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from willow_package_builder.compiler.declarations import OperatorType
from willow_package_builder.logging import CompilationError
from willow_package_builder.package_config import collect_visible_packages

from .expressions import BinaryExpression, Expression, IdentifierExpression, IntegerExpression
from .types import ResolvedType, TypeType

if TYPE_CHECKING:
    from .build import BuildContext
    from .declarations import OperatorDeclaration, TypeReference
    from .references import ResolvedMember
    from .scope import FunctionScope


@dataclass
class ExpressionResolver:
    context: BuildContext
    scope: FunctionScope

    _visibility: dict[str, set[str]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._visibility = {
            config.name.casefold(): collect_visible_packages(config, self.context.packages)
            for config in self.context.packages
        }

    def resolve_declared_type(
        self, type_ref: TypeReference | None, owner_class: str
    ) -> ResolvedType:
        package_name = owner_class.partition(".")[0].casefold()

        return self.context.references.resolve_type(
            type_ref,
            current_class=owner_class,
            visible_packages=self._visibility[package_name],
            parents=self.context.parents,
        )

    def resolve_operator(self, expression: BinaryExpression) -> ResolvedMember[OperatorDeclaration]:
        left = self.type_of(expression.left)
        right = self.type_of(expression.right)
        package_name = self.scope.class_path.partition(".")[0].casefold()

        return self.context.references.resolve_binary_operator(
            expression.operator,
            left,
            right,
            current_class=self.scope.class_path,
            visible_packages=self._visibility[package_name],
            parents=self.context.parents,
        )

    def type_of(self, expression: Expression) -> ResolvedType:
        if isinstance(expression, IntegerExpression):
            return ResolvedType(type=TypeType.INT)

        if isinstance(expression, IdentifierExpression):
            symbol = self.scope.resolve_variable(expression.name)

            return self.resolve_declared_type(symbol.declaration.type_ref, symbol.owner_class)

        if isinstance(expression, BinaryExpression):
            operator = self.resolve_operator(expression)

            return self.resolve_declared_type(
                operator.declaration.return_type, operator.owner_class
            )

        msg = f"Unsupported expression type: {type(expression).__name__}"
        raise CompilationError(msg)

    def binary_precedence(self, name: str, left: ResolvedType) -> int | None:
        key = name.casefold()
        precedences: set[int] = set()

        # A declaration on a derived class takes priority over an inherited
        # declaration with the same operand types.
        seen_right_types: set[ResolvedType] = set()

        for owner, declaration in self.context.references.iter_class_hierarchy(
            self.scope.class_path, self.context.parents
        ):
            for operator in declaration.operators:
                if operator.op_type is not OperatorType.BINARY or operator.name.casefold() != key:
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
            raise CompilationError(msg)

        return next(iter(precedences))
