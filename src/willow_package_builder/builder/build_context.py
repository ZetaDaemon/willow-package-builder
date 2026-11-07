from dataclasses import dataclass, field
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path

    from willow_package_builder.compiler.class_loading import ClassLoading
    from willow_package_builder.compiler.semantics.reference_database import ReferenceDatabase
    from willow_package_builder.package_config import PackageConfig
    from willow_package_builder.upackage import ReferencePath


@dataclass
class BuildContext:
    packages: tuple[PackageConfig, ...]
    build_packages: set[Path]
    references: ReferenceDatabase
    loader: ClassLoading
    parents: dict[ReferencePath, ReferencePath | None] = field(default_factory=dict, init=False)
    class_order: tuple[ReferencePath, ...] = field(default_factory=tuple, init=False)

    def refresh_class_hierarchy(self) -> None:
        """Update inheritance information after loading more declarations."""
        parents = self.references.resolve_parent_classes(self.packages)
        class_order = self.references.inheritance_order(parents)

        self.parents.clear()
        self.parents.update(parents)
        self.class_order = class_order
