import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING

from willow_package_builder.builder.struct_layout import requires_binary_struct
from willow_package_builder.compiler.semantics.intrinsics import (
    IMPLICIT_EXPORT_CLASS_PATH,
    IntrinsicDefinition,
)
from willow_package_builder.compiler.semantics.types import ResolvedType, TypeCategory
from willow_package_builder.compiler.syntax.modifiers import StructModifier, VariableModifier
from willow_package_builder.package_config import collect_visible_packages
from willow_package_builder.properties.property_tags import PropertyTag

from .values import (
    ArrayValue,
    BoolValue,
    ByteValue,
    EnumValue,
    FloatValue,
    IntValue,
    NameValue,
    NullValue,
    ObjectValue,
    StringValue,
    StructValue,
    Value,
)

if TYPE_CHECKING:
    from willow_package_builder.builder.build_context import BuildContext
    from willow_package_builder.compiler.syntax.declarations import VariableDeclaration
    from willow_package_builder.upackage import Package

from willow_package_builder.upackage import (
    ExternalReference,
    FName,
    ReferencePath,
    UObject,
    serialize_fstring,
)

PROPERTY_TAG_NAMES: dict[TypeCategory, PropertyTag] = {
    TypeCategory.INT: PropertyTag.INT,
    TypeCategory.BYTE: PropertyTag.BYTE,
    TypeCategory.ENUM: PropertyTag.BYTE,
    TypeCategory.FLOAT: PropertyTag.FLOAT,
    TypeCategory.BOOL: PropertyTag.BOOL,
    TypeCategory.STRING: PropertyTag.STRING,
    TypeCategory.NAME: PropertyTag.NAME,
    TypeCategory.OBJECT: PropertyTag.OBJECT,
    TypeCategory.CLASS: PropertyTag.OBJECT,
    TypeCategory.ARRAY: PropertyTag.ARRAY,
    TypeCategory.STRUCT: PropertyTag.STRUCT,
}


@dataclass
class ValueSerializer:
    package: Package
    context: BuildContext

    def object_class_path(self, target: UObject | ExternalReference) -> str:
        """Get the declared class of a registered object."""
        if isinstance(target, ExternalReference):
            return f"{target.class_package}.{target.class_name}"

        if target.object_class.is_none():
            return IMPLICIT_EXPORT_CLASS_PATH

        class_object = self.package.lookup_object_by_path(target.object_class)

        if isinstance(class_object, ExternalReference):
            return str(class_object.reference())

        return f"{self.package.name}.{class_object.reference()}"

    def validate_object_reference(
        self, value: ObjectValue, target: UObject | ExternalReference, resolved_type: ResolvedType
    ) -> None:
        expected = resolved_type.declaration_path

        if expected is None:
            msg = "Resolved object type has no declaration path"
            raise ValueError(msg)

        self.validate_reference_annotation(value, expected, self.object_class_path(target))

    def serialize_binary_field(
        self,
        name: FName,
        value: Value,
        definition: VariableDeclaration,
        resolved_type: ResolvedType,
    ) -> bytes:
        if definition.array_dimension == 1:
            return self.serialize_value(value, resolved_type)

        if not isinstance(value, ArrayValue):
            msg = f"Fixed-array field {name} requires an ArrayValue"
            raise TypeError(msg)

        if len(value.elements) != definition.array_dimension:
            msg = (
                f"Fixed-array field {name} requires "
                f"{definition.array_dimension} elements, "
                f"got {len(value.elements)}"
            )
            raise ValueError(msg)

        return b"".join(self.serialize_value(element, resolved_type) for element in value.elements)

    def resolve_field_type(self, definition: VariableDeclaration, owner_class: str) -> ResolvedType:
        package_name = owner_class.partition(".")[0]
        config = next(
            config
            for config in self.context.packages
            if config.name.casefold() == package_name.casefold()
        )
        visible = collect_visible_packages(config, self.context.packages)

        return self.context.references.resolve_type(
            definition.type_ref, owner_class, visible, self.context.parents
        )

    def serialize_property(
        self, name: FName, value: Value, resolved_type: ResolvedType, array_index: int = 0
    ) -> bytes:
        """Serialize one property tag and its value."""
        property_type = PROPERTY_TAG_NAMES[resolved_type.category]
        metadata = b""

        match property_type, value:
            case PropertyTag.BOOL, BoolValue():
                metadata = struct.pack("<?", value.value)
                data = b""

            case PropertyTag.BYTE, EnumValue():
                metadata = value.enum_name.serialize(self.package)
                data = value.member_name.serialize(self.package)

            case PropertyTag.BYTE, ByteValue():
                metadata = FName("None").serialize(self.package)
                data = self.serialize_value(value, resolved_type)

            case PropertyTag.STRUCT, StructValue():
                if value.struct_path is None:
                    msg = f"Struct property {name} has no struct type"
                    raise ValueError(msg)

                struct_name = FName(value.struct_path.rsplit(".", 1)[-1])
                metadata = struct_name.serialize(self.package)
                data = self.serialize_value(value, resolved_type)

            case _:
                data = self.serialize_value(value, resolved_type)

        return (
            name.serialize(self.package)
            + FName(property_type).serialize(self.package)
            + struct.pack("<ii", len(data), array_index)
            + metadata
            + data
        )

    def serialize_field(
        self,
        name: FName,
        value: Value,
        definition: VariableDeclaration,
        resolved_type: ResolvedType,
    ) -> bytes:
        """Serialize a property using its declared array dimension and type."""
        if definition.array_dimension == 1:
            return self.serialize_property(name, value, resolved_type)

        if not isinstance(value, ArrayValue):
            msg = f"Fixed-array property {name} requires an ArrayValue"
            raise TypeError(msg)

        if len(value.elements) != definition.array_dimension:
            msg = (
                f"Fixed-array property {name} requires "
                f"{definition.array_dimension} elements, "
                f"got {len(value.elements)}"
            )
            raise ValueError(msg)

        return b"".join(
            self.serialize_property(name, element, resolved_type, index)
            for index, element in enumerate(value.elements)
        )

    def serialize_struct(self, value: StructValue) -> bytes:
        path = value.struct_path

        if path is None:
            msg = "Struct value has no declaration path"
            raise ValueError(msg)

        hierarchy = self.context.references.struct_hierarchy(
            path, self.context.parents, self.context.packages
        )

        binary = False

        for _, declaration in hierarchy:
            if StructModifier.NATIVE in declaration.modifiers:
                msg = f"Native struct serialization is not implemented: {path}"
                raise NotImplementedError(msg)

            binary |= requires_binary_struct(declaration, self.package.flags)

        if binary:
            if len(hierarchy) != 1:
                msg = "Inherited binary struct serialization is not implemented"
                raise NotImplementedError(msg)

            declaration = hierarchy[0][1]
            data: list[bytes] = []

            for definition in declaration.variables:
                if any(
                    modifier in (VariableModifier.NATIVE, VariableModifier.TRANSIENT)
                    for modifier in definition.modifiers
                ):
                    msg = f"Binary field layout is not implemented: {path}.{definition.name}"
                    raise NotImplementedError(msg)

                name = FName(definition.name)

                if name not in value.values:
                    msg = f"Binary struct {path} is missing field {name}"
                    raise ValueError(msg)

                owner_class = hierarchy[0][0]
                resolved = self.resolve_field_type(definition, owner_class)

                data.append(
                    self.serialize_binary_field(name, value.values[name], definition, resolved)
                )

            return b"".join(data)

        return self.serialize_struct_fields(path, value.values)

    def serialize_class_reference(self, value: ObjectValue, resolved_type: ResolvedType) -> bytes:
        """Resolve a qualified class literal and serialize its package index."""
        self.validate_reference_annotation(
            value, IMPLICIT_EXPORT_CLASS_PATH, IMPLICIT_EXPORT_CLASS_PATH
        )
        path = value.path
        package_name, separator, class_name = path.partition(".")

        if not separator:
            msg = f"Unqualified class literal resolution is not implemented: {path}"
            raise NotImplementedError(msg)

        definition = self.context.references.lookup_class(path)
        bound = resolved_type.arguments[0].declaration_path

        if bound is None:
            msg = "Resolved class bound has no declaration path"
            raise ValueError(msg)

        if not self.context.references.is_subclass(path, bound, self.context.parents):
            msg = f"Class {path} does not extend {bound}"
            raise ValueError(msg)

        if isinstance(definition, IntrinsicDefinition):
            package_name, _, class_name = definition.path.partition(".")
            class_package = definition.class_package
            object_class = definition.class_name
        else:
            class_name = definition.name
            class_package = "Core"
            object_class = "Class"

            if package_name.casefold() == str(self.package.name).casefold():
                reference = ReferencePath(class_name)
                target = self.package.lookup_object_by_path(reference)
                return target.reference().serialize(self.package)

            config = next(
                config
                for config in self.context.packages
                if config.name.casefold() == package_name.casefold()
            )
            package_name = config.name

        outer = self.package.ensure_import(package_name, ReferencePath(), "Core", "Package")
        reference = self.package.ensure_import(class_name, outer, class_package, object_class)

        return reference.serialize(self.package)

    def serialize_object_reference(self, value: ObjectValue, resolved_type: ResolvedType) -> bytes:
        """Resolve and serialize an object reference without modifying its value."""
        if resolved_type.category is TypeCategory.CLASS:
            return self.serialize_class_reference(value, resolved_type)

        if value.reference is not None:
            target = self.package.lookup_object_by_path(value.reference)
            self.validate_object_reference(value, target, resolved_type)
            return target.reference().serialize(self.package)

        path = value.path.replace(":", ".")
        candidates = [ReferencePath(path)]

        # Local exports are registered without the physical UPK package prefix.
        package_name, separator, relative_path = path.partition(".")

        if separator and package_name.casefold() == str(self.package.name).casefold():
            candidates.append(ReferencePath(relative_path))

        for candidate in candidates:
            try:
                target = self.package.lookup_object_by_path(candidate)
            except KeyError:
                continue

            self.validate_object_reference(value, target, resolved_type)
            return target.reference().serialize(self.package)

        msg = f"Object reference target is not registered: {value.path}"
        raise ValueError(msg)

    def serialize_value(self, value: Value, resolved_type: ResolvedType) -> bytes:
        """Serialize raw value data without a property tag."""
        match value:
            case NullValue():
                return struct.pack("<i", 0)

            case IntValue(value=number):
                return struct.pack("<i", number)

            case ByteValue(value=number):
                return struct.pack("<B", number)

            case FloatValue(value=number):
                return struct.pack("<f", number)

            case BoolValue(value=boolean):
                return struct.pack("<?", boolean)

            case StringValue(value=text):
                return serialize_fstring(text)

            case NameValue(value=name):
                return name.serialize(self.package)

            case EnumValue(index=index):
                return struct.pack("<B", index)

            case ArrayValue(elements=elements):
                element_type = resolved_type.arguments[0]

                return struct.pack("<i", len(elements)) + b"".join(
                    self.serialize_value(element, element_type) for element in elements
                )

            case StructValue():
                return self.serialize_struct(value)

            case ObjectValue():
                return self.serialize_object_reference(value, resolved_type)

            case _:
                msg = f"Raw serialization for {type(value).__name__} is not implemented"
                raise NotImplementedError(msg)

    def serialize_properties(self, class_path: str, values: dict[FName, Value]) -> bytes:
        """Serialize tagged object properties and their terminator."""
        data: list[bytes] = []

        for name, value in values.items():
            member = self.context.references.resolve_variable(
                class_path, str(name), self.context.parents
            )
            resolved = self.resolve_field_type(member.declaration, member.owner_class)

            data.append(self.serialize_field(name, value, member.declaration, resolved))

        return b"".join(data) + FName("None").serialize(self.package)

    def serialize_struct_fields(self, struct_path: str, values: dict[FName, Value]) -> bytes:
        owner = struct_path.rpartition(".")[0]
        package_name = owner.partition(".")[0]
        config = next(
            config
            for config in self.context.packages
            if config.name.casefold() == package_name.casefold()
        )
        visible = collect_visible_packages(config, self.context.packages)
        data: list[bytes] = []

        for name, value in values.items():
            member = self.context.references.resolve_struct_variable(
                struct_path, str(name), self.context.parents, visible
            )
            resolved = self.resolve_field_type(member.declaration, member.owner_class)

            data.append(self.serialize_field(name, value, member.declaration, resolved))

        return b"".join(data) + FName("None").serialize(self.package)

    def validate_reference_annotation(
        self, value: ObjectValue, expected_class: str, actual_class: str
    ) -> None:
        annotation = value.class_name

        if not self.context.references.is_subclass(
            annotation, expected_class, self.context.parents
        ):
            msg = f"Reference annotation {annotation} does not extend {expected_class}"
            raise ValueError(msg)

        if not self.context.references.is_subclass(actual_class, annotation, self.context.parents):
            msg = (
                f"Reference {value.path} has class {actual_class}, "
                f"which does not extend annotation {annotation}"
            )
            raise ValueError(msg)
