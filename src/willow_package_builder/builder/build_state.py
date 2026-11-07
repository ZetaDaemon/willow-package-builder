from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from willow_package_builder.builder.build_context import BuildContext
    from willow_package_builder.package_config import PackageConfig
    from willow_package_builder.upackage import Package, ReferencePath

    from .classes.exports import ClassExport, StructExport


@dataclass
class PackageBuildState:
    context: BuildContext
    config: PackageConfig
    package: Package

    classes: dict[ReferencePath, ClassExport] = field(default_factory=dict)
    structs: dict[ReferencePath, StructExport] = field(default_factory=dict)
