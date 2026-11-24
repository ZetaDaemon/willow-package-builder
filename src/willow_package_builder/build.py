import json
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from time import perf_counter

from willow_package_builder.build_fingerprints import (
    builder_code_fingerprint,
    package_build_fingerprints,
)
from willow_package_builder.build_settings import (
    BuildSettings,
    get_build_settings,
    select_build_settings,
)
from willow_package_builder.compiler.class_loader import ClassLoader
from willow_package_builder.compiler.semantics.reference_database import ReferenceDatabase
from willow_package_builder.games import get_game
from willow_package_builder.handlers.registry import configure_class_handlers
from willow_package_builder.package_config import collect_build_packages, load_package_graph

from .builder.build_context import BuildContext
from .builder.package_builder import PackageBuilder
from .logging import CompilationError, Logger, WarningAction, WarningCode, info

__all__ = ["build_package"]


def prepare_build(target_directory: Path, reference_paths: tuple[Path, ...] = ()) -> BuildContext:
    target_directory = target_directory.resolve()

    packages = load_package_graph(target_directory, reference_paths)
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
    warning_actions: Mapping[WarningCode, WarningAction] | None = None,
    reference_paths: tuple[Path, ...] = (),
    *,
    settings: BuildSettings | None = None,
) -> tuple[Path, ...]:
    """Build the target package and its required packages."""
    if settings is None:
        settings = BuildSettings()

    target_directory = Path(target_directory).resolve()
    output_directory = (
        target_directory.parent if output_directory is None else Path(output_directory).resolve()
    )

    logger = Logger(
        target_directory.parent / "willow-package-builder.log",
        warning_actions={} if warning_actions is None else dict(warning_actions),
    )

    with select_build_settings(settings), logger.catch_errors_and_warnings():
        context = prepare_build(target_directory, reference_paths)
        configure_class_handlers(context.packages)
        fingerprints = package_build_fingerprints(
            context.packages,
            target=get_game().TARGET.value,
            builder_identity=json.dumps(
                {
                    "code": builder_code_fingerprint(),
                    "warnings": {
                        code.value: action.value for code, action in (warning_actions or {}).items()
                    },
                },
                sort_keys=True,
            ),
        )
        outputs: list[Path] = []

        for config in context.packages:
            if config.directory not in context.build_packages:
                continue

            output_path = config.output_path(output_directory)
            manifest_path = output_path.with_suffix(".manifest.json")
            output_key = sha256(str(output_path).encode("utf-8")).hexdigest()
            stamp_path = config.directory / ".willow-cache" / "builds" / f"{output_key}.fingerprint"
            fingerprint = fingerprints[config.directory]

            if not get_build_settings().force and output_path.is_file() and manifest_path.is_file():
                try:
                    previous_fingerprint = stamp_path.read_text(encoding="utf-8").strip()
                except OSError, UnicodeError:
                    previous_fingerprint = None

                if previous_fingerprint == fingerprint:
                    info(f"Skipping {config.name}; package is up to date")
                    outputs.append(output_path)
                    continue

            try:
                builder = PackageBuilder(context, config)
                package = builder.build()
                data = package.serialize()

            except CompilationError as exc:
                msg = f"Failed to build package {config.name!r}: {exc}"
                raise CompilationError(msg) from exc

            output_path.parent.mkdir(parents=True, exist_ok=True)
            stamp_path.unlink(missing_ok=True)
            output_path.write_bytes(data)

            outputs.append(output_path)
            info(f"Wrote {config.name} to {output_path}")

            manifest_path.write_text(
                json.dumps(builder.manifest(), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            stamp_path.parent.mkdir(parents=True, exist_ok=True)
            stamp_path.write_text(f"{fingerprint}\n", encoding="utf-8")

    return tuple(outputs)
