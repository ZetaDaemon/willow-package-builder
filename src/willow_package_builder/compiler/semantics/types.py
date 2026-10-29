from dataclasses import dataclass
from enum import StrEnum


class TypeType(StrEnum):
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
    type: TypeType
    declaration_path: str | None = None
    arguments: tuple[ResolvedType, ...] = ()
