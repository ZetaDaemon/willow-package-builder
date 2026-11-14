from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING, cast

from willow_package_builder.builder.build_component import BuildComponent
from willow_package_builder.compiler.codegen.emitter import FunctionEmitter
from willow_package_builder.compiler.semantics.expression_resolver import ExpressionResolver
from willow_package_builder.compiler.semantics.function_body_validator import FunctionBodyValidator
from willow_package_builder.compiler.semantics.scope import FunctionScope
from willow_package_builder.compiler.semantics.types import TypeCategory
from willow_package_builder.compiler.syntax.declarations import (
    FunctionCategory,
    FunctionDeclaration,
)
from willow_package_builder.compiler.syntax.modifiers import FunctionModifier, ParameterModifier
from willow_package_builder.compiler.syntax.parser import FunctionParser
from willow_package_builder.logging import CompilationError, declaration_context, info
from willow_package_builder.package_config import collect_visible_packages
from willow_package_builder.payloads.class_payload import (
    FunctionFlags,
    UClassPayload,
    UFunctionPayload,
    UScriptStatePayload,
    UStatePayload,
)
from willow_package_builder.payloads.property_payloads import PropertyFlags, UPropertyPayload
from willow_package_builder.upackage import (
    CORE_FUNCTION_PATH,
    CORE_STATE_PATH,
    RETURN_VALUE_NAME,
    ObjectFlags,
    ReferencePath,
    UObject,
)

from .prepared_function import PreparedFunction

if TYPE_CHECKING:
    from willow_package_builder.builder.references import PackageReferences
    from willow_package_builder.compiler.syntax.expressions import Expression

    from .exports import ClassExport
    from .property_builder import PropertyBuilder

FUNCTION_MODIFIER_FLAGS: dict[FunctionModifier, FunctionFlags] = {
    # Implementation and dispatch
    FunctionModifier.NATIVE: FunctionFlags.NATIVE,
    FunctionModifier.STATIC: FunctionFlags.STATIC,
    FunctionModifier.FINAL: FunctionFlags.FINAL,
    # Access
    FunctionModifier.PRIVATE: FunctionFlags.PRIVATE,
    FunctionModifier.PROTECTED: FunctionFlags.PROTECTED,
    FunctionModifier.PUBLIC: FunctionFlags.PUBLIC,
    # Execution
    FunctionModifier.EXEC: FunctionFlags.EXEC,
    FunctionModifier.ITERATOR: FunctionFlags.ITERATOR,
    FunctionModifier.LATENT: FunctionFlags.LATENT,
    FunctionModifier.SINGULAR: FunctionFlags.SINGULAR,
    FunctionModifier.SIMULATED: FunctionFlags.SIMULATED,
    # Networking
    FunctionModifier.CLIENT: FunctionFlags.NET | FunctionFlags.NET_CLIENT,
    FunctionModifier.SERVER: FunctionFlags.NET | FunctionFlags.NET_SERVER,
    FunctionModifier.RELIABLE: FunctionFlags.NET_RELIABLE,
    FunctionModifier.UNRELIABLE: FunctionFlags.NONE,
}


@dataclass
class FunctionBuilder(BuildComponent):
    references: PackageReferences
    properties: PropertyBuilder

    def _parse_parameter_defaults(
        self, function: FunctionDeclaration, resolver: ExpressionResolver
    ) -> list[Expression | None]:
        defaults: list[Expression | None] = []
        owner = resolver.scope.class_path

        for parameter in function.parameters:
            if parameter.default_tokens is None:
                defaults.append(None)
                continue

            path = owner + function.name + parameter.name

            with declaration_context(path, parameter.location):
                if ParameterModifier.OPTIONAL not in parameter.modifiers:
                    msg = "Non-optional parameter cannot have a default"
                    raise CompilationError(msg)

                parser = FunctionParser.from_tokens(parameter.default_tokens, resolver)
                defaults.append(parser.parse_default_expression())

        return defaults

    def _process_function_parameters(
        self,
        function: FunctionDeclaration,
        function_payload: UFunctionPayload,
        function_object: UObject,
        class_path: ReferencePath,
    ) -> list[UObject]:
        properties: list[UObject] = []
        owner = class_path

        for parameter in function.parameters:
            path = owner + function.name + parameter.name

            with declaration_context(path, parameter.location):
                if (
                    parameter.array_dimension != 1
                    and ParameterModifier.OPTIONAL in parameter.modifiers
                ):
                    msg = "Optional fixed-array parameters are not implemented yet"
                    raise NotImplementedError(msg)

                parameter_flags = PropertyFlags.PARAM

                for modifier in parameter.modifiers:
                    match modifier:
                        case ParameterModifier.OUT:
                            parameter_flags |= PropertyFlags.OUT_PARAM
                            function_payload.function_flags |= FunctionFlags.HAS_OUT_PARAMS

                        case ParameterModifier.CONST:
                            parameter_flags |= PropertyFlags.CONST

                        case ParameterModifier.OPTIONAL:
                            parameter_flags |= PropertyFlags.OPTIONAL_PARAM

                        case ParameterModifier.COERCE:
                            parameter_flags |= PropertyFlags.COERCE_PARAM

                        case _:
                            msg = f"Unsupported parameter modifier {modifier.value!r}"
                            raise NotImplementedError(msg)

                properties.append(
                    self.properties.create_property(
                        function_object,
                        parameter.name,
                        parameter.type_ref,
                        class_path,
                        parameter_flags,
                        parameter.array_dimension,
                    )
                )

        return properties

    @staticmethod
    def _validate_override(
        function: FunctionDeclaration,
        inherited: FunctionDeclaration,
        path: ReferencePath,
        base_path: ReferencePath,
    ) -> None:
        if FunctionModifier.FINAL in inherited.modifiers:
            msg = f"{path} cannot override final function {base_path}"
            raise CompilationError(msg)

        if (
            inherited.func_category != function.func_category
            or (set(inherited.modifiers) - {FunctionModifier.NATIVE}) != set(function.modifiers)
            or inherited.return_type != function.return_type
            or len(inherited.parameters) != len(function.parameters)
            or any(
                base.type_ref != derived.type_ref
                or base.array_dimension != derived.array_dimension
                or set(base.modifiers) != set(derived.modifiers)
                for base, derived in zip(inherited.parameters, function.parameters, strict=True)
            )
        ):
            msg = f"Override {path} must match the declaration of {base_path}"
            raise CompilationError(msg)

    def _resolve_super_function(
        self, class_path: ReferencePath, function: FunctionDeclaration
    ) -> ReferencePath:
        parent = self.context.parents[class_path]
        if parent is None:
            return ReferencePath()

        references = self.context.references
        for owner, declaration in references.iter_class_hierarchy(parent, self.context.parents):
            for inherited in declaration.functions:
                if inherited.name != function.name:
                    continue

                path = class_path + function.name
                base_path = owner + inherited.name

                self._validate_override(function, inherited, path, base_path)

                return self.references.function_reference(base_path)
        return ReferencePath()

    def _resolve_super_state_function(
        self, class_path: ReferencePath, state_path: ReferencePath, function: FunctionDeclaration
    ) -> ReferencePath:
        state_name = state_path.name
        parent = self.context.parents[class_path]
        if parent is None:
            return ReferencePath()

        for owner, declaration in self.context.references.iter_class_hierarchy(
            parent, self.context.parents
        ):
            for state in declaration.states:
                if state.name != state_name:
                    continue

                for inherited in state.functions:
                    if inherited.name != function.name:
                        continue

                    base_path = owner + state.name + inherited.name
                    self._validate_override(
                        function, inherited, state_path + function.name, base_path
                    )

                    class_outer = self.references.class_object_reference(owner)

                    if owner.get_outer().name == self.config.name:
                        reference = class_outer + state.name + inherited.name
                        return self.package.lookup_object_by_path(reference).reference()

                    state_outer = self.references.ensure_import(
                        state.name, class_outer, *CORE_STATE_PATH.full_split()
                    )
                    return self.references.ensure_import(
                        inherited.name, state_outer, *CORE_FUNCTION_PATH.full_split()
                    )

        return ReferencePath()

    def _prepare_function(
        self,
        function: FunctionDeclaration,
        class_path: ReferencePath,
        owner_payload: UClassPayload | UStatePayload,
        owner_reference: ReferencePath,
    ) -> PreparedFunction:
        function_class = self.references.class_object_reference(CORE_FUNCTION_PATH)
        supported_modifiers = {
            FunctionModifier.STATIC,
            FunctionModifier.PROTECTED,
            FunctionModifier.SIMULATED,
            FunctionModifier.RELIABLE,
            FunctionModifier.SERVER,
        }

        if FunctionModifier.NATIVE in function.modifiers:
            msg = f"Cannot compile native function {function.name}"
            raise CompilationError(msg)

        match function.func_category:
            case FunctionCategory.FUNCTION:
                flags = FunctionFlags.DEFINED

            case FunctionCategory.EVENT:
                flags = FunctionFlags.DEFINED | FunctionFlags.EVENT

            case _:
                msg = f"Function category {function.func_category} is not supported yet"
                raise NotImplementedError(msg)

        for modifier in function.modifiers:
            if modifier not in supported_modifiers:
                msg = f"Unsupported function modifier {modifier!r} on {function.name}"
                raise NotImplementedError(msg)

            flag = FUNCTION_MODIFIER_FLAGS[modifier]

            flags |= flag

        super_function = (
            self._resolve_super_function(class_path, function)
            if isinstance(owner_payload, UClassPayload)
            else self._resolve_super_state_function(class_path, owner_reference, function)
        )

        if flags & FunctionFlags.NET and (
            not isinstance(owner_payload, UClassPayload) or super_function.is_none()
        ):
            msg = "Only class-level overrides of existing networked functions are supported"
            raise NotImplementedError(msg)

        scope = FunctionScope(
            class_path,
            function,
            self.context.references,
            self.context.parents,
            state_name=(
                owner_reference.name if isinstance(owner_payload, UScriptStatePayload) else None
            ),
        )

        resolver = ExpressionResolver(self.context, scope)

        if not function.has_body:
            msg = (
                f"Bodyless scripted function compilation is not supported yet: "
                f"{class_path}.{function.name}"
            )
            raise NotImplementedError(msg)

        body = FunctionParser.from_function_body(function, resolver).parse_function_body()
        parameter_defaults = self._parse_parameter_defaults(function, resolver)
        FunctionBodyValidator(resolver).validate_parameter_defaults(parameter_defaults)

        locals_ = body.function_locals

        return_type = self.context.references.resolve_type(
            function.return_type,
            class_path,
            collect_visible_packages(self.config, self.context.packages),
            self.context.parents,
        )

        if return_type.category not in (
            TypeCategory.VOID,
            TypeCategory.INT,
            TypeCategory.BOOL,
            TypeCategory.FLOAT,
            TypeCategory.STRING,
            TypeCategory.OBJECT,
            TypeCategory.CLASS,
            TypeCategory.BYTE,
            TypeCategory.NAME,
            TypeCategory.ARRAY,
            TypeCategory.STRUCT,
        ):
            msg = f"Function return type is not supported yet: {return_type}"
            raise NotImplementedError(msg)

        function_payload = UFunctionPayload(
            next_field=owner_payload.children,
            super_struct=super_function,
            function_flags=flags,
            friendly_name=function.name,
        )

        function_object = UObject(
            function.name,
            ObjectFlags.PUBLIC_EXPORT,
            owner_reference,
            function_class,
            payload=function_payload,
        )

        function_reference = function_object.reference()
        try:
            self.package.lookup_object_by_path(function_reference)
        except KeyError:
            pass
        else:
            msg = (
                f"Function {function.name} conflicts with an existing"
                f" declaration in {owner_reference}"
            )
            raise CompilationError(msg)

        self.package.add_export(function_object)

        properties: list[UObject] = self._process_function_parameters(
            function, function_payload, function_object, class_path
        )

        if function.return_type is not None:
            properties.append(
                self.properties.create_property(
                    function_object,
                    RETURN_VALUE_NAME,
                    function.return_type,
                    class_path,
                    PropertyFlags.PARAM | PropertyFlags.OUT_PARAM | PropertyFlags.RETURN_PARAM,
                )
            )

        owner = owner_reference

        for local in locals_:
            path = owner + function.name + local.name

            with declaration_context(path, local.location):
                obj = self.properties.create_property(
                    function_object,
                    local.name,
                    local.type_ref,
                    class_path,
                    PropertyFlags.NONE,
                    local.array_dimension,
                )
                payload = cast("UPropertyPayload", obj.payload)
                payload.array_enum = self.properties.array_enum_reference(local, class_path)
                properties.append(obj)

        for index, obj in enumerate(properties):
            payload = cast("UPropertyPayload", obj.payload)
            payload.next_field = (
                properties[index + 1].reference()
                if index + 1 < len(properties)
                else ReferencePath()
            )

        if properties:
            function_payload.children = properties[0].reference()

        prepared_function = PreparedFunction(resolver, body, function_object, parameter_defaults)

        owner_payload.children = function_reference
        owner_payload.function_map[function.name] = function_reference

        return prepared_function

    def _prepare_class_functions(
        self, class_path: ReferencePath, exports: ClassExport
    ) -> list[PreparedFunction]:
        class_payload = exports.class_object.payload

        if not isinstance(class_payload, UClassPayload):
            msg = f"Class must be linked before building functions: {class_path}"
            raise ValueError(msg)  # noqa: TRY004

        owner = class_path
        prepared: list[PreparedFunction] = []

        for function in exports.declaration.functions:
            path = owner + function.name

            with declaration_context(path, function.location):
                prepared.append(
                    self._prepare_function(
                        function, class_path, class_payload, exports.class_object.reference()
                    )
                )

        for state in exports.declaration.states:
            state_path = exports.class_object.reference() + state.name
            state_object = self.package.lookup_object_by_path(state_path)

            if not isinstance(state_object, UObject) or not isinstance(
                state_object.payload, UScriptStatePayload
            ):
                msg = f"State must be exported before building its functions: {state_path}"
                raise ValueError(msg)  # noqa: TRY004

            for function in state.functions:
                with declaration_context(state_path + function.name, function.location):
                    prepared.append(
                        self._prepare_function(
                            function, class_path, state_object.payload, state_path
                        )
                    )

        return prepared

    def _prepare_all_functions(self) -> list[PreparedFunction]:
        prepared: list[PreparedFunction] = []

        for class_path, exports in self.classes.items():
            prepared.extend(self._prepare_class_functions(class_path, exports))

        return prepared

    def build_class_functions(self) -> None:
        info("Preparing function bodies")
        start = perf_counter()
        prepared = self._prepare_all_functions()
        info(f"Prepared {len(prepared)} functions in {perf_counter() - start:.3f}s")

        info(f"Validating and emitting bytecode for {len(prepared)} functions")
        start = perf_counter()

        for function in prepared:
            scope = function.resolver.scope
            path = function.function_object.reference()

            with declaration_context(path, scope.function.location):
                payload = cast("UFunctionPayload", function.function_object.payload)
                emitter = FunctionEmitter(
                    function.resolver, self.references, function.function_object
                )
                payload.script = emitter.emit_body(function)

        info(f"Validated and emitted bytecode in {perf_counter() - start:.3f}s")
