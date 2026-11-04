from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from willow_package_builder.builder.build_context import BuildContext
    from willow_package_builder.package_config import PackageConfig
    from willow_package_builder.upackage import Package

    from .classes.exports import ClassExport, StructExport


@dataclass
class PackageBuildState:
    context: BuildContext
    config: PackageConfig
    package: Package

    classes: dict[str, ClassExport] = field(default_factory=dict)
    structs: dict[str, StructExport] = field(default_factory=dict)
