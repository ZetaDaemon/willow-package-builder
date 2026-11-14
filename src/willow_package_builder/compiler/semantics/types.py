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

    def __str__(self) -> str:
        if self.category is TypeCategory.DELEGATE and self.declaration_path is not None:
            return f"delegate<{self.declaration_path}>"

        if self.declaration_path is not None:
            return str(self.declaration_path)

        if self.arguments:
            arguments = ", ".join(str(argument) for argument in self.arguments)
            return f"{self.category.value}<{arguments}>"

        return self.category.value
