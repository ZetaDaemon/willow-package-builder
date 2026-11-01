from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from willow_package_builder.compiler.syntax.declarations import (
        ClassDeclaration,
        StructDeclaration,
    )
    from willow_package_builder.upackage import UObject


@dataclass
class ClassExports:
    declaration: ClassDeclaration
    class_object: UObject
    default_object: UObject


@dataclass
class StructExports:
    owner_class: str
    declaration: StructDeclaration
    struct_object: UObject
