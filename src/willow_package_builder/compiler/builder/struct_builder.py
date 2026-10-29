from dataclasses import dataclass
from typing import TYPE_CHECKING

from willow_package_builder.compiler.semantics.types import TypeType
from willow_package_builder.compiler.syntax.declarations import TypeReference
from willow_package_builder.logging import CompilationError
from willow_package_builder.package_config import collect_visible_packages
from willow_package_builder.payloads.class_payload import UClassPayload
from willow_package_builder.payloads.struct_payload import StructFlags, UScriptStructPayload
from willow_package_builder.upackage import FName, ObjectFlags, UObject

from .build_component import BuildComponent
from .exports import StructExports

if TYPE_CHECKING:
    from .property_builder import PropertyBuilder
    from .references import PackageReferences


@dataclass
class StructBuilder(BuildComponent):
    references: PackageReferences
    properties: PropertyBuilder

    def reserve_structs(self) -> None:
        struct_class = self.references.class_object_reference("Core.ScriptStruct")

        supported_flags = {
            "export": StructFlags.EXPORT,
            "transient": StructFlags.TRANSIENT,
            "atomic": StructFlags.ATOMIC,
            "immutable": StructFlags.IMMUTABLE,
            "strictconfig": StructFlags.STRICT_CONFIG,
            "immutablewhencooked": StructFlags.IMMUTABLE_WHEN_COOKED,
            "atomicwhencooked": StructFlags.ATOMIC_WHEN_COOKED,
        }

        for class_path, exports in self.classes.items():
            for declaration in exports.declaration.structs:
                path = f"{class_path}.{declaration.name}".casefold()

                if path in self.structs:
                    msg = f"Duplicate struct: {path}"
                    raise CompilationError(msg)

                flags = StructFlags.NONE

                for modifier in declaration.modifiers:
                    if modifier == "noexport":
                        continue

                    flag = supported_flags.get(modifier)

                    if flag is None:
                        msg = f"Unsupported struct modifier {modifier!r} on {path}"
                        raise CompilationError(msg)

                    flags |= flag

                if declaration.default_tokens:
                    msg = f"Struct defaults are not supported yet: {path}"
                    raise CompilationError(msg)

                obj = UObject(
                    FName(declaration.name),
                    ObjectFlags.DEFAULT_EXPORT,
                    exports.class_object.reference(),
                    struct_class,
                    payload=UScriptStructPayload(struct_flags=flags),
                )

                self.package.add_export(obj)
                self.structs[path] = StructExports(class_path, declaration, obj)

    def link_structs(self) -> None:
        visible = collect_visible_packages(self.config, self.context.packages)
        parents: dict[str, str | None] = {}

        for path, exports in self.structs.items():
            parent_name = exports.declaration.parent

            if parent_name is None:
                parents[path] = None
                continue

            parent = self.context.references.resolve_type(
                TypeReference(parent_name),
                current_class=exports.owner_class,
                visible_packages=visible,
                parents=self.context.parents,
            )

            if parent.type is not TypeType.STRUCT:
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
                    type_ref,
                    current_class=member.owner_class,
                    visible_packages=visible,
                    parents=self.context.parents,
                )

                if resolved.type is TypeType.STRUCT:
                    if resolved.declaration_path is None:
                        msg = "Resolved struct type has no declaration path"
                        raise ValueError(msg)

                    visit(resolved.declaration_path.casefold())

            active.pop()
            completed.add(path)

        for path in self.structs:
            visit(path)
