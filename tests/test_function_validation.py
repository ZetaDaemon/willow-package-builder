from dataclasses import replace
from pathlib import Path

import pytest

from willow_package_builder.compiler.build import BuildContext, prepare_build
from willow_package_builder.compiler.expression_resolver import ExpressionResolver
from willow_package_builder.compiler.lexer import Lexer
from willow_package_builder.compiler.parser import Parser
from willow_package_builder.compiler.scope import FunctionScope
from willow_package_builder.compiler.validation import FunctionBodyValidator


@pytest.fixture(scope="module")
def context() -> BuildContext:
    project_directory = Path(__file__).resolve().parents[1]

    return prepare_build(project_directory / "example uc" / "ExamplePackage")


def validate_source(
    context: BuildContext,
    source: str,
    *,
    void: bool = False,
    const_parameter: bool = False,
    static: bool = False,
) -> None:
    class_path = "examplepackage.exampleclass"

    original = context.references.resolve_function(class_path, "Test", context.parents).declaration

    parameters = list(original.parameters)

    if const_parameter:
        parameters[0] = replace(parameters[0], modifiers=(*parameters[0].modifiers, "const"))

    # Construct an independent declaration; don't modify cached declarations.
    function = replace(
        original,
        parameters=parameters,
        return_type=None if void else original.return_type,
        modifiers=((*original.modifiers, "static") if static else original.modifiers),
        has_body=True,
        body_tokens=Lexer(source).tokenize()[:-1],
    )

    scope = FunctionScope(
        class_path=class_path,
        function=function,
        references=context.references,
        parents=context.parents,
    )

    resolver = ExpressionResolver(context=context, scope=scope)
    parser = Parser.from_function_body(function, expression_resolver=resolver)

    body = parser.parse_function_body()
    FunctionBodyValidator(resolver=resolver).validate(body)


def test_valid_body(context: BuildContext) -> None:
    validate_source(
        context,
        """
        local int Temporary;
        Temporary = Number;
        Value = Temporary;
        return Value * 2;
        """,
    )


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("1 = Number; return Number;", "Assignment destination must be a writable variable"),
        ("Value = Number < 10; return Number;", "Assignment type mismatch"),
        ("return Number < 10;", "Return type mismatch"),
        ("return;", "Non-void function requires a return value"),
        ("1 += 2; return Number;", "Assignment destination must be a writable variable"),
    ],
)
def test_invalid_body(context: BuildContext, source: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_source(context, source)


def test_void_return(context: BuildContext) -> None:
    validate_source(context, "return;", void=True)

    with pytest.raises(ValueError, match="Void function cannot return a value"):
        validate_source(context, "return Number;", void=True)


def test_const_parameter(context: BuildContext) -> None:
    with pytest.raises(ValueError, match="Cannot assign to const variable"):
        validate_source(context, "Number = 1; return Number;", const_parameter=True)


def test_static_instance_access(context: BuildContext) -> None:
    with pytest.raises(
        ValueError, match="Static function cannot directly access instance variable"
    ):
        validate_source(context, "return Value;", static=True)
