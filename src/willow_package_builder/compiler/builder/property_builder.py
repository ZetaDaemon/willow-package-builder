from dataclasses import dataclass
from typing import TYPE_CHECKING

from willow_package_builder.compiler.semantics.types import TypeCategory
from willow_package_builder.compiler.syntax.declarations import TypeReference, VariableDeclaration
from willow_package_builder.compiler.syntax.lexer import TokenCategory
from willow_package_builder.logging import CompilationError
from willow_package_builder.package_config import collect_visible_packages
from willow_package_builder.payloads.property_payloads import (
    PropertyFlags,
    UArrayPropertyPayload,
    UBoolPropertyPayload,
    UBytePropertyPayload,
    UClassPropertyPayload,
    UFloatPropertyPayload,
    UIntPropertyPayload,
    UNamePropertyPayload,
    UObjectPropertyPayload,
    UPropertyPayload,
    UStrPropertyPayload,
    UStructPropertyPayload,
)
from willow_package_builder.upackage import FName, ObjectFlags, ReferencePath, UObject

from .build_component import BuildComponent

if TYPE_CHECKING:
    from .references import PackageReferences


@dataclass
class PropertyBuilder(BuildComponent):
    references: PackageReferences

    def struct_needs_ctor_link(self, struct_path: str) -> bool:
        owner_path, _, name = struct_path.rpartition(".")

        member = self.context.references.resolve_struct(owner_path, name, self.context.parents)

        owner_package = member.owner_class.partition(".")[0]
        config = next(
            config
            for config in self.context.packages
            if config.name.casefold() == owner_package.casefold()
        )
        visible = collect_visible_packages(config, self.context.packages)

        type_refs = [variable.type_ref for variable in member.declaration.variables]

        if member.declaration.parent is not None:
            type_refs.insert(0, TypeReference(member.declaration.parent))

        for type_ref in type_refs:
            resolved = self.context.references.resolve_type(
                type_ref, member.owner_class, visible, self.context.parents
            )

            if resolved.category in (TypeCategory.STRING, TypeCategory.ARRAY):
                return True

            if resolved.category is TypeCategory.STRUCT:
                if resolved.declaration_path is None:
                    msg = "Resolved struct type has no declaration path"
                    raise ValueError(msg)

                if self.struct_needs_ctor_link(resolved.declaration_path):
                    return True

        return False

    def create_property(
        self,
        owner: UObject,
        name: str,
        type_ref: TypeReference,
        class_path: str,
        flags: PropertyFlags,
        array_dimension: int = 1,
    ) -> UObject:
        resolved = self.context.references.resolve_type(
            type_ref,
            class_path,
            collect_visible_packages(self.config, self.context.packages),
            self.context.parents,
        )

        payload: UPropertyPayload

        match resolved.category:
            case TypeCategory.INT:
                payload = UIntPropertyPayload()

            case TypeCategory.OBJECT:
                if resolved.declaration_path is None:
                    msg = "Resolved object type has no declaration path"
                    raise ValueError(msg)

                payload = UObjectPropertyPayload(
                    property_class=self.references.class_object_reference(resolved.declaration_path)
                )

            case TypeCategory.BYTE:
                payload = UBytePropertyPayload()

            case TypeCategory.FLOAT:
                payload = UFloatPropertyPayload()

            case TypeCategory.BOOL:
                payload = UBoolPropertyPayload()

            case TypeCategory.NAME:
                payload = UNamePropertyPayload()

            case TypeCategory.STRING:
                payload = UStrPropertyPayload()
                flags |= PropertyFlags.NEED_CTOR_LINK

            case TypeCategory.CLASS:
                bound = resolved.arguments[0]

                if bound.declaration_path is None:
                    msg = "Resolved class bound has no declaration path"
                    raise ValueError(msg)

                payload = UClassPropertyPayload(
                    property_class=self.references.class_object_reference("Core.Class"),
                    meta_class=self.references.class_object_reference(bound.declaration_path),
                )

            case TypeCategory.ARRAY:
                payload = UArrayPropertyPayload(inner=ReferencePath())
                flags |= PropertyFlags.NEED_CTOR_LINK

            case TypeCategory.ENUM:
                if resolved.declaration_path is None:
                    msg = "Resolved enum type has no declaration path"
                    raise ValueError(msg)

                payload = UBytePropertyPayload(
                    enum=self.references.enum_reference(resolved.declaration_path)
                )

            case TypeCategory.STRUCT:
                if resolved.declaration_path is None:
                    msg = "Resolved struct type has no declaration path"
                    raise ValueError(msg)

                payload = UStructPropertyPayload(
                    struct=self.references.struct_reference(resolved.declaration_path)
                )

                if self.struct_needs_ctor_link(resolved.declaration_path):
                    flags |= PropertyFlags.NEED_CTOR_LINK

            case _:
                msg = f"Property {owner.reference()}.{name} requires unsupported type {resolved!r}"
                raise NotImplementedError(msg)

        payload.array_dimension = array_dimension
        payload.property_flags = flags

        definition = self.context.references.property_class(resolved)
        property_class = self.references.class_object_reference(definition.path)

        obj = UObject(
            FName(name),
            ObjectFlags.DEFAULT_EXPORT,
            owner.reference(),
            property_class,
            payload=payload,
        )

        self.package.add_export(obj)
        if isinstance(payload, UArrayPropertyPayload):
            inner = self.create_property(
                obj, name, type_ref.arguments[0], class_path, PropertyFlags.NONE
            )
            payload.inner = inner.reference()
        return obj

    def create_field(
        self,
        owner: UObject,
        declaration: VariableDeclaration,
        class_path: str,
        next_field: ReferencePath,
    ) -> UObject:
        path = owner.reference() + FName(declaration.name)
        flags = PropertyFlags.NONE

        for modifier in declaration.modifiers:
            if modifier == "const":
                flags |= PropertyFlags.CONST
            else:
                msg = f"Unsupported field modifier {modifier!r} on {path}"
                raise CompilationError(msg)

        category = FName("None")
        tokens = declaration.category_tokens

        if tokens is not None:
            flags |= PropertyFlags.EDIT

            if tokens:
                if len(tokens) != 1 or tokens[0].category is not TokenCategory.IDENTIFIER:
                    msg = f"Unsupported category syntax on {path}"
                    raise CompilationError(msg)

                category = FName(tokens[0].text)

        obj = self.create_property(
            owner,
            declaration.name,
            declaration.type_ref,
            class_path,
            flags,
            declaration.array_dimension,
        )

        if not isinstance(obj.payload, UPropertyPayload):
            msg = f"Field has an invalid payload: {path}"
            raise TypeError(msg)

        obj.payload.category = category
        obj.payload.next_field = next_field
        return obj
