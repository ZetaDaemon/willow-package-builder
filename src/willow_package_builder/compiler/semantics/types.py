from dataclasses import dataclass
from enum import StrEnum


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


@dataclass(frozen=True)
class ResolvedType:
    category: TypeCategory
    declaration_path: str | None = None
    arguments: tuple[ResolvedType, ...] = ()
