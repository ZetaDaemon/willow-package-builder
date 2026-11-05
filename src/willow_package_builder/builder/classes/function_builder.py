from dataclasses import dataclass
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
from willow_package_builder.logging import CompilationError, declaration_context
from willow_package_builder.package_config import collect_visible_packages
from willow_package_builder.payloads.class_payload import (
    FunctionFlags,
    UClassPayload,
    UFunctionPayload,
)
from willow_package_builder.payloads.property_payloads import PropertyFlags, UPropertyPayload
from willow_package_builder.upackage import FName, ObjectFlags, ReferencePath, UObject

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
        owner = self.context.references.display_class_path(resolver.scope.class_path)

        for parameter in function.parameters:
            if parameter.default_tokens is None:
                defaults.append(None)
                continue

            path = f"{owner}.{function.name}.{parameter.name}"

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
        class_path: str,
    ) -> list[UObject]:
        properties: list[UObject] = []
        owner = self.context.references.display_class_path(class_path)

        for parameter in function.parameters:
            path = f"{owner}.{function.name}.{parameter.name}"

            with declaration_context(path, parameter.location):
                if parameter.array_dimension_name is not None or parameter.array_dimension != 1:
                    msg = "Compiling fixed-array parameters is not implemented"
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
                    )
                )

        return properties

    def _prepare_function(
        self,
        function: FunctionDeclaration,
        class_path: str,
        class_payload: UClassPayload,
        class_object_reference: ReferencePath,
    ) -> PreparedFunction:
        function_class = self.references.class_object_reference("Core.Function")
        supported_modifiers = {FunctionModifier.STATIC, FunctionModifier.PROTECTED}

        if function.func_category is not FunctionCategory.FUNCTION:
            msg = f"Function category {function.func_category} is not supported yet"
            raise NotImplementedError(msg)

        flags = FunctionFlags.DEFINED

        if FunctionModifier.NATIVE in function.modifiers:
            msg = f"Cannot compile native function {function.name}"
            raise CompilationError(msg)

        for modifier in function.modifiers:
            if modifier not in supported_modifiers:
                msg = f"Unsupported function modifier {modifier!r} on {function.name}"
                raise NotImplementedError(msg)

            flag = FUNCTION_MODIFIER_FLAGS[modifier]

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
                        "is not supported by the function builder yet"
                    )
                    raise NotImplementedError(msg)

        scope = FunctionScope(class_path, function, self.context.references, self.context.parents)

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
        ):
            msg = f"Function return type is not supported yet: {return_type!r}"
            raise NotImplementedError(msg)

        function_payload = UFunctionPayload(
            friendly_name=FName(function.name),
            function_flags=flags,
            next_field=class_payload.children,
        )

        function_object = UObject(
            FName(function.name),
            ObjectFlags.PUBLIC_EXPORT,
            class_object_reference,
            function_class,
            payload=function_payload,
        )

        function_reference = self.package.add_export(function_object)

        properties: list[UObject] = self._process_function_parameters(
            function, function_payload, function_object, class_path
        )

        if function.return_type is not None:
            properties.append(
                self.properties.create_property(
                    function_object,
                    "ReturnValue",
                    function.return_type,
                    class_path,
                    PropertyFlags.PARAM | PropertyFlags.OUT_PARAM | PropertyFlags.RETURN_PARAM,
                )
            )

        owner = self.context.references.display_class_path(class_path)

        for local in locals_:
            path = f"{owner}.{function.name}.{local.name}"

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

        class_payload.children = function_reference
        class_payload.function_map[FName(function.name)] = function_reference

        return prepared_function

    def _prepare_class_functions(
        self, class_path: str, exports: ClassExport
    ) -> list[PreparedFunction]:
        class_payload = exports.class_object.payload

        if not isinstance(class_payload, UClassPayload):
            msg = f"Class must be linked before building functions: {class_path}"
            raise ValueError(msg)  # noqa: TRY004

        owner = self.context.references.display_class_path(class_path)
        prepared: list[PreparedFunction] = []

        for function in exports.declaration.functions:
            path = f"{owner}.{function.name}"

            with declaration_context(path, function.location):
                prepared.append(
                    self._prepare_function(
                        function, class_path, class_payload, exports.class_object.reference()
                    )
                )

        return prepared

    def _prepare_all_functions(self) -> list[PreparedFunction]:
        prepared: list[PreparedFunction] = []

        for class_path, exports in self.classes.items():
            prepared.extend(self._prepare_class_functions(class_path, exports))

        return prepared

    def build_class_functions(self) -> None:
        prepared = self._prepare_all_functions()

        for function in prepared:
            scope = function.resolver.scope
            owner = self.context.references.display_class_path(scope.class_path)
            path = f"{owner}.{scope.function.name}"

            with declaration_context(path, scope.function.location):
                payload = cast("UFunctionPayload", function.function_object.payload)
                emitter = FunctionEmitter(
                    function.resolver, self.references, function.function_object
                )
                payload.script = emitter.emit_body(function)
