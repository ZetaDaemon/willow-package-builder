from dataclasses import dataclass, field

from willow_package_builder.upackage import (
    CLASS_CLASS_NAME,
    CORE_PACKAGE_NAME,
    FName,
    ReferencePath,
)

from .types import TypeCategory


@dataclass(frozen=True)
class IntrinsicDefinition:
    path: ReferencePath
    parent: ReferencePath
    class_package: FName = field(default_factory=lambda: CORE_PACKAGE_NAME)
    class_name: FName = field(default_factory=lambda: CLASS_CLASS_NAME)


_INTRINSIC_PARENTS: dict[ReferencePath, ReferencePath] = {
    ReferencePath(path): ReferencePath(parent)
    for path, parent in {
        "Core.Field": "Core.Object",
        "Core.Struct": "Core.Field",
        "Core.State": "Core.Struct",
        "Core.Class": "Core.State",
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
    }.items()
}


PROPERTY_CLASS_PATHS: dict[TypeCategory, ReferencePath] = {
    category: ReferencePath(path)
    for category, path in {
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
    }.items()
}

INTRINSICS: dict[ReferencePath, IntrinsicDefinition] = {
    path: IntrinsicDefinition(path, parent) for path, parent in _INTRINSIC_PARENTS.items()
}
