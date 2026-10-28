import tomllib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from willow_package_builder.logging import ConfigError

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class PackageConfig:
    """Package configuration data."""

    directory: Path
    name: str
    references: tuple[Path, ...]
    required: tuple[Path, ...]

    @staticmethod
    def _resolve_paths(directory: Path, data: dict[str, Any], key: str) -> tuple[Path, ...]:
        values = data.get(key, [])

        if not isinstance(values, list) or not all(
            isinstance(value, str) and value for value in values
        ):
            msg = f"{directory}: {key} must be a list of paths"
            raise ConfigError(msg)

        values = cast("list[str]", values)
        return tuple((directory / value).resolve() for value in values)

    @classmethod
    def load(cls, directory: Path) -> PackageConfig:
        """Load the configuration for a package directory."""
        directory = directory.resolve()

        with (directory / "package.toml").open("rb") as file:
            data = tomllib.load(file)

        name = data.get("name")
        references = cls._resolve_paths(directory, data, "references")
        required = cls._resolve_paths(directory, data, "required")

        if not isinstance(name, str) or not name.strip():
            msg = f"{directory}: package name must be a nonempty string"
            raise ConfigError(msg)

        return cls(
            directory=directory,
            name=name,
            references=tuple((directory / reference).resolve() for reference in references),
            required=tuple((directory / r).resolve() for r in required),
        )

    def source_files(self) -> tuple[Path, ...]:
        """Get all .uc files."""
        classes = self.directory / "Classes"

        if not classes.is_dir():
            msg = f"Package has no Classes directory: {self.directory}"
            raise ConfigError(msg)

        return tuple(sorted(classes.rglob("*.uc")))

    def output_path(self, target_directory: Path) -> Path:
        return target_directory.resolve() / f"{self.name}.upk"


def load_package_graph(directory: Path) -> tuple[PackageConfig, ...]:
    ordered: list[PackageConfig] = []
    completed: set[Path] = set()
    active: list[Path] = []
    package_names: dict[str, Path] = {}

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

        config = PackageConfig.load(package_directory)

        name_key = config.name.casefold()
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
) -> set[str]:
    configs = {package.directory: package for package in packages}

    visited: set[Path] = {config.directory}
    visible: set[str] = set()

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

    return visible
