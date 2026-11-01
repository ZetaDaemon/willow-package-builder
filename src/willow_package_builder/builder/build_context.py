from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from willow_package_builder.compiler.semantics.references import ReferenceDatabase
    from willow_package_builder.package_config import PackageConfig


@dataclass
class BuildContext:
    packages: tuple[PackageConfig, ...]
    build_packages: set[Path]
    references: ReferenceDatabase
    parents: dict[str, str | None]
    class_order: tuple[str, ...]
