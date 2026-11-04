from typing import TYPE_CHECKING

from willow_package_builder.compiler.syntax.modifiers import StructModifier
from willow_package_builder.upackage import PackageFlags

if TYPE_CHECKING:
    from willow_package_builder.compiler.syntax.declarations import StructDeclaration


def requires_binary_struct(declaration: StructDeclaration, package_flags: PackageFlags) -> bool:
    modifiers = declaration.modifiers

    return StructModifier.IMMUTABLE in modifiers or (
        StructModifier.IMMUTABLE_WHEN_COOKED in modifiers
        and bool(package_flags & PackageFlags.COOKED)
    )
