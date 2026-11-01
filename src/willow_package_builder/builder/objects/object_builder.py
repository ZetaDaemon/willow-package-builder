from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from willow_package_builder.builder.build_component import BuildComponent
from willow_package_builder.compiler.semantics.types import ResolvedType, TypeCategory
from willow_package_builder.compiler.syntax.declarations import (
    StructDeclaration,
    TypeReference,
    VariableDeclaration,
)
from willow_package_builder.compiler.syntax.modifiers import StructModifier, VariableModifier
from willow_package_builder.logging import info
from willow_package_builder.logging.diagnostics import ObjectDefinitionError
from willow_package_builder.objects.declarations import FolderDeclaration, ObjectDeclaration
from willow_package_builder.objects.reader import walk_objects_directory
from willow_package_builder.package_config import collect_visible_packages
from willow_package_builder.payloads.instance_payload import (
    BoolPropertyOverride,
    BytePropertyOverride,
    EnumPropertyOverride,
    ObjectInstancePayload,
    PropertyOverride,
    StructPropertyOverride,
)
from willow_package_builder.payloads.property_values import (
    ArrayValue,
    BoolValue,
    ByteValue,
    EnumValue,
    FloatValue,
    IntValue,
    NameValue,
    ObjectReferenceValue,
    PropertyValue,
    StringValue,
)
from willow_package_builder.payloads.struct_value import BinaryStructValue, TaggedStructValue
from willow_package_builder.upackage import (
    INT32_MAX,
    UINT8_MAX,
    ExportFlags,
    FName,
    ObjectFlags,
    PackageFlags,
    ReferencePath,
    UObject,
)

if TYPE_CHECKING:
    from willow_package_builder.builder.references import PackageReferences

PROPERTY_TAG_NAMES: dict[TypeCategory, str] = {
    TypeCategory.INT: "IntProperty",
    TypeCategory.FLOAT: "FloatProperty",
    TypeCategory.BOOL: "BoolProperty",
    TypeCategory.STRING: "StrProperty",
    TypeCategory.NAME: "NameProperty",
    TypeCategory.BYTE: "ByteProperty",
    TypeCategory.ENUM: "ByteProperty",
    TypeCategory.OBJECT: "ObjectProperty",
    TypeCategory.CLASS: "ObjectProperty",
    TypeCategory.ARRAY: "ArrayProperty",
    TypeCategory.STRUCT: "StructProperty",
}


@dataclass
class ObjectBuilder(BuildComponent):
    references: PackageReferences

    declarations: list[FolderDeclaration | ObjectDeclaration] = field(
        default_factory=list, init=False
    )

    exports: dict[FolderDeclaration | ObjectDeclaration, UObject] = field(
        default_factory=dict, init=False
    )

    def read_objects(self) -> None:
        directory = self.config.directory / "Objects"

        if not directory.exists():
            self.declarations = []
            return

        self.declarations = walk_objects_directory(directory)

    def reserve_objects(self) -> None:
        visible = collect_visible_packages(self.config, self.context.packages)

        for declaration in self.declarations:
            if declaration.outer is None:
                outer = ReferencePath()
            else:
                outer = self.exports[declaration.outer].reference()

            export_flags = ExportFlags.NONE

            match declaration:
                case FolderDeclaration():
                    object_class = self.references.class_object_reference("Core.Package")
                    archetype = ReferencePath()

                    if declaration.outer is None:
                        export_flags = ExportFlags.FORCED_EXPORT

                case ObjectDeclaration():
                    if declaration.outer is None:
                        msg = (
                            f"{declaration.source}, document {declaration.document}: "
                            "Objects must be placed inside a logical package directory"
                        )
                        raise ObjectDefinitionError(msg)

                    class_path, _ = self.context.references.resolve_class(
                        declaration.class_name, self.config.name, visible
                    )

                    object_class = self.references.class_object_reference(class_path)
                    archetype = self.references.class_object_reference(
                        class_path, default_object=True
                    )

            obj = UObject(
                FName(declaration.name),
                ObjectFlags.DEFAULT_EXPORT,
                outer,
                object_class,
                archetype=archetype,
                export_flags=export_flags,
            )

            self.package.add_export(obj)
            self.exports[declaration] = obj

            if isinstance(declaration, ObjectDeclaration):
                info(f"Building object {obj.object_class}'{obj.reference()}'")

    def initialize_payloads(self) -> None:
        for obj in self.exports.values():
            obj.payload = ObjectInstancePayload()

    def _build_int_value(self, context: str, value: object) -> IntValue:
        if not isinstance(value, int) or isinstance(value, bool):
            msg = f"{context}: Expected an integer, got {value!r}"
            raise ObjectDefinitionError(msg)

        if not -(INT32_MAX + 1) <= value <= INT32_MAX:
            msg = f"{context}: Integer {value} is outside the int32 range"
            raise ObjectDefinitionError(msg)

        return IntValue(value)

    def _build_bool_value(self, context: str, value: object) -> BoolValue:
        if not isinstance(value, bool):
            msg = f"{context}: Expected a boolean, got {value!r}"
            raise ObjectDefinitionError(msg)

        return BoolValue(value)

    def _build_float_value(self, context: str, value: object) -> FloatValue:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            msg = f"{context}: Expected a number, got {value!r}"
            raise ObjectDefinitionError(msg)

        return FloatValue(float(value))

    def _build_string_value(self, context: str, value: object) -> StringValue:
        if not isinstance(value, str):
            msg = f"{context}: Expected a string, got {value!r}"
            raise ObjectDefinitionError(msg)

        return StringValue(value)

    def _build_name_value(self, context: str, value: object) -> NameValue:
        if not isinstance(value, str):
            msg = f"{context}: Expected a name string, got {value!r}"
            raise ObjectDefinitionError(msg)

        return NameValue(FName(value))

    def _build_byte_value(self, context: str, value: object) -> ByteValue:
        if not isinstance(value, int) or isinstance(value, bool):
            msg = f"{context}: Expected a byte integer, got {value!r}"
            raise ObjectDefinitionError(msg)

        if not 0 <= value <= UINT8_MAX:
            msg = f"{context}: Byte {value} is outside the range 0-{UINT8_MAX}"
            raise ObjectDefinitionError(msg)

        return ByteValue(value)

    def _build_enum_value(
        self, context: str, value: object, resolved_type: ResolvedType
    ) -> EnumValue:
        if not isinstance(value, str):
            msg = f"{context}: Expected an enum member name, got {value!r}"
            raise ObjectDefinitionError(msg)

        if resolved_type.declaration_path is None:
            msg = f"{context}: Resolved enum has no declaration path"
            raise ValueError(msg)

        owner_class, _, enum_name = resolved_type.declaration_path.rpartition(".")
        enum = self.context.references.resolve_enum(
            owner_class, enum_name, self.context.parents
        ).declaration

        matched = next(
            (member for member in enum.members if member.casefold() == value.casefold()), None
        )

        if matched is None:
            msg = (
                f"{context}: Unknown member {value!r} of {enum.name}; "
                f"expected one of {', '.join(enum.members)}"
            )
            raise ObjectDefinitionError(msg)

        return EnumValue(FName(enum.name), FName(matched), enum.members.index(matched))

    def _build_object_value(
        self, context: str, value: object, resolved_type: ResolvedType
    ) -> ObjectReferenceValue:
        if value is None:
            return ObjectReferenceValue(ReferencePath())

        if not isinstance(value, str) or not value.strip():
            msg = f"{context}: Expected a full object path or null, got {value!r}"
            raise ObjectDefinitionError(msg)

        # Accept Unreal's subobject separator as well as dotted paths.
        reference = ReferencePath(value.replace(":", "."))

        target = next(
            (
                declaration
                for declaration, obj in self.exports.items()
                if isinstance(declaration, ObjectDeclaration) and obj.reference() == reference
            ),
            None,
        )

        if target is None:
            msg = (
                f"{context}: No packaged object matches {value!r}; "
                "references to external objects are not implemented yet"
            )
            raise ObjectDefinitionError(msg)

        if resolved_type.declaration_path is None:
            msg = f"{context}: Object property has no declared class"
            raise ValueError(msg)

        visible = collect_visible_packages(self.config, self.context.packages)
        target_class, _ = self.context.references.resolve_class(
            target.class_name, self.config.name, visible
        )

        expected_class = resolved_type.declaration_path.casefold()
        compatible = any(
            owner.casefold() == expected_class
            for owner, _ in self.context.references.iter_class_hierarchy(
                target_class, self.context.parents
            )
        )

        if not compatible:
            msg = (
                f"{context}: Object {value!r} has class {target_class}, "
                f"which is not compatible with {resolved_type.declaration_path}"
            )
            raise ObjectDefinitionError(msg)

        return ObjectReferenceValue(self.exports[target].reference())

    def _build_class_value(
        self, context: str, value: object, resolved_type: ResolvedType
    ) -> ObjectReferenceValue:
        if value is None:
            return ObjectReferenceValue(ReferencePath())

        if not isinstance(value, str) or not value.strip() or "." not in value:
            msg = f"{context}: Expected a fully qualified class path or null"
            raise ObjectDefinitionError(msg)

        visible = collect_visible_packages(self.config, self.context.packages)
        class_path, _ = self.context.references.resolve_class(value, self.config.name, visible)

        bound = resolved_type.arguments[0]

        if bound.declaration_path is None:
            msg = f"{context}: Class property bound has no declaration path"
            raise ValueError(msg)

        compatible = any(
            owner.casefold() == bound.declaration_path.casefold()
            for owner, _ in self.context.references.iter_class_hierarchy(
                class_path, self.context.parents
            )
        )

        if not compatible:
            msg = f"{context}: Class {value!r} does not extend {bound.declaration_path}"
            raise ObjectDefinitionError(msg)

        reference = self.references.class_object_reference(class_path)
        return ObjectReferenceValue(reference)

    def _build_array_value(
        self, context: str, value: object, resolved_type: ResolvedType
    ) -> ArrayValue:
        if not isinstance(value, list):
            msg = f"{context}: Expected an array, got {value!r}"
            raise ObjectDefinitionError(msg)

        element_type = resolved_type.arguments[0]

        return ArrayValue(
            [
                self._build_value(f"{context}, element {index}", element, element_type)  # pyright: ignore[reportUnknownArgumentType]
                for index, element in enumerate(value)  # pyright: ignore[reportUnknownArgumentType]
            ]
        )

    def _build_binary_struct_value(
        self,
        context: str,
        value: dict[str, object],
        declaration: StructDeclaration,
        owner_class: str,
    ) -> BinaryStructValue:
        if declaration.parent is not None:
            msg = f"{context}: Inherited binary struct layouts are not implemented yet"
            raise NotImplementedError(msg)

        supplied: dict[str, object] = {}

        for name, raw_value in value.items():
            key = name.casefold()

            if key in supplied:
                msg = f"{context}: Duplicate struct field {name!r}"
                raise ObjectDefinitionError(msg)

            supplied[key] = raw_value

        field_names = {variable.name.casefold() for variable in declaration.variables}

        for name in supplied:
            if name not in field_names:
                msg = f"{context}: Unknown field {name!r} on {declaration.name}"
                raise ObjectDefinitionError(msg)

        visible = collect_visible_packages(self.config, self.context.packages)
        fields: list[PropertyValue] = []

        for variable in declaration.variables:
            key = variable.name.casefold()
            field_context = f"{context}, field {variable.name!r}"

            if key not in supplied:
                msg = f"{field_context}: Omitting binary struct fields is not implemented yet"
                raise NotImplementedError(msg)

            if any(
                modifier in (VariableModifier.NATIVE, VariableModifier.TRANSIENT)
                for modifier in variable.modifiers
            ):
                msg = f"{field_context}: This binary field layout is not implemented yet"
                raise NotImplementedError(msg)

            field_type = self.context.references.resolve_type(
                variable.type_ref, owner_class, visible, self.context.parents
            )

            raw_value = supplied[key]

            if variable.array_dimension == 1:
                fields.append(self._build_value(field_context, raw_value, field_type))
            else:
                if not isinstance(raw_value, list):
                    msg = f"{field_context}: Expected a fixed-size array"
                    raise ObjectDefinitionError(msg)

                if len(raw_value) != variable.array_dimension:
                    msg = (
                        f"{field_context}: Expected {variable.array_dimension} elements, "
                        f"got {len(raw_value)}"
                    )
                    raise ObjectDefinitionError(msg)

                fields.extend(
                    self._build_value(f"{field_context}, element {index}", element, field_type)
                    for index, element in enumerate(raw_value)
                )

        return BinaryStructValue(fields)

    def _build_struct_value(
        self, context: str, value: object, resolved_type: ResolvedType
    ) -> TaggedStructValue | BinaryStructValue:
        if not isinstance(value, dict):
            msg = f"{context}: Expected a struct mapping, got {value!r}"
            raise ObjectDefinitionError(msg)

        struct_path = resolved_type.declaration_path

        if struct_path is None:
            msg = f"{context}: Struct type has no declaration path"
            raise ValueError(msg)

        visible = collect_visible_packages(self.config, self.context.packages)

        # Check the layout of the struct and its ancestors.
        current = struct_path
        visited: set[str] = set()

        while True:
            key = current.casefold()

            if key in visited:
                msg = f"{context}: Struct inheritance cycle at {current}"
                raise ObjectDefinitionError(msg)

            visited.add(key)
            owner_class, _, struct_name = current.rpartition(".")
            member = self.context.references.resolve_struct(
                owner_class, struct_name, self.context.parents
            )
            declaration = member.declaration

            if StructModifier.NATIVE in declaration.modifiers:
                msg = f"{context}: Native struct layout {current} is not implemented yet"
                raise NotImplementedError(msg)

            requires_binary = StructModifier.IMMUTABLE in declaration.modifiers or (
                StructModifier.IMMUTABLE_WHEN_COOKED in declaration.modifiers
                and bool(self.package.flags & PackageFlags.COOKED)
            )

            if requires_binary:
                if current.casefold() != struct_path.casefold():
                    msg = f"{context}: Inherited binary struct layouts are not implemented yet"
                    raise NotImplementedError(msg)

                return self._build_binary_struct_value(
                    context, value, declaration, member.owner_class
                )

            if declaration.parent is None:
                break

            parent = self.context.references.resolve_type(
                TypeReference(declaration.parent), member.owner_class, visible, self.context.parents
            )

            if parent.category is not TypeCategory.STRUCT or parent.declaration_path is None:
                msg = f"{context}: Invalid parent of struct {current}"
                raise ObjectDefinitionError(msg)

            current = parent.declaration_path

        fields: list[PropertyOverride] = []
        seen: set[str] = set()

        for name, raw_value in value.items():
            if not isinstance(name, str):
                msg = f"{context}: Struct field names must be strings"
                raise ObjectDefinitionError(msg)

            key = name.casefold()

            if key in seen:
                msg = f"{context}: Duplicate struct field {name!r}"
                raise ObjectDefinitionError(msg)

            seen.add(key)
            field_context = f"{context}, field {name!r}"

            member = self.context.references.resolve_struct_variable(
                struct_path, name, self.context.parents, visible
            )
            variable = member.declaration

            field_type = self.context.references.resolve_type(
                variable.type_ref, member.owner_class, visible, self.context.parents
            )

            fields.extend(
                self._build_field_overrides(field_context, variable, raw_value, field_type)
            )

        return TaggedStructValue(fields)

    def _build_value(  # noqa: C901, PLR0911
        self, context: str, value: object, resolved_type: ResolvedType
    ) -> PropertyValue:
        match resolved_type.category:
            case TypeCategory.INT:
                return self._build_int_value(context, value)

            case TypeCategory.BOOL:
                return self._build_bool_value(context, value)

            case TypeCategory.FLOAT:
                return self._build_float_value(context, value)

            case TypeCategory.STRING:
                return self._build_string_value(context, value)

            case TypeCategory.NAME:
                return self._build_name_value(context, value)

            case TypeCategory.BYTE:
                return self._build_byte_value(context, value)

            case TypeCategory.ENUM:
                return self._build_enum_value(context, value, resolved_type)

            case TypeCategory.OBJECT:
                return self._build_object_value(context, value, resolved_type)

            case TypeCategory.CLASS:
                return self._build_class_value(context, value, resolved_type)

            case TypeCategory.ARRAY:
                return self._build_array_value(context, value, resolved_type)

            case TypeCategory.STRUCT:
                return self._build_struct_value(context, value, resolved_type)

            case _:
                msg = (
                    f"{context}: Values of type "
                    f"{resolved_type.category.value} are not implemented yet"
                )
                raise NotImplementedError(msg)

    def _build_property_override(
        self, context: str, property_name: FName, value: object, resolved_type: ResolvedType
    ) -> PropertyOverride:
        value_data = self._build_value(context, value, resolved_type)
        property_type = FName(PROPERTY_TAG_NAMES[resolved_type.category])

        match resolved_type.category:
            case TypeCategory.BOOL:
                return BoolPropertyOverride(property_name, property_type, value_data)

            case TypeCategory.BYTE:
                return BytePropertyOverride(property_name, property_type, value_data)

            case TypeCategory.ENUM:
                return EnumPropertyOverride(property_name, property_type, value_data)

            case TypeCategory.STRUCT:
                if resolved_type.declaration_path is None:
                    msg = f"{context}: Struct type has no declaration path"
                    raise ValueError(msg)

                owner_class, _, struct_name = resolved_type.declaration_path.rpartition(".")
                member = self.context.references.resolve_struct(
                    owner_class, struct_name, self.context.parents
                )

                return StructPropertyOverride(
                    property_name, property_type, value_data, FName(member.declaration.name)
                )

            case _:
                return PropertyOverride(property_name, property_type, value_data)

    def _build_field_overrides(
        self,
        context: str,
        variable: VariableDeclaration,
        value: object,
        resolved_type: ResolvedType,
    ) -> list[PropertyOverride]:
        name = FName(variable.name)

        if variable.array_dimension == 1:
            return [self._build_property_override(context, name, value, resolved_type)]

        if not isinstance(value, list):
            msg = f"{context}: Expected a fixed-size array"
            raise ObjectDefinitionError(msg)

        if len(value) != variable.array_dimension:
            msg = f"{context}: Expected {variable.array_dimension} elements, got {len(value)}"
            raise ObjectDefinitionError(msg)

        overrides: list[PropertyOverride] = []

        for index, element in enumerate(value):
            override = self._build_property_override(
                f"{context}, element {index}", name, element, resolved_type
            )
            override.array_index = index
            overrides.append(override)

        return overrides

    def _build_properties(
        self, declaration: ObjectDeclaration, visible_packages: set[str]
    ) -> list[PropertyOverride]:
        class_path, _ = self.context.references.resolve_class(
            declaration.class_name, self.config.name, visible_packages
        )

        properties: list[PropertyOverride] = []

        for name, value in declaration.properties.items():
            context = f"{declaration.source}, document {declaration.document}, property {name!r}"

            member = self.context.references.resolve_variable(
                class_path, name, self.context.parents
            )
            variable = member.declaration

            resolved = self.context.references.resolve_type(
                variable.type_ref, member.owner_class, visible_packages, self.context.parents
            )

            if variable.array_dimension == 1:
                properties.append(
                    self._build_property_override(context, FName(variable.name), value, resolved)
                )

            properties.extend(self._build_field_overrides(context, variable, value, resolved))

        return properties

    def build_all_properties(self) -> None:
        """Build all properties for all objects."""
        visible = collect_visible_packages(self.config, self.context.packages)

        for declaration in self.declarations:
            if not isinstance(declaration, ObjectDeclaration):
                continue

            properties: list[PropertyOverride] = self._build_properties(declaration, visible)
            self.exports[declaration].payload = ObjectInstancePayload(properties=properties)
