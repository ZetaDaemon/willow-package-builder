from copy import deepcopy
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, cast

from willow_package_builder.builder.struct_layout import requires_binary_struct
from willow_package_builder.compiler.semantics.types import ResolvedType, TypeCategory
from willow_package_builder.compiler.syntax.parser.defaults_parser import IndexedArrayDefaults
from willow_package_builder.logging import (
    CompilationError,
    ValueBuildError,
    WarningCode,
    declaration_context,
    warn,
)
from willow_package_builder.package_config import collect_visible_packages
from willow_package_builder.properties.reference_text import parse_reference_text
from willow_package_builder.properties.values import (
    ArrayValue,
    BoolValue,
    ByteValue,
    DelegateValue,
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
from willow_package_builder.upackage import (
    CORE_CLASS_PATH,
    INT32_MAX,
    UINT8_MAX,
    FName,
    ReferencePath,
)

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
    reference_base: ReferencePath | None = field(default=None, kw_only=True)
    external_archetype: ReferencePath | None = field(default=None, kw_only=True)
    known_archetype_properties: frozenset[FName] = field(default_factory=frozenset)

    def _build_object_value(
        self, context: str, value: object, resolved_type: ResolvedType
    ) -> ObjectValue | NullValue:
        if value is None:
            return NullValue()

        if isinstance(value, ReferencePath):
            if value.is_none():
                return NullValue()

            annotation = None
            path = value
        elif isinstance(value, str) and value.strip():
            annotation, path = parse_reference_text(context, value, self.reference_base)
        else:
            msg = f"{context}: Expected an object reference or null, got {value!r}"
            raise ValueBuildError(msg)

        class_path = resolved_type.declaration_path

        if class_path is None:
            msg = f"{context}: Object property has no declared class"
            raise ValueError(msg)

        annotation = self.resolve_reference_annotation(context, annotation, class_path)
        return ObjectValue(annotation, path)

    def _build_class_value(self, context: str, value: object) -> ObjectValue | NullValue:
        if value is None:
            return NullValue()

        if isinstance(value, ReferencePath):
            if value.is_none():
                return NullValue()

            annotation = None
            path = value
        elif isinstance(value, str) and value.strip():
            annotation, path = parse_reference_text(context, value, None)
        else:
            msg = f"{context}: Expected a class reference or null, got {value!r}"
            raise ValueBuildError(msg)

        annotation = self.resolve_reference_annotation(context, annotation, CORE_CLASS_PATH)
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
                values = replace(self, external_archetype=None)

                return ArrayValue(
                    [
                        values.build_value(f"{context}, element {index}", element, element_type)
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

        fields: dict[FName, object] = {}

        for raw_name, raw_value in value.items():
            if isinstance(raw_name, FName):
                name = raw_name
            elif isinstance(raw_name, str):
                name = FName(raw_name)
            else:
                msg = f"{context}: Struct field names must be names or strings"
                raise ValueBuildError(msg)

            if name in fields:
                msg = f"{context}: Duplicate struct field {name}"
                raise ValueBuildError(msg)

            fields[name] = raw_value

        supplied = self.build_struct_values(context, path, fields, base.values)

        if isinstance(existing, StructValue):
            self._warn_external_binary_defaults(context, path, supplied)

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

            case TypeCategory.NAME, FName():
                return NameValue(value)

            case TypeCategory.NAME, str():
                return NameValue(FName(value))

            case TypeCategory.ENUM, (str() | FName()):
                try:
                    return self.enums.construct_value(
                        IdentifierValue(ReferencePath(value)), resolved_type
                    )
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

            case TypeCategory.DELEGATE, None:
                return DelegateValue()

            case TypeCategory.DELEGATE, _:
                msg = f"{context}: Non-empty delegate values are not implemented"
                raise NotImplementedError(msg)

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

        previous: list[Value] | None = None

        if existing is not None:
            if not isinstance(existing, ArrayValue):
                msg = f"{context}: Existing fixed-array value is not an ArrayValue"
                raise ValueError(msg)

            if len(existing.elements) != definition.array_dimension:
                msg = f"{context}: Existing fixed-array length does not match its declaration"
                raise ValueError(msg)

            previous = existing.elements

        return ArrayValue(
            [
                self.build_value(
                    f"{context}, element {index}",
                    element,
                    resolved_type,
                    None if previous is None else previous[index],
                )
                for index, element in enumerate(value)
            ]
        )

    def resolve_field_type(
        self, definition: VariableDeclaration, owner_class: ReferencePath
    ) -> ResolvedType:
        if owner_class.outer is None:
            msg = f"Expected fully qualified class, got {owner_class}"
            raise ValueError(msg)
        package_name = owner_class.outer.name
        config = next(config for config in self.context.packages if config.name == package_name)
        visible = collect_visible_packages(config, self.context.packages)
        path = owner_class + definition.name

        with declaration_context(path, definition.location):
            return self.context.references.resolve_type(
                definition.type_ref, owner_class, visible, self.context.parents
            )

    def build_class_values(
        self,
        context: str,
        class_path: ReferencePath,
        properties: dict[FName, object],
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

            name = definition.name

            if name in result:
                msg = f"{field_context}: Duplicate property"
                raise ValueBuildError(msg)

            existing = None if defaults is None else defaults.get(name)

            values = self

            if name in self.known_archetype_properties:
                values = replace(self, external_archetype=None)

            result[name] = values.build_field_value(
                field_context, definition, raw_value, resolved, existing
            )

        return result

    def build_struct_values(
        self,
        context: str,
        struct_path: ReferencePath,
        properties: dict[FName, object],
        defaults: dict[FName, Value] | None = None,
    ) -> dict[FName, Value]:
        """Convert supplied struct fields into typed values."""
        if struct_path.outer is None or struct_path.outer.outer is None:
            msg = f"Expected fully qualified struct, got {struct_path}"
            raise ValueError(msg)

        package_name = struct_path.base
        config = next(config for config in self.context.packages if config.name == package_name)
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

            name = definition.name

            if name in result:
                msg = f"{field_context}: Duplicate struct field"
                raise ValueBuildError(msg)

            existing = None if defaults is None else defaults.get(name)

            result[name] = self.build_field_value(
                field_context, definition, raw_value, resolved, existing
            )

        return result

    def resolve_reference_annotation(
        self, context: str, annotation: ReferencePath | None, expected_class: ReferencePath
    ) -> ReferencePath:
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

    def _warn_external_binary_defaults(
        self, context: str, struct_path: ReferencePath, supplied: dict[FName, Value]
    ) -> None:
        """Warn about unavailable defaults needed by serialized binary structs."""
        if self.external_archetype is None:
            return

        hierarchy = self.struct_builder.struct_hierarchy(struct_path)
        binary = any(
            requires_binary_struct(declaration, self.package.flags) for _, declaration in hierarchy
        )
        fields = {
            variable.name: (owner, variable)
            for owner, declaration in hierarchy
            for variable in declaration.variables
        }
        missing = fields.keys() - supplied.keys()

        if binary:
            if missing:
                omitted = ", ".join(sorted(str(name) for name in missing))
                msg = (
                    f"{context}: Values from external archetype "
                    f"{self.external_archetype} are unavailable; omitted binary struct "
                    f"fields use the available class/struct defaults: {omitted}"
                )
                warn(WarningCode.EXTERNAL_ARCHETYPE_DEFAULTS, msg)

            return

        # Supplied nested structs are checked during their own construction.
        # Check omitted nested structs that will be serialized from the baseline.
        for name, (owner, definition) in fields.items():
            if name not in missing:
                continue

            resolved = self.resolve_field_type(definition, owner)

            if resolved.category is not TypeCategory.STRUCT:
                continue

            nested_path = resolved.declaration_path

            if nested_path is None:
                msg = f"Struct field {name} has no declaration path"
                raise ValueError(msg)

            self._warn_external_binary_defaults(f"{context}, field {str(name)!r}", nested_path, {})
