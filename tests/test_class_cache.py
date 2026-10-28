from pathlib import Path
from unittest.mock import patch

from willow_package_builder.compiler.cache import load_or_parse_class
from willow_package_builder.compiler.parser import Parser
from willow_package_builder.package_config import PackageConfig

SOURCE = """\
class ExampleClass extends Object;

var int Value;

function int Test(int Number)
{
    local int Temporary;
    return Number;
}
"""


def create_package(directory: Path) -> tuple[PackageConfig, Path]:
    classes = directory / "Classes"
    classes.mkdir()

    source_path = classes / "ExampleClass.uc"
    source_path.write_text(SOURCE, encoding="utf-8")

    config = PackageConfig(
        directory=directory.resolve(), name="ExamplePackage", references=(), required=()
    )

    return config, source_path


def test_unchanged_source_skips_parsing(tmp_path: Path) -> None:
    config, source_path = create_package(tmp_path)

    first = load_or_parse_class(config, source_path, include_body_tokens=True)

    with patch.object(
        Parser,
        "parse_class_declaration",
        side_effect=AssertionError("Unchanged class was reparsed"),
    ):
        second = load_or_parse_class(config, source_path, include_body_tokens=True)

    assert second == first


def test_changed_source_invalidates_cache(tmp_path: Path) -> None:
    config, source_path = create_package(tmp_path)

    first = load_or_parse_class(config, source_path, include_body_tokens=True)

    source_path.write_text(SOURCE.replace("var int Value;", "var int Changed;"), encoding="utf-8")

    second = load_or_parse_class(config, source_path, include_body_tokens=True)

    assert second.source_hash != first.source_hash
    assert second.declaration.variables[0].name == "Changed"


def test_reference_cache_upgrades_for_compilation(tmp_path: Path) -> None:
    config, source_path = create_package(tmp_path)

    reference = load_or_parse_class(config, source_path, include_body_tokens=False)

    assert reference.declaration.functions[0].body_tokens is None

    compiled_input = load_or_parse_class(config, source_path, include_body_tokens=True)

    assert compiled_input.includes_body_tokens
    assert compiled_input.declaration.functions[0].body_tokens is not None

    # The richer cache also satisfies a later reference-only request.
    with patch.object(
        Parser,
        "parse_class_declaration",
        side_effect=AssertionError("Body-complete cache was unnecessarily reparsed"),
    ):
        reused = load_or_parse_class(config, source_path, include_body_tokens=False)

    assert reused == compiled_input
