from dataclasses import dataclass

from .types import TypeCategory


@dataclass(frozen=True)
class IntrinsicDefinition:
    path: str
    class_package: str = "Core"
    class_name: str = "Class"


_INTRINSIC_PATHS = (
    "Core.Class",
    "Core.Function",
    "Core.ScriptStruct",
    "Core.Enum",
    "Core.IntProperty",
    "Core.ByteProperty",
    "Core.FloatProperty",
    "Core.BoolProperty",
    "Core.NameProperty",
    "Core.StrProperty",
    "Core.ObjectProperty",
    "Core.ComponentProperty",
    "Core.ClassProperty",
    "Core.InterfaceProperty",
    "Core.ArrayProperty",
    "Core.MapProperty",
    "Core.StructProperty",
    "Core.DelegateProperty",
)

PROPERTY_CLASS_PATHS = {
    TypeCategory.BYTE: "Core.ByteProperty",
    TypeCategory.INT: "Core.IntProperty",
    TypeCategory.BOOL: "Core.BoolProperty",
    TypeCategory.FLOAT: "Core.FloatProperty",
    TypeCategory.STRING: "Core.StrProperty",
    TypeCategory.NAME: "Core.NameProperty",
    TypeCategory.OBJECT: "Core.ObjectProperty",
    TypeCategory.ARRAY: "Core.ArrayProperty",
    TypeCategory.CLASS: "Core.ClassProperty",
    TypeCategory.STRUCT: "Core.StructProperty",
    TypeCategory.ENUM: "Core.ByteProperty",
}

INTRINSICS = {path.casefold(): IntrinsicDefinition(path) for path in _INTRINSIC_PATHS}
