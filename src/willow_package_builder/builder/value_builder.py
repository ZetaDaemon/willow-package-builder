from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from willow_package_builder.compiler.semantics.intrinsics import IMPLICIT_EXPORT_CLASS_PATH
from willow_package_builder.compiler.semantics.types import ResolvedType, TypeCategory
from willow_package_builder.compiler.syntax.parser.defaults_parser import IndexedArrayDefaults
from willow_package_builder.logging import CompilationError, ValueBuildError
from willow_package_builder.package_config import collect_visible_packages
from willow_package_builder.properties.reference_text import parse_reference_text
from willow_package_builder.properties.values import (
    ArrayValue,
    BoolValue,
    ByteValue,
    FloatValue,
    IdentifierValue,
    IntValue,
    NameValue,
    NullValue,
    ObjectValue,
    StringValue,
    StructValue,
    Value,
)
from willow_package_builder.upackage import INT32_MAX, UINT8_MAX, FName

from .build_component import BuildComponent

if TYPE_CHECKING:
    from willow_package_builder.builder.classes.struct_builder import StructBuilder
    from willow_package_builder.compiler.syntax.declarations import VariableDeclaration

    from .classes.enum_builder import EnumBuilder


@dataclass
class ValueBuilder(BuildComponent):
    enums: EnumBuilder
    struct_builder: StructBuilder
    implicit_fixed_index: bool = field(default=False, kw_only=True)
    allow_dump_fixups: bool = field(default=False, kw_only=True)

    def _build_object_value(
        self, context: str, value: object, resolved_type: ResolvedType
    ) -> ObjectValue | NullValue:
        if value is None:
            return NullValue()

        if not isinstance(value, str) or not value.strip():
            msg = f"{context}: Expected an object reference or null, got {value!r}"
            raise ValueBuildError(msg)

        class_path = resolved_type.declaration_path

        if class_path is None:
            msg = f"{context}: Object property has no declared class"
            raise ValueError(msg)

        annotation, path = parse_reference_text(context, value)
        annotation = self.resolve_reference_annotation(context, annotation, class_path)
        return ObjectValue(annotation, path)

    def _build_class_value(self, context: str, value: object) -> ObjectValue | NullValue:
        if value is None:
            return NullValue()

        if not isinstance(value, str) or not value.strip():
            msg = f"{context}: Expected a class reference or null, got {value!r}"
            raise ValueBuildError(msg)

        annotation, path = parse_reference_text(context, value)
        annotation = self.resolve_reference_annotation(
            context, annotation, IMPLICIT_EXPORT_CLASS_PATH
        )

        visible = collect_visible_packages(self.config, self.context.packages)

        try:
            path = self.context.references.resolve_class_path(
                path, self.config.name, visible, include_intrinsics=True
            )
        except CompilationError as error:
            msg = f"{context}: {error}"
            raise ValueBuildError(msg) from error

        return ObjectValue(annotation, path)

    def _build_array_value(
        self, context: str, value: object, resolved_type: ResolvedType
    ) -> ArrayValue:
        match value:
            case ():
                return ArrayValue()

            case None if self.allow_dump_fixups:
                return ArrayValue()

            case list():
                element_type = resolved_type.arguments[0]
                elements = cast("list[object]", value)

                return ArrayValue(
                    [
                        self.build_value(f"{context}, element {index}", element, element_type)
                        for index, element in enumerate(elements)
                    ]
                )

            case _:
                msg = f"{context}: Expected an array, got {value!r}"
                raise ValueBuildError(msg)

    def _build_struct_value(
        self,
        context: str,
        value: object,
        resolved_type: ResolvedType,
        existing: Value | None = None,
    ) -> StructValue:
        match value:
            case ():
                value = {}
            case _:
                pass
        if not isinstance(value, dict):
            msg = f"{context}: Expected a struct mapping, got {value!r}"
            raise ValueBuildError(msg)

        path = resolved_type.declaration_path

        if path is None:
            msg = f"{context}: Struct type has no declaration path"
            raise ValueError(msg)

        if existing is not None and not isinstance(existing, StructValue):
            msg = f"{context}: Existing property value is not a struct"
            raise ValueError(msg)

        # Establish the baseline for partially supplied nested fields.
        base = self.struct_builder.make_struct(path, existing=existing)
        if not all(isinstance(name, str) for name in value):
            msg = f"{context}: Struct field names must be strings"
            raise ValueBuildError(msg)

        supplied = self.build_struct_values(
            context, path, cast("dict[str, object]", value), base.values
        )

        try:
            return self.struct_builder.make_struct(path, supplied, base)
        except ValueError as error:
            msg = f"{context}: {error}"
            raise ValueBuildError(msg) from error

    def build_value(
        self,
        context: str,
        value: object,
        resolved_type: ResolvedType,
        existing: Value | None = None,
    ) -> Value:
        """Convert Python data into a value of its declared type."""
        match resolved_type.category, value:
            case TypeCategory.INT, int() if not isinstance(value, bool):
                if -(INT32_MAX + 1) <= value <= INT32_MAX:
                    return IntValue(value)

            case TypeCategory.BYTE, int() if not isinstance(value, bool):
                if 0 <= value <= UINT8_MAX:
                    return ByteValue(value)

            case TypeCategory.FLOAT, (int() | float()) if not isinstance(value, bool):
                return FloatValue(float(value))

            case TypeCategory.BOOL, bool():
                return BoolValue(value)

            case TypeCategory.STRING, str():
                return StringValue(value)

            case TypeCategory.NAME, None:
                return NameValue()

            case TypeCategory.NAME, str():
                return NameValue(FName(value))

            case TypeCategory.ENUM, str():
                try:
                    return self.enums.construct_value(IdentifierValue(value), resolved_type)
                except ValueError as error:
                    msg = f"{context}: {error}"
                    raise ValueBuildError(msg) from error

            case TypeCategory.OBJECT, _:
                return self._build_object_value(context, value, resolved_type)

            case TypeCategory.CLASS, _:
                return self._build_class_value(context, value)

            case TypeCategory.ARRAY, _:
                return self._build_array_value(context, value, resolved_type)

            case TypeCategory.STRUCT, _:
                return self._build_struct_value(context, value, resolved_type, existing)

            case (
                TypeCategory.INT
                | TypeCategory.BYTE
                | TypeCategory.FLOAT
                | TypeCategory.BOOL
                | TypeCategory.STRING
                | TypeCategory.NAME
                | TypeCategory.ENUM,
                _,
            ):
                pass

            case _:
                msg = (
                    f"{context}: Building values of type "
                    f"{resolved_type.category.value} is not implemented"
                )
                raise NotImplementedError(msg)

        msg = f"{context}: Invalid {resolved_type.category.value} value: {value!r}"
        raise ValueBuildError(msg)

    def build_field_value(
        self,
        context: str,
        definition: VariableDeclaration,
        value: object,
        resolved_type: ResolvedType,
        existing: Value | None = None,
    ) -> Value:
        if isinstance(value, IndexedArrayDefaults):
            return self._build_indexed_array_value(
                context, definition, value, resolved_type, existing
            )

        if definition.array_dimension == 1:
            return self.build_value(context, value, resolved_type, existing)

        if self.implicit_fixed_index and not isinstance(value, list):
            indexed = IndexedArrayDefaults(updates=[(0, value)])
            return self._build_indexed_array_value(
                context, definition, indexed, resolved_type, existing
            )

        if not isinstance(value, list):
            msg = f"{context}: Expected a fixed-size array"
            raise ValueBuildError(msg)

        if len(value) != definition.array_dimension:
            msg = f"{context}: Expected {definition.array_dimension} elements, got {len(value)}"
            raise ValueBuildError(msg)

        return ArrayValue(
            [
                self.build_value(f"{context}, element {index}", element, resolved_type)
                for index, element in enumerate(value)
            ]
        )

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

    def build_class_values(
        self,
        context: str,
        class_path: str,
        properties: dict[str, object],
        defaults: dict[FName, Value] | None = None,
    ) -> dict[FName, Value]:
        """Convert supplied class properties into typed values."""
        result: dict[FName, Value] = {}

        for supplied_name, raw_value in properties.items():
            field_context = f"{context}, property {supplied_name!r}"

            try:
                member = self.context.references.resolve_variable(
                    class_path, supplied_name, self.context.parents
                )
                definition = member.declaration
                resolved = self.resolve_field_type(definition, member.owner_class)
            except CompilationError as error:
                msg = f"{field_context}: {error}"
                raise ValueBuildError(msg) from error

            name = FName(definition.name)

            if name in result:
                msg = f"{field_context}: Duplicate property"
                raise ValueBuildError(msg)

            existing = None if defaults is None else defaults.get(name)

            result[name] = self.build_field_value(
                field_context, definition, raw_value, resolved, existing
            )

        return result

    def build_struct_values(
        self,
        context: str,
        struct_path: str,
        properties: dict[str, object],
        defaults: dict[FName, Value] | None = None,
    ) -> dict[FName, Value]:
        """Convert supplied struct fields into typed values."""
        owner_class = struct_path.rpartition(".")[0]
        package_name = owner_class.partition(".")[0]
        config = next(
            config
            for config in self.context.packages
            if config.name.casefold() == package_name.casefold()
        )
        visible = collect_visible_packages(config, self.context.packages)
        result: dict[FName, Value] = {}

        for supplied_name, raw_value in properties.items():
            field_context = f"{context}, field {supplied_name!r}"

            try:
                member = self.context.references.resolve_struct_variable(
                    struct_path, supplied_name, self.context.parents, visible
                )
                definition = member.declaration
                resolved = self.resolve_field_type(definition, member.owner_class)
            except CompilationError as error:
                msg = f"{field_context}: {error}"
                raise ValueBuildError(msg) from error

            name = FName(definition.name)

            if name in result:
                msg = f"{field_context}: Duplicate struct field"
                raise ValueBuildError(msg)

            existing = None if defaults is None else defaults.get(name)

            result[name] = self.build_field_value(
                field_context, definition, raw_value, resolved, existing
            )

        return result

    def resolve_reference_annotation(
        self, context: str, annotation: str | None, expected_class: str
    ) -> str:
        if annotation is None:
            return expected_class

        visible = collect_visible_packages(self.config, self.context.packages)

        try:
            path = self.context.references.resolve_class_path(
                annotation, self.config.name, visible, include_intrinsics=True
            )
        except CompilationError as error:
            msg = f"{context}: {error}"
            raise ValueBuildError(msg) from error

        if not self.context.references.is_subclass(path, expected_class, self.context.parents):
            msg = f"{context}: Reference annotation {path} does not extend {expected_class}"
            raise ValueBuildError(msg)

        return path

    def _build_indexed_array_value(
        self,
        context: str,
        definition: VariableDeclaration,
        value: IndexedArrayDefaults,
        resolved_type: ResolvedType,
        existing: Value | None,
    ) -> ArrayValue:
        fixed = definition.array_dimension > 1

        if not fixed and resolved_type.category is not TypeCategory.ARRAY:
            msg = f"{context}: Indexed defaults require an array property"
            raise ValueBuildError(msg)

        element_type = resolved_type if fixed else resolved_type.arguments[0]

        if value.has_initial:
            initial = self.build_field_value(
                context, definition, value.initial, resolved_type, existing
            )
            if not isinstance(initial, ArrayValue):
                msg = f"{context}: Array initializer did not produce an array"
                raise ValueError(msg)
            result = initial
        elif existing is not None:
            if not isinstance(existing, ArrayValue):
                msg = f"{context}: Existing array value is not an ArrayValue"
                raise ValueError(msg)
            result = deepcopy(existing)
        elif fixed:
            result = ArrayValue(
                [
                    self.struct_builder.initial_value(element_type)
                    for _ in range(definition.array_dimension)
                ]
            )
        else:
            result = ArrayValue()

        if fixed and len(result.elements) != definition.array_dimension:
            msg = f"{context}: Existing fixed-array length does not match its declaration"
            raise ValueError(msg)

        for index, raw_value in value.updates:
            element_context = f"{context}, element {index}"
            if index < 0 or (fixed and index >= definition.array_dimension):
                msg = f"{element_context}: Array index out of bounds"
                raise ValueBuildError(msg)

            while len(result.elements) <= index:
                result.elements.append(self.struct_builder.initial_value(element_type))

            result.elements[index] = self.build_value(
                element_context, raw_value, element_type, result.elements[index]
            )

        return result
