from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from willow_package_builder.compiler.codegen.emitter import FunctionEmitter
from willow_package_builder.compiler.semantics.expression_resolver import ExpressionResolver
from willow_package_builder.compiler.semantics.scope import FunctionScope
from willow_package_builder.compiler.semantics.types import TypeType
from willow_package_builder.compiler.syntax.declarations import FunctionType
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

if TYPE_CHECKING:
    from .property_builder import PropertyBuilder
    from .references import PackageReferences


@dataclass
class FunctionBuilder(BuildComponent):
    references: PackageReferences
    properties: PropertyBuilder

    def build_class_functions(self) -> None:
        function_class = self.references.class_object_reference("Core.Function")

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
                                "is not supported by the function builder yet"
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
                        self.properties.create_property(
                            function_object,
                            parameter.name,
                            parameter.type_ref,
                            class_path,
                            parameter_flags,
                        )
                    )

                if function.return_type is not None:
                    properties.append(
                        self.properties.create_property(
                            function_object,
                            "ReturnValue",
                            function.return_type,
                            class_path,
                            PropertyFlags.PARAM | PropertyFlags.RETURN_PARAM,
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

                emitter = FunctionEmitter(resolver, self.references, function_object)
                function_payload.script = emitter.emit_body(body)

                class_payload.children = function_reference
                class_payload.function_map[FName(function.name)] = function_reference
