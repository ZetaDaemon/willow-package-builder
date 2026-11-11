from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from willow_package_builder.compiler.syntax.declarations import DefaultObjectDeclaration
    from willow_package_builder.upackage import FName, ReferencePath


@dataclass
class DefaultObjectTemplate:
    """An effective template with its parent-to-child declaration layers."""

    class_path: ReferencePath
    layers: list[tuple[ReferencePath, DefaultObjectDeclaration]] = field(default_factory=list)
    children: dict[FName, DefaultObjectTemplate] = field(default_factory=dict)
