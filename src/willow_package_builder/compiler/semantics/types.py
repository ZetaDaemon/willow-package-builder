from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from willow_package_builder.upackage import ReferencePath


class TypeCategory(StrEnum):
    VOID = "void"
    BYTE = "byte"
    INT = "int"
    BOOL = "bool"
    FLOAT = "float"
    STRING = "string"
    NAME = "name"
    OBJECT = "object"
    ARRAY = "array"
    CLASS = "class"
    STRUCT = "struct"
    ENUM = "enum"
    DELEGATE = "delegate"


@dataclass(frozen=True)
class ResolvedType:
    category: TypeCategory
    declaration_path: ReferencePath | None = None
    arguments: tuple[ResolvedType, ...] = ()
