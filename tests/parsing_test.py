from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from willow_package_builder.compiler.cache import CachedClass, read_cached_class, write_cached_class
from willow_package_builder.compiler.lexer import Lexer
from willow_package_builder.compiler.parser import Parser
from willow_package_builder.package_config import load_package_graph


def main() -> None:
    target_directory = Path("example uc/ExamplePackage").resolve()

    packages = load_package_graph(target_directory)
    tested = 0

    # Keep this test's generated cache files outside the project.
    with TemporaryDirectory(prefix="willow-cache-test-") as temporary:
        cache_directory = Path(temporary)

        for config in packages:
            include_body_tokens = config.directory == target_directory

            for source_path in config.source_files():
                relative_path = source_path.relative_to(config.directory)
                source_bytes = source_path.read_bytes()
                source = source_bytes.decode("utf-8-sig")

                tokens = Lexer(source).tokenize()
                parser = Parser(tokens, binary_precedence={})

                declaration = parser.parse_class_declaration(
                    include_body_tokens=include_body_tokens
                )

                expected = CachedClass(
                    package_name=config.name,
                    source_path=relative_path.as_posix(),
                    source_hash=sha256(source_bytes).hexdigest(),
                    declaration=declaration,
                    includes_body_tokens=include_body_tokens,
                )

                cache_path = cache_directory / config.name / relative_path.with_suffix(".json")

                write_cached_class(cache_path, expected)
                loaded = read_cached_class(cache_path)

                # Compare the complete nested declaration tree and metadata.
                assert loaded == expected, (
                    f"Cache round trip changed {config.name}.{declaration.name}"
                )

                # Ensure we reconstructed objects rather than returning originals.
                assert loaded is not expected
                assert loaded.declaration is not expected.declaration

                # Verify function and operator body-capture behavior survives.
                callables = [*loaded.declaration.functions, *loaded.declaration.operators]

                for callable_declaration in callables:
                    if not callable_declaration.has_body:
                        assert callable_declaration.body_tokens is None
                    elif include_body_tokens:
                        assert callable_declaration.body_tokens is not None
                    else:
                        assert callable_declaration.body_tokens is None

                tested += 1
                print(
                    f"PASS {config.name}.{declaration.name}: "
                    f"{cache_path.stat().st_size:,} cached bytes"
                )

    assert tested > 0, "No class files were discovered"
    print(f"Successfully round-tripped {tested} classes.")


if __name__ == "__main__":
    main()
