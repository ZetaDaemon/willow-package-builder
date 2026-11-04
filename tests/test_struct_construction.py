from pathlib import Path

from willow_package_builder.builder.build_context import BuildContext
from willow_package_builder.builder.build_state import PackageBuildState
from willow_package_builder.builder.classes.property_builder import PropertyBuilder
from willow_package_builder.builder.classes.struct_builder import StructBuilder
from willow_package_builder.builder.references import PackageReferences
from willow_package_builder.compiler.semantics.reference_database import ReferenceDatabase
from willow_package_builder.compiler.syntax.declarations import (
    ClassDeclaration,
    StructDeclaration,
    TypeReference,
    VariableDeclaration,
)
from willow_package_builder.games import TargetGame, select_game
from willow_package_builder.package_config import PackageConfig
from willow_package_builder.properties.values import ArrayValue, FloatValue, IntValue, StructValue
from willow_package_builder.upackage import FName, Package


def test_struct_construction(tmp_path: Path) -> None:
    base = StructDeclaration("BaseData")
    base.variables.append(VariableDeclaration("Count", TypeReference("int")))
    base.defaults = {FName("Count"): IntValue(3)}

    child = StructDeclaration("ChildData", "BaseData")
    child.variables.append(VariableDeclaration("Scale", TypeReference("float")))
    child.defaults = {FName("Scale"): FloatValue(2.0)}

    holder = StructDeclaration("Holder")
    holder.variables.extend(
        [
            VariableDeclaration("Items", TypeReference("ChildData"), 2),
            VariableDeclaration("Single", TypeReference("ChildData")),
        ]
    )
    holder.defaults = {FName("Single"): StructValue({FName("Count"): IntValue(8)})}

    owner = ClassDeclaration("ExampleClass", None)
    owner.structs.extend([base, child, holder])

    config = PackageConfig(tmp_path, "ExamplePackage", (), ())
    references = ReferenceDatabase()
    references.add_class(config.name, owner)
    context = BuildContext(
        (config,),
        {config.directory},
        references,
        {"examplepackage.exampleclass": None},
        ("examplepackage.exampleclass",),
    )

    with select_game(TargetGame.BL2) as game:
        package = Package(FName(config.name), game.package_format(), game.PACKAGE_FLAGS)
        state = PackageBuildState(context, config, package)
        package_references = PackageReferences(state)
        builder = StructBuilder(
            state, package_references, PropertyBuilder(state, package_references)
        )

        direct = builder.make_struct(
            "examplepackage.exampleclass.childdata", {FName("Count"): IntValue(5)}
        )
        assert direct.values[FName("Count")] == IntValue(5)
        assert direct.values[FName("Scale")] == FloatValue(2.0)

        result = builder.make_struct(
            "examplepackage.exampleclass.holder",
            {FName("Single"): StructValue({FName("Scale"): FloatValue(4.0)})},
        )
        single = result.values[FName("Single")]
        assert isinstance(single, StructValue)
        assert single.values[FName("Count")] == IntValue(8)
        assert single.values[FName("Scale")] == FloatValue(4.0)

        items = result.values[FName("Items")]
        assert isinstance(items, ArrayValue)
        assert len(items.elements) == 2
        first, second = items.elements
        assert isinstance(first, StructValue)
        assert isinstance(second, StructValue)
        assert first is not second

        assert first.values[FName("Count")] == IntValue(3)
        assert first.values[FName("Scale")] == FloatValue(2.0)
        first.values[FName("Count")] = IntValue(99)
        assert second.values[FName("Count")] == IntValue(3)

        assert base.defaults[FName("Count")] == IntValue(3)
        assert child.defaults[FName("Scale")] == FloatValue(2.0)
        supplied = holder.defaults[FName("Single")]
        assert isinstance(supplied, StructValue)
        assert supplied.values[FName("Count")] == IntValue(8)
        assert FName("Scale") not in supplied.values

        fresh = builder.make_struct("examplepackage.exampleclass.childdata")
        assert fresh.values[FName("Count")] == IntValue(3)
        assert fresh.values[FName("Scale")] == FloatValue(2.0)
