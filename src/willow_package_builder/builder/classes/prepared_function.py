from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from willow_package_builder.compiler.semantics.expression_resolver import ExpressionResolver
    from willow_package_builder.compiler.syntax.expressions import Expression
    from willow_package_builder.compiler.syntax.statements import FunctionBody
    from willow_package_builder.upackage import UObject


@dataclass
class PreparedFunction:
    resolver: ExpressionResolver
    body: FunctionBody
    function_object: UObject
    parameter_defaults: list[Expression | None]
