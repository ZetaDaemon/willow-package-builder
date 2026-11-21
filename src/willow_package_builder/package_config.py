from functools import lru_cache
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from willow_package_builder.logging.diagnostics import ConfigError
from willow_package_builder.upackage import FName

PACKAGE_CONFIG_FILENAME = "package.toml"
CLASSES_DIRECTORY_NAME = "Classes"
OBJECTS_DIRECTORY_NAME = "Objects"


@dataclass(frozen=True)
class PackageConfig:
    """Package configuration data."""

    directory: Path
    name: FName
    references: tuple[Path, ...]
    required: tuple[Path, ...]

    @staticmethod
    def _resolve_paths(
        directory: Path, data: dict[str, Any], key: str, *, reference_paths: tuple[Path, ...] = ()
    ) -> tuple[Path, ...]:
        values = data.get(key, [])

        if not isinstance(values, list) or not all(
            isinstance(value, str) and value for value in values
        ):
            msg = f"{directory}: {key} must be a list of paths"
            raise ConfigError(msg)

        values = cast("list[str]", values)
        resolved: list[Path] = []

        for value in values:
            explicit_path = (
                Path(value).is_absolute() or "/" in value or "\\" in value or value in (".", "..")
            )

            if key != "references" or explicit_path:
                resolved.append((directory / value).resolve())
                continue

            name = FName(value)
            matches = {
                candidate.resolve()
                for root in reference_paths
                for candidate in root.iterdir()
                if candidate.is_dir() and FName(candidate.name) == name
            }

            if not matches:
                msg = f"{directory}: Reference package {value!r} was not found in reference search directories"
                raise ConfigError(msg)

            if len(matches) > 1:
                candidates = ", ".join(str(path) for path in sorted(matches))
                msg = f"{directory}: Ambiguous reference package {value!r}: {candidates}"
                raise ConfigError(msg)

            resolved.append(matches.pop())

        return tuple(resolved)

    @classmethod
    def load(cls, directory: Path, reference_paths: tuple[Path, ...] = ()) -> PackageConfig:
        """Load the configuration for a package directory."""
        directory = directory.resolve()
        source_directories = (
            directory / CLASSES_DIRECTORY_NAME,
            directory / OBJECTS_DIRECTORY_NAME,
        )
        for source_directory in source_directories:
            if source_directory.exists() and not source_directory.is_dir():
                msg = f"Expected a directory: {source_directory}"
                raise ConfigError(msg)

        if not any(path.is_dir() for path in source_directories):
            msg = f"{directory}: Package must contain Classes or Objects"
            raise ConfigError(msg)

        config_path = directory / PACKAGE_CONFIG_FILENAME

        try:
            with config_path.open("rb") as file:
                data = tomllib.load(file)
        except (OSError, tomllib.TOMLDecodeError) as error:
            msg = f"{config_path}: {error}"
            raise ConfigError(msg) from error

        name = data.get("name")
        references = cls._resolve_paths(
            directory, data, "references", reference_paths=reference_paths
        )
        required = cls._resolve_paths(directory, data, "required")

        if not isinstance(name, str) or not name.strip():
            msg = f"{directory}: package name must be a nonempty string"
            raise ConfigError(msg)

        return cls(directory=directory, name=FName(name), references=references, required=required)

    def source_files(self) -> tuple[Path, ...]:
        """Get all UnrealScript source files, if Classes is present."""
        classes = self.directory / CLASSES_DIRECTORY_NAME

        if not classes.exists():
            return ()

        return tuple(sorted(classes.rglob("*.uc")))

    def output_path(self, target_directory: Path) -> Path:
        return target_directory.resolve() / f"{self.name}.upk"


def load_package_graph(
    directory: Path, reference_paths: tuple[Path, ...] = ()
) -> tuple[PackageConfig, ...]:
    reference_paths = tuple(path.resolve() for path in reference_paths)
    for path in reference_paths:
        if not path.is_dir():
            msg = f"Expected a reference search directory: {path}"
            raise ConfigError(msg)

    ordered: list[PackageConfig] = []
    completed: set[Path] = set()
    active: list[Path] = []
    package_names: dict[FName, Path] = {}

    def visit(package_directory: Path) -> None:
        package_directory = package_directory.resolve()

        if package_directory in active:
            cycle_start = active.index(package_directory)
            cycle = [*active[cycle_start:], package_directory]
            description = " -> ".join(str(path) for path in cycle)
            msg = f"Package dependency cycle: {description}"
            raise ConfigError(msg)

        if package_directory in completed:
            return

        config = PackageConfig.load(package_directory, reference_paths)

        name_key = config.name
        existing_directory = package_names.get(name_key)

        if existing_directory is not None and existing_directory != package_directory:
            msg = (
                f"Package name {config.name!r} is declared by both "
                f"{existing_directory} and {package_directory}"
            )
            raise ConfigError(msg)

        package_names[name_key] = package_directory
        active.append(package_directory)

        try:
            for dependency in (*config.references, *config.required):
                visit(dependency)
        finally:
            active.pop()

        completed.add(package_directory)
        ordered.append(config)

    visit(directory)
    return tuple(ordered)


def collect_build_packages(target: Path, packages: tuple[PackageConfig, ...]) -> set[Path]:
    configs = {config.directory: config for config in packages}
    build_packages: set[Path] = set()

    def visit(directory: Path) -> None:
        directory = directory.resolve()

        if directory in build_packages:
            return

        build_packages.add(directory)

        for dependency in configs[directory].required:
            visit(dependency)

    visit(target)
    return build_packages


def collect_visible_packages(
    config: PackageConfig, packages: tuple[PackageConfig, ...]
) -> set[FName]:
    return set(_collect_visible_packages(config, packages))


@lru_cache(maxsize=256)
def _collect_visible_packages(
    config: PackageConfig, packages: tuple[PackageConfig, ...]
) -> frozenset[FName]:
    configs = {package.directory: package for package in packages}

    visited: set[Path] = {config.directory}
    visible: set[FName] = set()

    def visit(directory: Path) -> None:
        if directory in visited:
            return

        visited.add(directory)
        dependency = configs[directory]
        visible.add(dependency.name)

        for reference in (*dependency.references, *dependency.required):
            visit(reference)

    for reference in (*config.references, *config.required):
        visit(reference)

    return frozenset(visible)
