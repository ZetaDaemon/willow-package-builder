import json
from pathlib import Path

from willow_package_builder.compiler.builder.package_builder import PackageBuilder
from willow_package_builder.compiler.cache.cache import load_or_parse_class
from willow_package_builder.compiler.semantics.references import ReferenceDatabase
from willow_package_builder.logging import CompilationError, Logger, info
from willow_package_builder.package_config import collect_build_packages, load_package_graph

from .build_context import BuildContext

__all__ = ["build_package"]


def prepare_build(target_directory: Path) -> BuildContext:
    target_directory = target_directory.resolve()

    packages = load_package_graph(target_directory)
    build_packages = collect_build_packages(target_directory, packages)
    references = ReferenceDatabase()

    for config in packages:
        if config.directory in build_packages:
            info(f"Preparing package {config.name}")
        else:
            info(f"Loading reference package {config.name}")
        for source_path in config.source_files():
            cached = load_or_parse_class(
                config, source_path, include_body_tokens=config.directory in build_packages
            )

            references.add_class(config.name, cached.declaration)

    parents = references.resolve_parent_classes(packages)
    class_order = references.inheritance_order(parents)

    return BuildContext(packages, build_packages, references, parents, class_order)


def build_package(
    target_directory: str | Path, output_directory: str | Path | None = None, debug: bool = False
) -> tuple[Path, ...]:
    """Build the target package and its required packages."""
    target_directory = Path(target_directory).resolve()
    output_directory = (
        target_directory.parent if output_directory is None else Path(output_directory).resolve()
    )

    logger = Logger(output_directory / "willow-package-builder.log", debug)

    with logger.catch_errors_and_warnings():
        context = prepare_build(target_directory)
        outputs: list[Path] = []

        for config in context.packages:
            if config.directory not in context.build_packages:
                continue

            try:
                builder = PackageBuilder(context, config)
                package = builder.build()
                data = package.serialize()

            except CompilationError as exc:
                msg = f"Failed to build package {config.name!r}: {exc}"
                raise CompilationError(msg) from exc

            output_path = config.output_path(output_directory)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(data)

            outputs.append(output_path)
            info(f"Wrote {config.name} to {output_path}")

            manifest_path = output_path.with_suffix(".manifest.json")
            manifest_path.write_text(
                json.dumps(builder.manifest(), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    return tuple(outputs)
