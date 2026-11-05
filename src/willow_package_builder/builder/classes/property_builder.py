from dataclasses import dataclass
from typing import TYPE_CHECKING

from willow_package_builder.builder.build_component import BuildComponent
from willow_package_builder.compiler.semantics.types import TypeCategory
from willow_package_builder.compiler.syntax.declarations import TypeReference, VariableDeclaration
from willow_package_builder.compiler.syntax.lexer import TokenCategory
from willow_package_builder.compiler.syntax.modifiers import VariableModifier
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

if TYPE_CHECKING:
    from willow_package_builder.builder.references import PackageReferences

VARIABLE_MODIFIER_FLAGS: dict[VariableModifier, PropertyFlags] = {
    VariableModifier.CONST: PropertyFlags.CONST,
    VariableModifier.EDIT_CONST: PropertyFlags.EDIT_CONST,
    VariableModifier.INIT: PropertyFlags.ALWAYS_INIT,
    VariableModifier.NO_EXPORT: PropertyFlags.NO_EXPORT,
    VariableModifier.DUPLICATE_TRANSIENT: PropertyFlags.DUPLICATE_TRANSIENT,
    VariableModifier.PRIVATE_WRITE: PropertyFlags.PRIVATE_WRITE,
    VariableModifier.PROTECTED_WRITE: PropertyFlags.PROTECTED_WRITE,
    VariableModifier.PUBLIC: PropertyFlags.NONE,
    VariableModifier.PRIVATE: PropertyFlags.NONE,
    VariableModifier.PROTECTED: PropertyFlags.NONE,
    VariableModifier.INTERP: PropertyFlags.INTERP | PropertyFlags.EDIT,
    VariableModifier.EDIT_INLINE: PropertyFlags.EDIT_INLINE,
    VariableModifier.EXPORT: PropertyFlags.EXPORT_OBJECT,
}

SUPPORTED_VARIABLE_MODIFIERS = frozenset(
    {key for key in VARIABLE_MODIFIER_FLAGS if key != VariableModifier.EXPORT}
)

ARRAY_INNER_FLAGS = (
    PropertyFlags.EXPORT_OBJECT
    | PropertyFlags.ALWAYS_INIT
    | PropertyFlags.EDIT_CONST
    | PropertyFlags.EDIT_INLINE
)


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
        path = owner.reference() + FName(name)
        flags |= self.variable_modifier_flags(type_ref.modifiers, path)
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

        instancing_flags = PropertyFlags.EDIT_INLINE | PropertyFlags.EXPORT_OBJECT

        if (
            isinstance(payload, UObjectPropertyPayload)
            and flags & instancing_flags == instancing_flags
        ):
            flags |= PropertyFlags.NEED_CTOR_LINK

        payload.array_dimension = array_dimension
        payload.property_flags = flags

        definition = self.context.references.property_class(resolved)
        property_class = self.references.class_object_reference(definition.path)

        obj = UObject(
            FName(name),
            ObjectFlags.PUBLIC_EXPORT,
            owner.reference(),
            property_class,
            payload=payload,
        )

        self.package.add_export(obj)
        if isinstance(payload, UArrayPropertyPayload):
            inner = self.create_property(
                obj, name, type_ref.arguments[0], class_path, flags & ARRAY_INNER_FLAGS
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
        flags = self.variable_modifier_flags(declaration.modifiers, path)

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
        if VariableModifier.PRIVATE in declaration.modifiers:
            obj.flags &= ~ObjectFlags.PUBLIC

        if VariableModifier.PROTECTED in declaration.modifiers:
            obj.flags |= ObjectFlags.PUBLIC | ObjectFlags.PROTECTED

        if not isinstance(obj.payload, UPropertyPayload):
            msg = f"Field has an invalid payload: {path}"
            raise TypeError(msg)

        obj.payload.category = category
        obj.payload.next_field = next_field
        obj.payload.array_enum = self.array_enum_reference(declaration, class_path)
        return obj

    def variable_modifier_flags(
        self, modifiers: tuple[VariableModifier, ...], path: ReferencePath
    ) -> PropertyFlags:
        incompatible_pairs = (
            (VariableModifier.PRIVATE, VariableModifier.PROTECTED),
            (VariableModifier.PRIVATE, VariableModifier.PRIVATE_WRITE),
            (VariableModifier.PROTECTED, VariableModifier.PRIVATE_WRITE),
            (VariableModifier.PROTECTED, VariableModifier.PROTECTED_WRITE),
            (VariableModifier.PRIVATE_WRITE, VariableModifier.PROTECTED_WRITE),
        )

        flags = PropertyFlags.NONE

        if VariableModifier.PRIVATE in modifiers and VariableModifier.PROTECTED in modifiers:
            msg = f"Property {path} cannot be both private and protected"
            raise CompilationError(msg)

        for first, second in incompatible_pairs:
            if first in modifiers and second in modifiers:
                msg = f"Property {path} cannot combine {first.value!r} and {second.value!r}"
                raise CompilationError(msg)

        for modifier in modifiers:
            if modifier not in SUPPORTED_VARIABLE_MODIFIERS:
                msg = f"Variable modifier {modifier.value!r} is not implemented"
                raise NotImplementedError(msg)

            if modifier is VariableModifier.NATIVE:
                msg = f"Cannot compile native property {path}"
                raise CompilationError(msg)

            flags |= VARIABLE_MODIFIER_FLAGS[modifier]

        return flags

    def array_enum_reference(
        self, declaration: VariableDeclaration, class_path: str
    ) -> ReferencePath:
        name = declaration.array_dimension_name

        if name is None:
            return ReferencePath()

        resolved = self.context.references.resolve_type(
            TypeReference(name),
            class_path,
            collect_visible_packages(self.config, self.context.packages),
            self.context.parents,
        )

        if resolved.category is not TypeCategory.ENUM:
            msg = f"Array dimension {name!r} does not resolve to an enum"
            raise NotImplementedError(msg)

        if resolved.declaration_path is None:
            msg = "Array dimension enum has no declaration path"
            raise ValueError(msg)

        return self.references.enum_reference(resolved.declaration_path)
