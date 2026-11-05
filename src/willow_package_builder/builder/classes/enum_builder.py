from dataclasses import dataclass
from typing import TYPE_CHECKING

from willow_package_builder.builder.build_component import BuildComponent
from willow_package_builder.logging import CompilationError
from willow_package_builder.payloads.class_payload import UClassPayload
from willow_package_builder.payloads.enum_payload import UEnumPayload
from willow_package_builder.properties.values import EnumValue, IdentifierValue, Value
from willow_package_builder.upackage import FName, ObjectFlags, UObject

if TYPE_CHECKING:
    from willow_package_builder.builder.references import PackageReferences
    from willow_package_builder.compiler.semantics.types import ResolvedType


@dataclass
class EnumBuilder(BuildComponent):
    references: PackageReferences

    def build_class_enums(self) -> None:
        enum_class = self.references.class_object_reference("Core.Enum")

        for class_path, exports in self.classes.items():
            class_payload = exports.class_object.payload

            if not isinstance(class_payload, UClassPayload):
                msg = f"Class must be linked before building enums: {class_path}"
                raise ValueError(msg)  # noqa: TRY004

            for declaration in reversed(exports.declaration.enums):
                payload = UEnumPayload(
                    next_field=class_payload.children,
                    names=[FName(member) for member in declaration.members],
                )

                obj = UObject(
                    FName(declaration.name),
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

        owner, _, name = path.rpartition(".")
        enum_member = self.context.references.resolve_enum(owner, name, self.context.parents)
        declaration = enum_member.declaration
        canonical_path = f"{enum_member.owner_class}.{declaration.name}"

        match value:
            case IdentifierValue():
                qualifier, separator, member_name = value.name.rpartition(".")

                if separator:
                    allowed = {declaration.name.casefold(), canonical_path.casefold()}

                    if qualifier.casefold() not in allowed:
                        msg = f"Expected enum {canonical_path}, got qualifier {qualifier!r}"
                        raise ValueError(msg)
                else:
                    member_name = value.name

            case EnumValue():
                if value.enum_name != FName(declaration.name):
                    msg = f"Expected enum {canonical_path}, got {value.enum_name}"
                    raise ValueError(msg)

                if not 0 <= value.index < len(declaration.members):
                    msg = f"Invalid index {value.index} for enum {canonical_path}"
                    raise ValueError(msg)

                member = declaration.members[value.index]

                if FName(member) != value.member_name:
                    msg = f"Enum member does not match index {value.index} in {canonical_path}"
                    raise ValueError(msg)

                return EnumValue(FName(declaration.name), FName(member), value.index)

            case _:
                msg = f"Expected a member of {canonical_path}, got {type(value).__name__}"
                raise ValueError(msg)

        matches = [
            (index, member)
            for index, member in enumerate(declaration.members)
            if member.casefold() == member_name.casefold()
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
            return EnumValue(FName(declaration.name), FName(member), index)

        msg = f"Unknown member {member_name!r} of enum {canonical_path}"
        raise ValueError(msg)

    def initial_value(self, resolved_type: ResolvedType) -> EnumValue:
        """Construct the enum's initial value."""
        path = resolved_type.declaration_path

        if path is None:
            msg = "Enum type has no declaration path"
            raise ValueError(msg)

        owner, _, name = path.rpartition(".")
        declaration = self.context.references.resolve_enum(
            owner, name, self.context.parents
        ).declaration

        if not declaration.members:
            msg = f"Enum {path} has no members"
            raise CompilationError(msg)

        return EnumValue(FName(declaration.name), FName(declaration.members[0]), 0)
