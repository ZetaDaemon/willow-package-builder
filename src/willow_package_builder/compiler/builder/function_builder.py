from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from willow_package_builder.compiler.codegen.emitter import FunctionEmitter
from willow_package_builder.compiler.semantics.expression_resolver import ExpressionResolver
from willow_package_builder.compiler.semantics.function_body_validator import FunctionBodyValidator
from willow_package_builder.compiler.semantics.scope import FunctionScope
from willow_package_builder.compiler.semantics.types import TypeCategory
from willow_package_builder.compiler.syntax.declarations import (
    FunctionCategory,
    FunctionDeclaration,
)
from willow_package_builder.compiler.syntax.parser import FunctionParser
from willow_package_builder.logging import CompilationError
from willow_package_builder.package_config import collect_visible_packages
from willow_package_builder.payloads.class_payload import (
    FunctionFlags,
    UClassPayload,
    UFunctionPayload,
)
from willow_package_builder.payloads.property_payloads import PropertyFlags, UPropertyPayload
from willow_package_builder.upackage import FName, ObjectFlags, ReferencePath, UObject

from .build_component import BuildComponent
from .prepared_function import PreparedFunction

if TYPE_CHECKING:
    from willow_package_builder.compiler.builder.exports import ClassExports
    from willow_package_builder.compiler.syntax.expressions import Expression

    from .property_builder import PropertyBuilder
    from .references import PackageReferences


@dataclass
class FunctionBuilder(BuildComponent):
    references: PackageReferences
    properties: PropertyBuilder

    def _parse_parameter_defaults(
        self, function: FunctionDeclaration, resolver: ExpressionResolver
    ) -> list[Expression | None]:
        defaults: list[Expression | None] = []

        for parameter in function.parameters:
            if parameter.default_tokens is None:
                defaults.append(None)
                continue

            if "optional" not in parameter.modifiers:
                msg = f"Non-optional parameter {parameter.name!r} cannot have a default"
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
        for parameter in function.parameters:
            parameter_flags = PropertyFlags.PARAM

            for modifier in parameter.modifiers:
                match modifier:
                    case "out":
                        parameter_flags |= PropertyFlags.OUT_PARAM
                        function_payload.function_flags |= FunctionFlags.HAS_OUT_PARAMS
                    case "const":
                        parameter_flags |= PropertyFlags.CONST
                    case "optional":
                        parameter_flags |= PropertyFlags.OPTIONAL_PARAM
                    case _:
                        msg = f"Unsupported parameter modifier {modifier!r}"
                        raise NotImplementedError(msg)

            properties.append(
                self.properties.create_property(
                    function_object, parameter.name, parameter.type_ref, class_path, parameter_flags
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
        supported_flags = {"static": FunctionFlags.STATIC, "protected": FunctionFlags.PROTECTED}

        if function.func_category is not FunctionCategory.FUNCTION:
            msg = f"Function category {function.func_category} is not supported yet"
            raise NotImplementedError(msg)

        flags = FunctionFlags.DEFINED

        for modifier in function.modifiers:
            flag = supported_flags.get(modifier)

            if flag is None:
                msg = f"Unsupported function modifier {modifier!r} on {function.name}"
                raise NotImplementedError(msg)

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
            ObjectFlags.DEFAULT_EXPORT,
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

        properties.extend(
            [
                self.properties.create_property(
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

        prepared_function = PreparedFunction(resolver, body, function_object, parameter_defaults)

        class_payload.children = function_reference
        class_payload.function_map[FName(function.name)] = function_reference

        return prepared_function

    def _prepare_class_functions(
        self, class_path: str, exports: ClassExports
    ) -> list[PreparedFunction]:

        class_payload = exports.class_object.payload

        if not isinstance(class_payload, UClassPayload):
            msg = f"Class must be linked before building functions: {class_path}"
            raise ValueError(msg)  # noqa: TRY004

        return [
            self._prepare_function(
                function, class_path, class_payload, exports.class_object.reference()
            )
            for function in exports.declaration.functions
        ]

    def _prepare_all_functions(self) -> list[PreparedFunction]:
        prepared: list[PreparedFunction] = []

        for class_path, exports in self.classes.items():
            prepared.extend(self._prepare_class_functions(class_path, exports))

        return prepared

    def build_class_functions(self) -> None:
        prepared = self._prepare_all_functions()

        for function in prepared:
            payload = cast("UFunctionPayload", function.function_object.payload)

            emitter = FunctionEmitter(function.resolver, self.references, function.function_object)
            payload.script = emitter.emit_body(function)
