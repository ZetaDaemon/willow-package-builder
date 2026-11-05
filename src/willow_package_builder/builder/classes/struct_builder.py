from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from willow_package_builder.builder.build_component import BuildComponent
from willow_package_builder.compiler.semantics.types import ResolvedType, TypeCategory
from willow_package_builder.compiler.syntax.declarations import StructDeclaration, TypeReference
from willow_package_builder.compiler.syntax.modifiers import StructModifier
from willow_package_builder.logging import CompilationError
from willow_package_builder.package_config import collect_visible_packages
from willow_package_builder.payloads.class_payload import UClassPayload
from willow_package_builder.payloads.struct_payload import StructFlags, UScriptStructPayload
from willow_package_builder.properties.construction import initial_scalar_value
from willow_package_builder.properties.merge import merge_values
from willow_package_builder.properties.values import ArrayValue, StructValue, Value
from willow_package_builder.upackage import FName, ObjectFlags, UObject

from .exports import StructExport

if TYPE_CHECKING:
    from willow_package_builder.builder.classes.enum_builder import EnumBuilder
    from willow_package_builder.builder.references import PackageReferences

    from .property_builder import PropertyBuilder

STRUCT_MODIFIER_FLAGS: dict[StructModifier, StructFlags] = {
    StructModifier.NATIVE: StructFlags.NATIVE,
    StructModifier.EXPORT: StructFlags.EXPORT,
    StructModifier.NO_EXPORT: StructFlags.NONE,
    StructModifier.TRANSIENT: StructFlags.TRANSIENT,
    StructModifier.ATOMIC: StructFlags.ATOMIC,
    StructModifier.IMMUTABLE: StructFlags.IMMUTABLE,
    StructModifier.STRICT_CONFIG: StructFlags.STRICT_CONFIG,
    StructModifier.IMMUTABLE_WHEN_COOKED: StructFlags.IMMUTABLE_WHEN_COOKED,
    StructModifier.ATOMIC_WHEN_COOKED: StructFlags.ATOMIC_WHEN_COOKED,
}


@dataclass
class StructBuilder(BuildComponent):
    references: PackageReferences
    properties: PropertyBuilder
    enums: EnumBuilder

    _constructing_structs: set[str] = field(default_factory=set, init=False, repr=False)

    def reserve_structs(self) -> None:
        struct_class = self.references.class_object_reference("Core.ScriptStruct")

        supported_modifiers = {
            StructModifier.EXPORT,
            StructModifier.TRANSIENT,
            StructModifier.ATOMIC,
            StructModifier.IMMUTABLE,
            StructModifier.STRICT_CONFIG,
            StructModifier.IMMUTABLE_WHEN_COOKED,
            StructModifier.ATOMIC_WHEN_COOKED,
            StructModifier.NO_EXPORT,
        }

        for class_path, exports in self.classes.items():
            for declaration in exports.declaration.structs:
                path = f"{class_path}.{declaration.name}".casefold()

                if path in self.structs:
                    msg = f"Duplicate struct: {path}"
                    raise CompilationError(msg)

                flags = StructFlags.NONE

                if StructModifier.NATIVE in declaration.modifiers:
                    msg = f"Cannot compile native struct {path}"
                    raise CompilationError(msg)

                for modifier in declaration.modifiers:
                    if modifier not in supported_modifiers:
                        msg = f"Unsupported struct modifier {modifier!r} on {path}"
                        raise NotImplementedError(msg)

                    flags |= STRUCT_MODIFIER_FLAGS[modifier]

                obj = UObject(
                    FName(declaration.name),
                    ObjectFlags.PUBLIC_EXPORT,
                    exports.class_object.reference(),
                    struct_class,
                    payload=UScriptStructPayload(
                        struct_path=path,
                        context=self.context,
                        struct_flags=flags,
                        defaults=self.make_struct(path).values,
                    ),
                )

                self.package.add_export(obj)
                self.structs[path] = StructExport(class_path, declaration, obj)

    def link_structs(self) -> None:
        visible = collect_visible_packages(self.config, self.context.packages)
        parents: dict[str, str | None] = {}

        for path, exports in self.structs.items():
            parent_name = exports.declaration.parent

            if parent_name is None:
                parents[path] = None
                continue

            parent = self.context.references.resolve_type(
                TypeReference(parent_name), exports.owner_class, visible, self.context.parents
            )

            if parent.category is not TypeCategory.STRUCT:
                msg = f"Struct {path} cannot extend non-struct {parent_name!r}"
                raise CompilationError(msg)

            if parent.declaration_path is None:
                msg = f"Resolved parent struct has no declaration path: {path}"
                raise ValueError(msg)

            parents[path] = parent.declaration_path.casefold()

        # Reject inheritance cycles among structs built in this package.
        completed: set[str] = set()
        active: list[str] = []

        def visit(path: str) -> None:
            if path in completed:
                return

            if path in active:
                start = active.index(path)
                cycle = " -> ".join((*active[start:], path))
                msg = f"Struct inheritance cycle: {cycle}"
                raise CompilationError(msg)

            active.append(path)
            parent = parents[path]

            if parent in parents:
                visit(parent)

            active.pop()
            completed.add(path)

        for path in parents:
            visit(path)

        # Prepending in reverse preserves declaration order.
        for path, exports in reversed(list(self.structs.items())):
            payload = exports.struct_object.payload
            class_payload = self.classes[exports.owner_class].class_object.payload

            if not isinstance(payload, UScriptStructPayload):
                msg = f"Struct has an invalid payload: {path}"
                raise TypeError(msg)

            if not isinstance(class_payload, UClassPayload):
                msg = f"Class must be linked before linking structs: {exports.owner_class}"
                raise ValueError(msg)  # noqa: TRY004

            parent_path = parents[path]

            if parent_path is not None:
                parent_reference = self.references.struct_reference(parent_path)
                exports.struct_object.super_object = parent_reference
                payload.super_struct = parent_reference

            payload.next_field = class_payload.children
            class_payload.children = exports.struct_object.reference()

    def build_struct_fields(self) -> None:
        for path, exports in self.structs.items():
            payload = exports.struct_object.payload

            if not isinstance(payload, UScriptStructPayload):
                msg = f"Struct has an invalid payload: {path}"
                raise ValueError(msg)  # noqa: TRY004

            for variable in reversed(exports.declaration.variables):
                obj = self.properties.create_field(
                    exports.struct_object, variable, exports.owner_class, payload.children
                )
                payload.children = obj.reference()

    def validate_struct_layouts(self) -> None:
        completed: set[str] = set()
        active: list[str] = []

        def visit(path: str) -> None:
            if path in completed:
                return

            if path in active:
                start = active.index(path)
                cycle = " -> ".join((*active[start:], path))
                msg = f"Recursive struct layout: {cycle}"
                raise CompilationError(msg)

            owner_path, _, name = path.rpartition(".")
            member = self.context.references.resolve_struct(owner_path, name, self.context.parents)

            owner_package = member.owner_class.partition(".")[0]
            config = next(
                config
                for config in self.context.packages
                if config.name.casefold() == owner_package.casefold()
            )
            visible = collect_visible_packages(config, self.context.packages)

            active.append(path)

            type_refs = [variable.type_ref for variable in member.declaration.variables]

            if member.declaration.parent is not None:
                type_refs.insert(0, TypeReference(member.declaration.parent))

            for type_ref in type_refs:
                resolved = self.context.references.resolve_type(
                    type_ref, member.owner_class, visible, self.context.parents
                )

                if resolved.category is TypeCategory.STRUCT:
                    if resolved.declaration_path is None:
                        msg = "Resolved struct type has no declaration path"
                        raise ValueError(msg)

                    visit(resolved.declaration_path.casefold())

            active.pop()
            completed.add(path)

        for path in self.structs:
            visit(path)

    def initial_value(self, resolved_type: ResolvedType) -> Value:
        match resolved_type.category:
            case TypeCategory.STRUCT:
                path = resolved_type.declaration_path

                if path is None:
                    msg = "Struct type has no declaration path"
                    raise ValueError(msg)

                return self.make_struct(path)

            case TypeCategory.ENUM:
                return self.enums.initial_value(resolved_type)

            case _:
                return initial_scalar_value(resolved_type)

    def make_struct(
        self,
        struct_path: str,
        values: dict[FName, Value] | None = None,
        existing: StructValue | None = None,
    ) -> StructValue:
        """Construct a struct from its defaults and typed overrides."""
        key = struct_path.casefold()

        if key in self._constructing_structs:
            msg = f"Recursive struct construction at {struct_path}"
            raise CompilationError(msg)

        self._constructing_structs.add(key)

        try:
            result: dict[FName, Value] = {}

            for owner, declaration in self.struct_hierarchy(struct_path):
                package_name = owner.partition(".")[0]
                config = next(
                    config
                    for config in self.context.packages
                    if config.name.casefold() == package_name.casefold()
                )
                visible = collect_visible_packages(config, self.context.packages)

                for variable in declaration.variables:
                    name = FName(variable.name)

                    if name in result:
                        continue

                    resolved = self.context.references.resolve_type(
                        variable.type_ref, owner, visible, self.context.parents
                    )

                    if variable.array_dimension == 1:
                        result[name] = self.initial_value(resolved)
                    else:
                        result[name] = ArrayValue(
                            [self.initial_value(resolved) for _ in range(variable.array_dimension)]
                        )

                result = merge_values(result, declaration.defaults)

            if existing is not None:
                result = merge_values(result, existing.values)

            if values is not None:
                result = merge_values(result, values)

            return StructValue(result, struct_path=struct_path)
        finally:
            self._constructing_structs.remove(key)

    def struct_hierarchy(self, struct_path: str) -> list[tuple[str, StructDeclaration]]:
        return self.context.references.struct_hierarchy(
            struct_path, self.context.parents, self.context.packages
        )
