from dataclasses import dataclass
from typing import TYPE_CHECKING

from willow_package_builder.builder.build_component import BuildComponent
from willow_package_builder.logging import CompilationError
from willow_package_builder.payloads.class_payload import UClassPayload
from willow_package_builder.payloads.enum_payload import UEnumPayload
from willow_package_builder.properties.values import EnumValue, IdentifierValue, Value
from willow_package_builder.upackage import ObjectFlags, ReferencePath, UObject

if TYPE_CHECKING:
    from willow_package_builder.builder.references import PackageReferences
    from willow_package_builder.compiler.semantics.types import ResolvedType

CORE_ENUM = ReferencePath("Core.Enum")


@dataclass
class EnumBuilder(BuildComponent):
    references: PackageReferences

    def build_class_enums(self) -> None:
        enum_class = self.references.class_object_reference(CORE_ENUM)

        for class_path, exports in self.classes.items():
            class_payload = exports.class_object.payload

            if not isinstance(class_payload, UClassPayload):
                msg = f"Class must be linked before building enums: {class_path}"
                raise ValueError(msg)  # noqa: TRY004

            for declaration in reversed(exports.declaration.enums):
                payload = UEnumPayload(
                    next_field=class_payload.children, names=list(declaration.members)
                )

                obj = UObject(
                    declaration.name,
                    ObjectFlags.PUBLIC_EXPORT,
                    exports.class_object.reference(),
                    enum_class,
                    payload=payload,
                )

                class_payload.children = self.package.add_export(obj)

    def construct_value(self, value: Value, resolved_type: ResolvedType) -> EnumValue:
        """Resolve an enum member, optionally qualified by its enum name or path."""
        path = resolved_type.declaration_path

        if path is None:
            msg = "Enum type has no declaration path"
            raise ValueError(msg)

        owner, name = path.split(require_outer=True)
        enum_member = self.context.references.resolve_enum(owner, name, self.context.parents)
        declaration = enum_member.declaration
        canonical_path = enum_member.owner_class + declaration.name

        match value:
            case IdentifierValue():
                qualifier, member_name = value.name.split()

                if qualifier is not None:
                    allowed = {ReferencePath(declaration.name), canonical_path}

                    if qualifier not in allowed:
                        msg = f"Expected enum {canonical_path}, got qualifier {qualifier!r}"
                        raise ValueError(msg)

            case EnumValue():
                if value.enum_name != declaration.name:
                    msg = f"Expected enum {canonical_path}, got {value.enum_name}"
                    raise ValueError(msg)

                if not 0 <= value.index < len(declaration.members):
                    msg = f"Invalid index {value.index} for enum {canonical_path}"
                    raise ValueError(msg)

                member = declaration.members[value.index]

                if member != value.member_name:
                    msg = f"Enum member does not match index {value.index} in {canonical_path}"
                    raise ValueError(msg)

                return EnumValue(declaration.name, member, value.index)

            case _:
                msg = f"Expected a member of {canonical_path}, got {type(value).__name__}"
                raise ValueError(msg)

        matches = [
            (index, member)
            for index, member in enumerate(declaration.members)
            if member == member_name
        ]

        if len(matches) > 1:
            indices = ", ".join(str(index) for index, _ in matches)
            msg = (
                f"Ambiguous member {member_name!r} of enum {canonical_path}; "
                f"it occurs at indices {indices}"
            )
            raise ValueError(msg)

        if matches:
            index, member = matches[0]
            return EnumValue(declaration.name, member, index)

        msg = f"Unknown member {member_name!r} of enum {canonical_path}"
        raise ValueError(msg)

    def initial_value(self, resolved_type: ResolvedType) -> EnumValue:
        """Construct the enum's initial value."""
        path = resolved_type.declaration_path

        if path is None:
            msg = "Enum type has no declaration path"
            raise ValueError(msg)

        owner, name = path.split(require_outer=True)
        declaration = self.context.references.resolve_enum(
            owner, name, self.context.parents
        ).declaration

        if not declaration.members:
            msg = f"Enum {path} has no members"
            raise CompilationError(msg)

        return EnumValue(declaration.name, declaration.members[0], 0)
