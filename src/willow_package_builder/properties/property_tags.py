from enum import StrEnum


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
    DELEGATE = "DelegateProperty"
    INT_ATTRIBUTE = "IntAttributeProperty"
    FLOAT_ATTRIBUTE = "FloatAttributeProperty"
    BYTE_ATTRIBUTE = "ByteAttributeProperty"
