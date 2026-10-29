from dataclasses import dataclass

from .types import TypeType


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
    TypeType.BYTE: "Core.ByteProperty",
    TypeType.INT: "Core.IntProperty",
    TypeType.BOOL: "Core.BoolProperty",
    TypeType.FLOAT: "Core.FloatProperty",
    TypeType.STRING: "Core.StrProperty",
    TypeType.NAME: "Core.NameProperty",
    TypeType.OBJECT: "Core.ObjectProperty",
    TypeType.ARRAY: "Core.ArrayProperty",
    TypeType.CLASS: "Core.ClassProperty",
    TypeType.STRUCT: "Core.StructProperty",
    TypeType.ENUM: "Core.ByteProperty",
}

INTRINSICS = {path.casefold(): IntrinsicDefinition(path) for path in _INTRINSIC_PATHS}
