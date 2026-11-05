import json
from collections.abc import Mapping
from pathlib import Path
from time import perf_counter

from willow_package_builder.compiler.class_loader import ClassLoader
from willow_package_builder.compiler.semantics.reference_database import ReferenceDatabase
from willow_package_builder.package_config import collect_build_packages, load_package_graph

from .builder.build_context import BuildContext
from .builder.package_builder import PackageBuilder
from .logging import CompilationError, Logger, WarningAction, WarningCode, info

__all__ = ["build_package"]


def prepare_build(target_directory: Path) -> BuildContext:
    target_directory = target_directory.resolve()

    packages = load_package_graph(target_directory)
    build_packages = collect_build_packages(target_directory, packages)
    references = ReferenceDatabase()
    loader = ClassLoader(packages, build_packages, references)

    loader.load_declarations()

    context = BuildContext(packages, build_packages, references, loader)

    info("Resolving class hierarchy")
    start = perf_counter()
    context.refresh_class_hierarchy()
    info(
        f"Resolved hierarchy for {len(context.class_order)} classes "
        f"in {perf_counter() - start:.3f}s"
    )

    loader.resolve_dimensions(context.class_order)

    return context


def build_package(
    target_directory: str | Path,
    output_directory: str | Path | None = None,
    debug: bool = False,
    silent_console: bool = False,
    warning_actions: Mapping[WarningCode, WarningAction] | None = None,
) -> tuple[Path, ...]:
    """Build the target package and its required packages."""
    target_directory = Path(target_directory).resolve()
    output_directory = (
        target_directory.parent if output_directory is None else Path(output_directory).resolve()
    )

    logger = Logger(
        target_directory.parent / "willow-package-builder.log",
        debug=debug,
        silent_console=silent_console,
        warning_actions={} if warning_actions is None else dict(warning_actions),
    )

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
