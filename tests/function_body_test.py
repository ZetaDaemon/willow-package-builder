from pathlib import Path

from willow_package_builder.compiler.build import prepare_build
from willow_package_builder.compiler.declarations import TypeReference
from willow_package_builder.compiler.expression_resolver import ExpressionResolver
from willow_package_builder.compiler.expressions import (
    BinaryExpression,
    IdentifierExpression,
    IntegerExpression,
)
from willow_package_builder.compiler.lexer import TokenType
from willow_package_builder.compiler.parser import Parser
from willow_package_builder.compiler.scope import FunctionScope, VariableType
from willow_package_builder.compiler.statements import AssignmentStatement, ReturnStatement
from willow_package_builder.compiler.types import TypeType
from willow_package_builder.compiler.validation import FunctionBodyValidator


def main() -> None:
    project_directory = Path(__file__).resolve().parents[1]
    target_directory = project_directory / "example uc" / "ExamplePackage"

    context = prepare_build(target_directory)
    class_path = "examplepackage.exampleclass"

    function = context.references.resolve_function(class_path, "Test", context.parents).declaration

    # Use a fresh scope: parse_function_body registers the locals.
    scope = FunctionScope(
        class_path=class_path,
        function=function,
        references=context.references,
        parents=context.parents,
    )

    resolver = ExpressionResolver(context=context, scope=scope)

    parser = Parser.from_function_body(function, expression_resolver=resolver)

    body = parser.parse_function_body()

    assert parser.peek().type is TokenType.EOF

    validator = FunctionBodyValidator(resolver=resolver)
    validator.validate(body)

    print("Function-body validation passed.")

    # local int Temporary;
    assert len(body.locals) == 1
    assert body.locals[0].name == "Temporary"
    assert body.locals[0].type_ref == TypeReference(name="int")

    # Parameters, locals, and instance fields remain distinguishable.
    assert scope.resolve_variable("Number").type is VariableType.PARAMETER
    assert scope.resolve_variable("Temporary").type is VariableType.LOCAL
    assert scope.resolve_variable("Value").type is VariableType.INSTANCE

    assert len(body.statements) == 2

    # Value = Number;
    assignment = body.statements[0]
    assert isinstance(assignment, AssignmentStatement)

    assert isinstance(assignment.target, IdentifierExpression)
    assert assignment.target.name == "Value"

    assert isinstance(assignment.value, IdentifierExpression)
    assert assignment.value.name == "Number"

    assert resolver.type_of(assignment.target).type is TypeType.INT
    assert resolver.type_of(assignment.value).type is TypeType.INT

    # return Value * 2;
    return_statement = body.statements[1]
    assert isinstance(return_statement, ReturnStatement)

    multiplication = return_statement.value
    assert isinstance(multiplication, BinaryExpression)
    assert multiplication.operator == "*"

    assert isinstance(multiplication.left, IdentifierExpression)
    assert multiplication.left.name == "Value"

    assert isinstance(multiplication.right, IntegerExpression)
    assert multiplication.right.value == 2

    # The multiplication resolves to the native integer overload.
    operator = resolver.resolve_operator(multiplication)
    assert operator.owner_class == "core.object"
    assert operator.declaration.native_index == 144
    assert operator.declaration.precedence == 16

    # Its result matches the function's declared return type.
    result_type = resolver.type_of(multiplication)
    declared_return_type = resolver.resolve_declared_type(function.return_type, class_path)

    assert result_type.type is TypeType.INT
    assert result_type == declared_return_type

    print("PASS local declarations and function scope")
    print("PASS assignment statement")
    print("PASS return statement and multiplication overload")
    print("Function-body parsing checks passed.")


if __name__ == "__main__":
    main()
