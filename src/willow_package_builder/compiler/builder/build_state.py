from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from willow_package_builder.compiler.build_context import BuildContext
    from willow_package_builder.package_config import PackageConfig
    from willow_package_builder.upackage import Package

    from .exports import ClassExports, StructExports


@dataclass
class PackageBuildState:
    context: BuildContext
    config: PackageConfig
    package: Package

    classes: dict[str, ClassExports] = field(default_factory=dict)
    structs: dict[str, StructExports] = field(default_factory=dict)
