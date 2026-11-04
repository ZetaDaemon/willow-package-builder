from enum import StrEnum

from willow_package_builder.compiler.semantics.types import TypeCategory


class PropertyTag(StrEnum):
    INT = "IntProperty"
    BYTE = "ByteProperty"
    FLOAT = "FloatProperty"
    BOOL = "BoolProperty"
    STRING = "StrProperty"
    NAME = "NameProperty"
    OBJECT = "ObjectProperty"
    ARRAY = "ArrayProperty"
    STRUCT = "StructProperty"
