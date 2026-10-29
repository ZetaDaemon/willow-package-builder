from abc import ABC
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from willow_package_builder.compiler.build_context import BuildContext
    from willow_package_builder.package_config import PackageConfig
    from willow_package_builder.upackage import Package

    from .build_state import PackageBuildState
    from .exports import ClassExports, StructExports


@dataclass
class BuildComponent(ABC):
    """ABC for each build component."""

    state: PackageBuildState

    @property
    def context(self) -> BuildContext:
        """Access context from state."""
        return self.state.context

    @property
    def config(self) -> PackageConfig:
        """Access config from state."""
        return self.state.config

    @property
    def package(self) -> Package:
        """Access package from state."""
        return self.state.package

    @property
    def classes(self) -> dict[str, ClassExports]:
        """Access classes from state."""
        return self.state.classes

    @property
    def structs(self) -> dict[str, StructExports]:
        """Access structs from state."""
        return self.state.structs
