from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from willow_package_builder.logging import CompilationError, WarningCode, info, warn
from willow_package_builder.package_config import collect_visible_packages
from willow_package_builder.payloads.class_payload import (
    ClassFlags,
    FunctionFlags,
    StateFlags,
    UClassPayload,
    UFunctionPayload,
)
from willow_package_builder.payloads.enum_payload import UEnumPayload
from willow_package_builder.payloads.instance_payload import ObjectInstancePayload
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
from willow_package_builder.payloads.struct_payload import StructFlags, UScriptStructPayload
from willow_package_builder.upackage import (
    ExternalReference,
    FName,
    ObjectFlags,
    Package,
    PackageFlags,
    PackageFormat,
    ReferencePath,
    UObject,
)

from .declarations import FunctionType, StructDeclaration, TypeReference
from .emitter import FunctionEmitter
from .expression_resolver import ExpressionResolver
from .intrinsics import IntrinsicDefinition
from .lexer import TokenType
from .parser import FunctionParser
from .scope import FunctionScope
from .types import TypeType

if TYPE_CHECKING:
    from willow_package_builder.package_config import PackageConfig

    from .build_context import BuildContext
    from .declarations import ClassDeclaration


@dataclass
class ClassExports:
    declaration: ClassDeclaration
    class_object: UObject
    default_object: UObject


@dataclass
class StructExports:
    owner_class: str
    declaration: StructDeclaration
    struct_object: UObject


@dataclass
class PackageBuilder:
    context: BuildContext
    config: PackageConfig

    package: Package = field(init=False)
    classes: dict[str, ClassExports] = field(default_factory=dict, init=False)
    structs: dict[str, StructExports] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.package = Package(
            name=FName(self.config.name),
            format=PackageFormat(
                version=832, license_version=46, engine_version=1712575, cooker_version=134
            ),
            flags=(
                PackageFlags.ALLOW_DOWNLOAD
                | PackageFlags.COOKED
                | PackageFlags.CONTAINS_SCRIPT
                | PackageFlags.STRIPPED_SOURCE
            ),
        )

    def build(self) -> Package:
        self.reserve_classes()
        self.link_classes()
        self.reserve_structs()
        self.link_structs()
        self.validate_struct_layouts()
        self.build_class_enums()
        self.build_struct_fields()
        self.build_class_fields()
        self.build_class_functions()

        return self.package

    def reserve_classes(self) -> None:
        package_name = self.config.name.casefold()

        for class_path in self.context.class_order:
            if class_path.partition(".")[0] != package_name:
                continue

            declaration = self.context.references.classes[class_path]

            if declaration.is_interface:
                warn(
                    WarningCode.UNSUPPORTED_INTERFACE_COMPILATION,
                    f"Interface {class_path!r} is available for reference only; "
                    "its export will be omitted because interface compilation "
                    "is not supported yet.",
                )
                continue

            info(f"Compiling class {class_path}")
            class_object = UObject(name=FName(declaration.name), flags=ObjectFlags.CLASS_EXPORT)

            class_reference = self.package.add_export(class_object)

            default_object = UObject(
                name=FName(f"Default__{declaration.name}"),
                object_class=class_reference,
                flags=ObjectFlags.CDO_EXPORT,
                payload=ObjectInstancePayload(),
            )

            self.package.add_export(default_object)

            self.classes[class_path] = ClassExports(
                declaration=declaration, class_object=class_object, default_object=default_object
            )

    def ensure_import(
        self, *, name: str, outer: ReferencePath, class_package: str, class_name: str
    ) -> ReferencePath:
        obj = ExternalReference(
            name=FName(name),
            outer=outer,
            class_package=FName(class_package),
            class_name=FName(class_name),
        )
        reference = obj.reference()

        try:
            existing = self.package.lookup_object_by_path(reference)
        except KeyError:
            return self.package.add_import(obj)

        if (
            not isinstance(existing, ExternalReference)
            or existing.class_package != obj.class_package
            or existing.class_name != obj.class_name
        ):
            msg = f"Conflicting import definition for {reference}"
            raise ValueError(msg)

        return reference

    def class_object_reference(
        self, class_path: str, *, default_object: bool = False
    ) -> ReferencePath:
        class_path = class_path.casefold()
        definition = self.context.references.lookup_class(class_path)

        if isinstance(definition, IntrinsicDefinition):
            if default_object:
                msg = (
                    f"Default-object references for intrinsic "
                    f"{definition.path!r} are not supported yet"
                )
                raise CompilationError(msg)

            package_name, _, name = definition.path.partition(".")

            package_reference = self.ensure_import(
                name=package_name, outer=ReferencePath(), class_package="Core", class_name="Package"
            )

            return self.ensure_import(
                name=name,
                outer=package_reference,
                class_package=definition.class_package,
                class_name=definition.class_name,
            )

        if definition.is_interface:
            msg = (
                f"Cannot reference interface {class_path!r} as a local export: "
                "interface compilation is not supported yet"
            )
            raise CompilationError(msg)

        package_key = class_path.partition(".")[0]

        if package_key == self.config.name.casefold():
            exports = self.classes[class_path]
            obj = exports.default_object if default_object else exports.class_object
            return obj.reference()

        config = next(
            config for config in self.context.packages if config.name.casefold() == package_key
        )

        package_reference = self.ensure_import(
            name=config.name, outer=ReferencePath(), class_package="Core", class_name="Package"
        )

        if default_object:
            return self.ensure_import(
                name=f"Default__{definition.name}",
                outer=package_reference,
                class_package=config.name,
                class_name=definition.name,
            )

        return self.ensure_import(
            name=definition.name, outer=package_reference, class_package="Core", class_name="Class"
        )

    def resolve_within_class(self, class_path: str) -> str:
        current: str | None = class_path.casefold()

        while current is not None:
            declaration = self.context.references.classes[current]

            if declaration.within is not None:
                package_key = current.partition(".")[0]
                config = next(
                    config
                    for config in self.context.packages
                    if config.name.casefold() == package_key
                )

                resolved, _ = self.context.references.resolve_class(
                    declaration.within,
                    current_package=config.name,
                    visible_packages=collect_visible_packages(config, self.context.packages),
                )
                return resolved

            current = self.context.parents[current]

        return "core.object"

    def link_classes(self) -> None:
        supported_flags = {
            "abstract": ClassFlags.ABSTRACT,
            "editinlinenew": ClassFlags.EDIT_INLINE_NEW,
            "perobjectlocalized": ClassFlags.PER_OBJECT_LOCALIZED,
        }

        for class_path, exports in self.classes.items():
            parent = self.context.parents[class_path]

            if parent is None:
                msg = "Building root classes is not supported yet"
                raise CompilationError(msg)

            flags = ClassFlags.COMPILED | ClassFlags.PARSED

            for modifier in exports.declaration.modifiers:
                flag = supported_flags.get(modifier.name.casefold())

                if flag is None:
                    msg = (
                        f"Class modifier {modifier.name!r} on {class_path} "
                        "is not supported by the package builder yet"
                    )
                    raise CompilationError(msg)

                flags |= flag

            parent_reference = self.class_object_reference(parent)

            exports.class_object.super_object = parent_reference

            exports.default_object.archetype = self.class_object_reference(
                parent, default_object=True
            )

            exports.class_object.payload = UClassPayload(
                super_struct=parent_reference,
                within=self.class_object_reference(self.resolve_within_class(class_path)),
                default_object=exports.default_object.reference(),
                class_flags=flags,
                state_flags=StateFlags.AUTO,
            )

    def build_class_fields(self) -> None:
        for class_path, exports in self.classes.items():
            class_payload = exports.class_object.payload

            if not isinstance(class_payload, UClassPayload):
                msg = f"Class must be linked before building fields: {class_path}"
                raise ValueError(msg)  # noqa: TRY004

            # Prepending in reverse preserves declaration order.
            for variable in reversed(exports.declaration.variables):
                property_flags = PropertyFlags.NONE

                for modifier in variable.modifiers:
                    if modifier == "const":
                        property_flags |= PropertyFlags.CONST
                    else:
                        msg = (
                            f"Unsupported field modifier {modifier!r} "
                            f"on {class_path}.{variable.name}"
                        )
                        raise CompilationError(msg)

                category = FName("None")

                if variable.category_tokens is not None:
                    property_flags |= PropertyFlags.EDIT
                    tokens = variable.category_tokens

                    if tokens:
                        if len(tokens) != 1 or tokens[0].type is not TokenType.IDENTIFIER:
                            msg = f"Unsupported category syntax on {class_path}.{variable.name}"
                            raise CompilationError(msg)

                        category = FName(tokens[0].text)

                field_object = self.create_property(
                    exports.class_object,
                    variable.name,
                    variable.type_ref,
                    class_path,
                    property_flags,
                    variable.array_dimension,
                )

                payload = cast("UPropertyPayload", field_object.payload)
                payload.category = category
                payload.next_field = class_payload.children

                class_payload.children = field_object.reference()

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
            current_class=class_path,
            visible_packages=collect_visible_packages(self.config, self.context.packages),
            parents=self.context.parents,
        )

        payload: UPropertyPayload

        match resolved.type:
            case TypeType.INT:
                payload = UIntPropertyPayload()

            case TypeType.OBJECT:
                if resolved.declaration_path is None:
                    msg = "Resolved object type has no declaration path"
                    raise ValueError(msg)

                payload = UObjectPropertyPayload(
                    property_class=self.class_object_reference(resolved.declaration_path)
                )

            case TypeType.BYTE:
                payload = UBytePropertyPayload()

            case TypeType.FLOAT:
                payload = UFloatPropertyPayload()

            case TypeType.BOOL:
                payload = UBoolPropertyPayload()

            case TypeType.NAME:
                payload = UNamePropertyPayload()

            case TypeType.STRING:
                payload = UStrPropertyPayload()
                flags |= PropertyFlags.NEED_CTOR_LINK

            case TypeType.CLASS:
                bound = resolved.arguments[0]

                if bound.declaration_path is None:
                    msg = "Resolved class bound has no declaration path"
                    raise ValueError(msg)

                payload = UClassPropertyPayload(
                    property_class=self.class_object_reference("Core.Class"),
                    meta_class=self.class_object_reference(bound.declaration_path),
                )

            case TypeType.ARRAY:
                payload = UArrayPropertyPayload(inner=ReferencePath())
                flags |= PropertyFlags.NEED_CTOR_LINK

            case TypeType.ENUM:
                if resolved.declaration_path is None:
                    msg = "Resolved enum type has no declaration path"
                    raise ValueError(msg)

                payload = UBytePropertyPayload(enum=self.enum_reference(resolved.declaration_path))

            case TypeType.STRUCT:
                if resolved.declaration_path is None:
                    msg = "Resolved struct type has no declaration path"
                    raise ValueError(msg)

                payload = UStructPropertyPayload(
                    struct=self.struct_reference(resolved.declaration_path)
                )

                if self.struct_needs_ctor_link(resolved.declaration_path):
                    flags |= PropertyFlags.NEED_CTOR_LINK

            case _:
                msg = f"Property {owner.reference()}.{name} requires unsupported type {resolved!r}"
                raise CompilationError(msg)

        payload.array_dimension = array_dimension
        payload.property_flags = flags

        definition = self.context.references.property_class(resolved)
        property_class = self.class_object_reference(definition.path)

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

    def build_class_functions(self) -> None:
        function_class = self.class_object_reference("Core.Function")

        supported_flags = {"static": FunctionFlags.STATIC, "protected": FunctionFlags.PROTECTED}

        for class_path, exports in self.classes.items():
            class_payload = exports.class_object.payload

            if not isinstance(class_payload, UClassPayload):
                msg = f"Class must be linked before building functions: {class_path}"
                raise ValueError(msg)  # noqa: TRY004

            for function in exports.declaration.functions:
                if function.func_type is not FunctionType.FUNCTION:
                    msg = f"Function type {function.func_type} is not supported yet"
                    raise CompilationError(msg)

                flags = FunctionFlags.DEFINED

                for modifier in function.modifiers:
                    flag = supported_flags.get(modifier)

                    if flag is None:
                        msg = f"Unsupported function modifier {modifier!r} on {function.name}"
                        raise CompilationError(msg)

                    flags |= flag

                # Don't silently emit an override without linking its base function.
                parent = self.context.parents[class_path]

                if parent is not None:
                    for owner, ancestor in self.context.references.iter_class_hierarchy(
                        parent, self.context.parents
                    ):
                        if any(
                            candidate.name.casefold() == function.name.casefold()
                            for candidate in ancestor.functions
                        ):
                            msg = (
                                f"Override {class_path}.{function.name} of {owner} "
                                "is not supported by the placeholder builder yet"
                            )
                            raise CompilationError(msg)

                scope = FunctionScope(
                    class_path, function, self.context.references, self.context.parents
                )

                resolver = ExpressionResolver(self.context, scope)

                body = FunctionParser.from_function_body(
                    function, expression_resolver=resolver
                ).parse_function_body()

                locals_ = body.locals

                return_type = self.context.references.resolve_type(
                    function.return_type,
                    current_class=class_path,
                    visible_packages=collect_visible_packages(self.config, self.context.packages),
                    parents=self.context.parents,
                )

                if return_type.type not in (TypeType.VOID, TypeType.INT):
                    msg = f"Function return type is not supported yet: {return_type!r}"
                    raise CompilationError(msg)

                function_payload = UFunctionPayload(
                    friendly_name=FName(function.name),
                    function_flags=flags,
                    next_field=class_payload.children,
                )

                function_object = UObject(
                    FName(function.name),
                    ObjectFlags.DEFAULT_EXPORT,
                    exports.class_object.reference(),
                    function_class,
                    payload=function_payload,
                )

                function_reference = self.package.add_export(function_object)
                properties: list[UObject] = []

                for parameter in function.parameters:
                    parameter_flags = PropertyFlags.PARAM

                    for modifier in parameter.modifiers:
                        if modifier == "out":
                            parameter_flags |= PropertyFlags.OUT_PARAM
                            function_payload.function_flags |= FunctionFlags.HAS_OUT_PARAMS
                        elif modifier == "const":
                            parameter_flags |= PropertyFlags.CONST
                        else:
                            msg = f"Unsupported parameter modifier {modifier!r}"
                            raise CompilationError(msg)

                    if parameter.default_tokens is not None:
                        msg = "Parameter defaults are not supported by the builder yet"
                        raise CompilationError(msg)

                    properties.append(
                        self.create_property(
                            function_object,
                            parameter.name,
                            parameter.type_ref,
                            class_path,
                            parameter_flags,
                        )
                    )

                if function.return_type is not None:
                    properties.append(
                        self.create_property(
                            function_object,
                            "ReturnValue",
                            function.return_type,
                            class_path,
                            PropertyFlags.PARAM | PropertyFlags.RETURN_PARAM,
                        )
                    )

                properties.extend(
                    [
                        self.create_property(
                            function_object,
                            local.name,
                            local.type_ref,
                            class_path,
                            PropertyFlags.NONE,
                            local.array_dimension,
                        )
                        for local in locals_
                    ]
                )

                for index, obj in enumerate(properties):
                    payload = cast("UPropertyPayload", obj.payload)
                    payload.next_field = (
                        properties[index + 1].reference()
                        if index + 1 < len(properties)
                        else ReferencePath()
                    )

                if properties:
                    function_payload.children = properties[0].reference()

                emitter = FunctionEmitter(resolver, self, function_object)
                function_payload.script = emitter.emit_body(body)

                class_payload.children = function_reference
                class_payload.function_map[FName(function.name)] = function_reference

    def build_class_enums(self) -> None:
        enum_class = self.class_object_reference("Core.Enum")

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
                    ObjectFlags.DEFAULT_EXPORT,
                    exports.class_object.reference(),
                    enum_class,
                    payload=payload,
                )

                class_payload.children = self.package.add_export(obj)

    def enum_reference(self, enum_path: str) -> ReferencePath:
        owner_path, separator, name = enum_path.rpartition(".")

        if not separator:
            msg = f"Expected a qualified enum path: {enum_path}"
            raise ValueError(msg)

        member = self.context.references.resolve_enum(owner_path, name, self.context.parents)

        outer = self.class_object_reference(member.owner_class)
        package_name = member.owner_class.partition(".")[0]

        if package_name.casefold() == self.config.name.casefold():
            reference = outer + FName(member.declaration.name)

            # Local enum exports must already have been built.
            return self.package.lookup_object_by_path(reference).reference()

        return self.ensure_import(
            name=member.declaration.name, outer=outer, class_package="Core", class_name="Enum"
        )

    def reserve_structs(self) -> None:
        struct_class = self.class_object_reference("Core.ScriptStruct")

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

    def struct_reference(self, struct_path: str) -> ReferencePath:
        owner_path, separator, name = struct_path.rpartition(".")

        if not separator:
            msg = f"Expected a qualified struct path: {struct_path}"
            raise ValueError(msg)

        member = self.context.references.resolve_struct(owner_path, name, self.context.parents)

        path = f"{member.owner_class}.{member.declaration.name}".casefold()
        package_name = member.owner_class.partition(".")[0]

        if package_name.casefold() == self.config.name.casefold():
            return self.structs[path].struct_object.reference()

        outer = self.class_object_reference(member.owner_class)

        return self.ensure_import(
            name=member.declaration.name,
            outer=outer,
            class_package="Core",
            class_name="ScriptStruct",
        )

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
                parent_reference = self.struct_reference(parent_path)
                exports.struct_object.super_object = parent_reference
                payload.super_struct = parent_reference

            payload.next_field = class_payload.children
            class_payload.children = exports.struct_object.reference()

    def build_struct_fields(self) -> None:
        for path, exports in self.structs.items():
            payload = exports.struct_object.payload

            if not isinstance(payload, UScriptStructPayload):
                msg = f"Struct has an invalid payload: {path}"
                raise TypeError(msg)

            for variable in reversed(exports.declaration.variables):
                flags = PropertyFlags.NONE

                for modifier in variable.modifiers:
                    if modifier == "const":
                        flags |= PropertyFlags.CONST
                    else:
                        msg = f"Unsupported struct field modifier {modifier!r} on {path}.{variable.name}"
                        raise CompilationError(msg)

                category = FName("None")

                if variable.category_tokens is not None:
                    flags |= PropertyFlags.EDIT
                    tokens = variable.category_tokens

                    if tokens:
                        if len(tokens) != 1 or tokens[0].type is not TokenType.IDENTIFIER:
                            msg = f"Unsupported category syntax on {path}.{variable.name}"
                            raise CompilationError(msg)

                        category = FName(tokens[0].text)

                obj = self.create_property(
                    exports.struct_object,
                    variable.name,
                    variable.type_ref,
                    exports.owner_class,
                    flags,
                    variable.array_dimension,
                )

                field_payload = cast("UPropertyPayload", obj.payload)
                field_payload.category = category
                field_payload.next_field = payload.children

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
                type_ref,
                current_class=member.owner_class,
                visible_packages=visible,
                parents=self.context.parents,
            )

            if resolved.type in (TypeType.STRING, TypeType.ARRAY):
                return True

            if resolved.type is TypeType.STRUCT:
                if resolved.declaration_path is None:
                    msg = "Resolved struct type has no declaration path"
                    raise ValueError(msg)

                if self.struct_needs_ctor_link(resolved.declaration_path):
                    return True

        return False

    def manifest(self) -> dict[str, object]:
        return {
            "classes": [
                f"{self.config.name}.{exports.class_object.reference()}"
                for exports in self.classes.values()
            ]
        }
