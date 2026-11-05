from dataclasses import dataclass

from .types import TypeCategory

IMPLICIT_EXPORT_CLASS_PATH = "Core.Class"


@dataclass(frozen=True)
class IntrinsicDefinition:
    path: str
    parent: str
    class_package: str = "Core"
    class_name: str = "Class"


_INTRINSIC_PARENTS: dict[str, str] = {
    "Core.Field": "Core.Object",
    "Core.Struct": "Core.Field",
    "Core.State": "Core.Struct",
    IMPLICIT_EXPORT_CLASS_PATH: "Core.State",
    "Core.Function": "Core.Struct",
    "Core.ScriptStruct": "Core.Struct",
    "Core.Enum": "Core.Field",
    "Core.Package": "Core.Object",
    "Core.Property": "Core.Field",
    "Core.IntProperty": "Core.Property",
    "Core.ByteProperty": "Core.Property",
    "Core.FloatProperty": "Core.Property",
    "Core.BoolProperty": "Core.Property",
    "Core.NameProperty": "Core.Property",
    "Core.StrProperty": "Core.Property",
    "Core.ObjectProperty": "Core.Property",
    "Core.ComponentProperty": "Core.ObjectProperty",
    "Core.ClassProperty": "Core.ObjectProperty",
    "Core.InterfaceProperty": "Core.Property",
    "Core.ArrayProperty": "Core.Property",
    "Core.MapProperty": "Core.Property",
    "Core.StructProperty": "Core.Property",
    "Core.DelegateProperty": "Core.Property",
    "Engine.StaticMesh": "Core.Object",
}

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

INTRINSICS = {
    path.casefold(): IntrinsicDefinition(path, parent)
    for path, parent in _INTRINSIC_PARENTS.items()
}
