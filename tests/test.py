import pytest

from willow_package_builder.compiler.semantics.defaults_resolver import (
    DefaultsResolver,
    ResolvedArrayValue,
    ResolvedEnumValue,
    ResolvedStructValue,
)
from willow_package_builder.compiler.semantics.reference_database import ReferenceDatabase
from willow_package_builder.compiler.semantics.types import ResolvedType, TypeCategory
from willow_package_builder.compiler.syntax.declarations import (
    ClassDeclaration,
    EnumDeclaration,
    StructDeclaration,
    TypeReference,
    VariableDeclaration,
)
from willow_package_builder.compiler.syntax.defaults import (
    DefaultAssignment,
    IdentifierDefaultValue,
    LiteralDefaultValue,
    ObjectDefaultValue,
)
from willow_package_builder.compiler.syntax.lexer import Lexer
from willow_package_builder.logging import CompilationError, SourceLocation


def make_resolver() -> DefaultsResolver:
    base = ClassDeclaration("BaseClass", None)
    base.variables.extend(
        [
            VariableDeclaration("Count", TypeReference("int")),
            VariableDeclaration("Scale", TypeReference("float")),
            VariableDeclaration("Enabled", TypeReference("bool")),
            VariableDeclaration("SmallNumber", TypeReference("byte")),
        ]
    )

    child = ClassDeclaration("ChildClass", "BaseClass")

    references = ReferenceDatabase()
    references.add_class("ExamplePackage", base)
    references.add_class("ExamplePackage", child)

    return DefaultsResolver(
        references,
        {"examplepackage.baseclass": None, "examplepackage.childclass": "examplepackage.baseclass"},
        {"examplepackage"},
    )


def test_inherited_default_target() -> None:
    resolver = make_resolver()
    assignment = DefaultAssignment("Count", LiteralDefaultValue(15), SourceLocation(3, 5))

    target = resolver.resolve_target("examplepackage.childclass", assignment)

    assert target.owner_class == "examplepackage.baseclass"
    assert target.declaration.name == "Count"
    assert resolver.resolve_scalar_value(assignment, target.resolved_type) == LiteralDefaultValue(
        15
    )


def test_integer_default_for_float() -> None:
    resolver = make_resolver()
    assignment = DefaultAssignment("Scale", LiteralDefaultValue(2), SourceLocation(4, 5))

    target = resolver.resolve_target("examplepackage.childclass", assignment)
    value = resolver.resolve_scalar_value(assignment, target.resolved_type)

    assert isinstance(value, LiteralDefaultValue)
    assert type(value.value) is float
    assert value.value == 2.0


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("Count", True),
        ("Count", 1 << 31),
        ("Enabled", 1),
        ("SmallNumber", -1),
        ("SmallNumber", 256),
    ],
)
def test_invalid_scalar_default(name: str, value: object) -> None:
    resolver = make_resolver()
    location = SourceLocation(7, 5)
    assignment = DefaultAssignment(name, LiteralDefaultValue(value), location)  # pyright: ignore[reportArgumentType]

    target = resolver.resolve_target("examplepackage.childclass", assignment)

    with pytest.raises(CompilationError) as caught:
        resolver.resolve_scalar_value(assignment, target.resolved_type)

    assert caught.value.location == location


def test_class_defaults_inheritance() -> None:
    resolver = make_resolver()

    base = resolver.references.classes["examplepackage.baseclass"]
    child = resolver.references.classes["examplepackage.childclass"]

    base.default_tokens = tuple(Lexer("Count=10 Scale=2.0").tokenize()[:-1])
    child.default_tokens = tuple(Lexer("Count=20").tokenize()[:-1])

    child_defaults = resolver.resolve_class_defaults("examplepackage.childclass")

    assert child_defaults["count"].value == LiteralDefaultValue(20)
    assert child_defaults["scale"].value == LiteralDefaultValue(2.0)
    assert child_defaults["count"].target.owner_class == "examplepackage.baseclass"

    # Resolving the child must not change its parent's defaults.
    base_defaults = resolver.resolve_class_defaults("examplepackage.baseclass")

    assert base_defaults["count"].value == LiteralDefaultValue(10)
    assert base_defaults["scale"].value == LiteralDefaultValue(2.0)

    assert child_defaults["enabled"].value == LiteralDefaultValue(False)
    assert child_defaults["smallnumber"].value == LiteralDefaultValue(0)


def test_later_default_assignment_wins() -> None:
    resolver = make_resolver()

    base = resolver.references.classes["examplepackage.baseclass"]
    base.default_tokens = tuple(Lexer("Count=10 Count=30").tokenize()[:-1])

    defaults = resolver.resolve_class_defaults("examplepackage.baseclass")

    assert defaults["count"].value == LiteralDefaultValue(30)


def test_nested_struct_defaults() -> None:
    resolver = make_resolver()
    base = resolver.references.classes["examplepackage.baseclass"]
    child = resolver.references.classes["examplepackage.childclass"]

    position = StructDeclaration("Position")
    position.variables.extend(
        [
            VariableDeclaration("X", TypeReference("float")),
            VariableDeclaration("Y", TypeReference("float")),
        ]
    )
    position.default_tokens = tuple(Lexer("Y=2.0").tokenize()[:-1])

    data = StructDeclaration("Data")
    data.variables.extend(
        [
            VariableDeclaration("Count", TypeReference("int")),
            VariableDeclaration("Position", TypeReference("Position")),
        ]
    )
    data.default_tokens = tuple(Lexer("Count=3 Position=(X=1.0)").tokenize()[:-1])

    base.structs.extend([position, data])
    base.variables.append(VariableDeclaration("DataValue", TypeReference("Data")))
    base.default_tokens = tuple(Lexer("DataValue=(Count=5)").tokenize()[:-1])
    child.default_tokens = tuple(Lexer("DataValue=(Position=(X=10.0))").tokenize()[:-1])

    defaults = resolver.resolve_class_defaults("examplepackage.childclass")

    resolved_data = defaults["datavalue"].value
    assert isinstance(resolved_data, ResolvedStructValue)
    assert resolved_data.fields["count"].value == LiteralDefaultValue(5)

    resolved_position = resolved_data.fields["position"].value
    assert isinstance(resolved_position, ResolvedStructValue)
    assert resolved_position.fields["x"].value == LiteralDefaultValue(10.0)
    assert resolved_position.fields["y"].value == LiteralDefaultValue(2.0)

    # Child overrides must not mutate the parent's resolved defaults.
    parent_defaults = resolver.resolve_class_defaults("examplepackage.baseclass")
    parent_data = parent_defaults["datavalue"].value
    assert isinstance(parent_data, ResolvedStructValue)

    parent_position = parent_data.fields["position"].value
    assert isinstance(parent_position, ResolvedStructValue)
    assert parent_position.fields["x"].value == LiteralDefaultValue(1.0)
    assert parent_position.fields["y"].value == LiteralDefaultValue(2.0)


def test_class_reference_default() -> None:
    resolver = make_resolver()
    resolved_type = ResolvedType(
        TypeCategory.CLASS,
        arguments=(ResolvedType(TypeCategory.OBJECT, "examplepackage.baseclass"),),
    )
    assignment = DefaultAssignment(
        "TargetClass",
        ObjectDefaultValue("Class", "ExamplePackage.ChildClass"),
        SourceLocation(3, 5),
    )

    value = resolver.resolve_value(
        assignment, resolved_type, LiteralDefaultValue(None), "examplepackage.baseclass"
    )

    assert value == ObjectDefaultValue("Class", "examplepackage.childclass")


def test_incompatible_class_reference_default() -> None:
    resolver = make_resolver()
    resolver.references.add_class("ExamplePackage", ClassDeclaration("UnrelatedClass", None))
    parents = dict(resolver.parents)
    parents["examplepackage.unrelatedclass"] = None
    resolver.parents = parents

    resolved_type = ResolvedType(
        TypeCategory.CLASS,
        arguments=(ResolvedType(TypeCategory.OBJECT, "examplepackage.baseclass"),),
    )
    assignment = DefaultAssignment(
        "TargetClass",
        ObjectDefaultValue("Class", "ExamplePackage.UnrelatedClass"),
        SourceLocation(3, 5),
    )

    with pytest.raises(CompilationError, match="does not extend"):
        resolver.resolve_value(
            assignment, resolved_type, LiteralDefaultValue(None), "examplepackage.baseclass"
        )


def test_null_class_reference_default() -> None:
    resolver = make_resolver()
    resolved_type = ResolvedType(
        TypeCategory.CLASS,
        arguments=(ResolvedType(TypeCategory.OBJECT, "examplepackage.baseclass"),),
    )
    assignment = DefaultAssignment("TargetClass", LiteralDefaultValue(None), SourceLocation(3, 5))

    assert resolver.resolve_value(
        assignment, resolved_type, LiteralDefaultValue(None), "examplepackage.baseclass"
    ) == LiteralDefaultValue(None)


def test_enum_defaults() -> None:
    resolver = make_resolver()
    base = resolver.references.classes["examplepackage.baseclass"]
    child = resolver.references.classes["examplepackage.childclass"]

    base.enums.append(EnumDeclaration("ExampleMode", ("EM_First", "EM_Second")))
    base.variables.append(VariableDeclaration("Mode", TypeReference("ExampleMode")))

    initial = resolver.resolve_class_defaults("examplepackage.baseclass")

    assert initial["mode"].value == ResolvedEnumValue(
        "examplepackage.baseclass.examplemode", "EM_First", 0
    )

    # Resolve without regard to case, but retain the declared spelling.
    child.default_tokens = tuple(Lexer("Mode=em_second").tokenize()[:-1])

    overridden = resolver.resolve_class_defaults("examplepackage.childclass")

    assert overridden["mode"].value == ResolvedEnumValue(
        "examplepackage.baseclass.examplemode", "EM_Second", 1
    )

    # The child's override must not change the parent's defaults.
    unchanged = resolver.resolve_class_defaults("examplepackage.baseclass")

    assert unchanged["mode"].value == initial["mode"].value


def test_enum_rejects_unknown_member() -> None:
    resolver = make_resolver()
    base = resolver.references.classes["examplepackage.baseclass"]
    base.enums.append(EnumDeclaration("ExampleMode", ("EM_First", "EM_Second")))

    resolved_type = ResolvedType(TypeCategory.ENUM, "examplepackage.baseclass.examplemode")
    assignment = DefaultAssignment(
        "Mode", IdentifierDefaultValue("OTHER_Value"), SourceLocation(3, 5)
    )

    with pytest.raises(CompilationError, match="Unknown member") as caught:
        resolver.resolve_enum_value(resolved_type, assignment)

    assert caught.value.location == assignment.location


def test_dynamic_array_defaults() -> None:
    resolver = make_resolver()
    base = resolver.references.classes["examplepackage.baseclass"]
    child = resolver.references.classes["examplepackage.childclass"]

    base.variables.append(
        VariableDeclaration("Values", TypeReference("array", (TypeReference("int"),)))
    )
    base.default_tokens = tuple(Lexer("Values(0)=10 Values(2)=30").tokenize()[:-1])
    child.default_tokens = tuple(Lexer("Values(1)=20").tokenize()[:-1])

    defaults = resolver.resolve_class_defaults("examplepackage.childclass")

    assert defaults["values"].value == ResolvedArrayValue(
        [LiteralDefaultValue(10), LiteralDefaultValue(20), LiteralDefaultValue(30)]
    )

    parent_defaults = resolver.resolve_class_defaults("examplepackage.baseclass")

    assert parent_defaults["values"].value == ResolvedArrayValue(
        [LiteralDefaultValue(10), LiteralDefaultValue(0), LiteralDefaultValue(30)]
    )
    assert defaults["values"].target.resolved_type.category is TypeCategory.ARRAY


def test_fixed_array_defaults() -> None:
    resolver = make_resolver()
    base = resolver.references.classes["examplepackage.baseclass"]

    base.variables.append(VariableDeclaration("Values", TypeReference("int"), 3))
    base.default_tokens = tuple(Lexer("Values(1)=20").tokenize()[:-1])

    defaults = resolver.resolve_class_defaults("examplepackage.baseclass")

    assert defaults["values"].value == ResolvedArrayValue(
        [LiteralDefaultValue(0), LiteralDefaultValue(20), LiteralDefaultValue(0)]
    )


def test_fixed_array_default_out_of_bounds() -> None:
    resolver = make_resolver()
    base = resolver.references.classes["examplepackage.baseclass"]

    base.variables.append(VariableDeclaration("Values", TypeReference("int"), 3))
    base.default_tokens = tuple(Lexer("Values(3)=20").tokenize()[:-1])

    with pytest.raises(CompilationError, match="exceeds the fixed array"):
        resolver.resolve_class_defaults("examplepackage.baseclass")


def test_array_fields_in_struct_defaults() -> None:
    resolver = make_resolver()
    base = resolver.references.classes["examplepackage.baseclass"]
    child = resolver.references.classes["examplepackage.childclass"]

    data = StructDeclaration("ArrayData")
    data.variables.extend(
        [
            VariableDeclaration("DynamicValues", TypeReference("array", (TypeReference("int"),))),
            VariableDeclaration("FixedValues", TypeReference("int"), 3),
        ]
    )
    data.default_tokens = tuple(Lexer("DynamicValues(0)=10 FixedValues(1)=20").tokenize()[:-1])

    base.structs.append(data)
    base.variables.append(VariableDeclaration("Data", TypeReference("ArrayData")))
    base.default_tokens = tuple(Lexer("Data=(DynamicValues(2)=30)").tokenize()[:-1])
    child.default_tokens = tuple(
        Lexer("Data=(DynamicValues(1)=15,FixedValues(2)=40)").tokenize()[:-1]
    )

    defaults = resolver.resolve_class_defaults("examplepackage.childclass")
    resolved = defaults["data"].value
    assert isinstance(resolved, ResolvedStructValue)

    assert resolved.fields["dynamicvalues"].value == ResolvedArrayValue(
        [LiteralDefaultValue(10), LiteralDefaultValue(15), LiteralDefaultValue(30)]
    )
    assert resolved.fields["fixedvalues"].value == ResolvedArrayValue(
        [LiteralDefaultValue(0), LiteralDefaultValue(20), LiteralDefaultValue(40)]
    )

    # The child's assignments must leave the parent's values unchanged.
    parent_defaults = resolver.resolve_class_defaults("examplepackage.baseclass")
    parent = parent_defaults["data"].value
    assert isinstance(parent, ResolvedStructValue)

    assert parent.fields["dynamicvalues"].value == ResolvedArrayValue(
        [LiteralDefaultValue(10), LiteralDefaultValue(0), LiteralDefaultValue(30)]
    )
    assert parent.fields["fixedvalues"].value == ResolvedArrayValue(
        [LiteralDefaultValue(0), LiteralDefaultValue(20), LiteralDefaultValue(0)]
    )


def test_array_of_struct_defaults() -> None:
    resolver = make_resolver()
    base = resolver.references.classes["examplepackage.baseclass"]
    child = resolver.references.classes["examplepackage.childclass"]

    item = StructDeclaration("ItemData")
    item.variables.extend(
        [
            VariableDeclaration("Count", TypeReference("int")),
            VariableDeclaration("Scale", TypeReference("float")),
        ]
    )
    item.default_tokens = tuple(Lexer("Count=3 Scale=2.0").tokenize()[:-1])

    base.structs.append(item)
    base.variables.append(
        VariableDeclaration("Items", TypeReference("array", (TypeReference("ItemData"),)))
    )
    base.default_tokens = tuple(Lexer("Items(1)=(Count=10)").tokenize()[:-1])
    child.default_tokens = tuple(Lexer("Items(1)=(Scale=5.0)").tokenize()[:-1])

    defaults = resolver.resolve_class_defaults("examplepackage.childclass")
    items = defaults["items"].value
    assert isinstance(items, ResolvedArrayValue)
    assert len(items.elements) == 2

    # The gap element receives the struct's defaults.
    first = items.elements[0]
    assert isinstance(first, ResolvedStructValue)
    assert first.fields["count"].value == LiteralDefaultValue(3)
    assert first.fields["scale"].value == LiteralDefaultValue(2.0)

    # The child changes Scale while preserving the parent's Count.
    second = items.elements[1]
    assert isinstance(second, ResolvedStructValue)
    assert second.fields["count"].value == LiteralDefaultValue(10)
    assert second.fields["scale"].value == LiteralDefaultValue(5.0)

    # Elements must have independent field maps.
    assert first.fields is not second.fields

    parent_defaults = resolver.resolve_class_defaults("examplepackage.baseclass")
    parent_items = parent_defaults["items"].value
    assert isinstance(parent_items, ResolvedArrayValue)

    parent_second = parent_items.elements[1]
    assert isinstance(parent_second, ResolvedStructValue)
    assert parent_second.fields["count"].value == LiteralDefaultValue(10)
    assert parent_second.fields["scale"].value == LiteralDefaultValue(2.0)


def test_whole_array_default_replaces_inherited_array() -> None:
    resolver = make_resolver()
    base = resolver.references.classes["examplepackage.baseclass"]
    child = resolver.references.classes["examplepackage.childclass"]

    base.variables.append(
        VariableDeclaration("Values", TypeReference("array", (TypeReference("int"),)))
    )
    base.default_tokens = tuple(Lexer("Values=(10,20,30)").tokenize()[:-1])
    child.default_tokens = tuple(Lexer("Values=(40)").tokenize()[:-1])

    defaults = resolver.resolve_class_defaults("examplepackage.childclass")

    assert defaults["values"].value == ResolvedArrayValue([LiteralDefaultValue(40)])

    child.default_tokens = tuple(Lexer("Values=()").tokenize()[:-1])
    cleared = resolver.resolve_class_defaults("examplepackage.childclass")

    assert cleared["values"].value == ResolvedArrayValue([])


def test_whole_struct_array_uses_struct_defaults() -> None:
    resolver = make_resolver()
    base = resolver.references.classes["examplepackage.baseclass"]
    child = resolver.references.classes["examplepackage.childclass"]

    item = StructDeclaration("ItemData")
    item.variables.extend(
        [
            VariableDeclaration("Count", TypeReference("int")),
            VariableDeclaration("Scale", TypeReference("float")),
        ]
    )
    item.default_tokens = tuple(Lexer("Count=3 Scale=2.0").tokenize()[:-1])

    base.structs.append(item)
    base.variables.append(
        VariableDeclaration("Items", TypeReference("array", (TypeReference("ItemData"),)))
    )
    base.default_tokens = tuple(Lexer("Items=((Count=99,Scale=9.0))").tokenize()[:-1])
    child.default_tokens = tuple(Lexer("Items=((Count=5),())").tokenize()[:-1])

    defaults = resolver.resolve_class_defaults("examplepackage.childclass")
    items = defaults["items"].value
    assert isinstance(items, ResolvedArrayValue)
    assert len(items.elements) == 2

    first, second = items.elements
    assert isinstance(first, ResolvedStructValue)
    assert isinstance(second, ResolvedStructValue)

    assert first.fields["count"].value == LiteralDefaultValue(5)
    assert first.fields["scale"].value == LiteralDefaultValue(2.0)
    assert second.fields["count"].value == LiteralDefaultValue(3)
    assert second.fields["scale"].value == LiteralDefaultValue(2.0)
