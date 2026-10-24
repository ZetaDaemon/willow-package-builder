from pathlib import Path

from willow_package_builder.bytecode import Bytecode, NativeFunction, ScriptOpcode
from willow_package_builder.payloads.class_payload import (
    ClassFlags,
    FunctionFlags,
    StateFlags,
    UClassPayload,
    UFunctionPayload,
)
from willow_package_builder.payloads.instance_payload import ObjectInstancePayload
from willow_package_builder.payloads.property_payloads import PropertyFlags, UIntPropertyPayload
from willow_package_builder.upackage import (
    ExternalReference,
    FName,
    ObjectFlags,
    Package,
    PackageFlags,
    PackageFormat,
    UObject,
)


def build_example_package() -> Package:
    package = Package(
        name=FName("ExampleClasses"),
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

    # External package.
    core_package = package.add_import(
        ExternalReference(
            name=FName("Core"), class_package=FName("Core"), class_name=FName("Package")
        )
    )

    # External classes.
    object_cls = package.add_import(
        ExternalReference(
            name=FName("Object"),
            outer=core_package,
            class_package=FName("Core"),
            class_name=FName("Class"),
        )
    )
    int_property = package.add_import(
        ExternalReference(
            name=FName("IntProperty"),
            outer=core_package,
            class_package=FName("Core"),
            class_name=FName("Class"),
        )
    )

    # Parent class's default object.
    default_object = package.add_import(
        ExternalReference(
            name=FName("Default__Object"),
            outer=core_package,
            class_package=FName("Core"),
            class_name=FName("Object"),
        )
    )

    # Reserve the exports before connecting their payloads.
    example_class = UObject(
        name=FName("ExampleClass"), flags=ObjectFlags.CLASS_EXPORT, super_object=object_cls
    )

    value_property = UObject(
        name=FName("Value"),
        outer=example_class.reference(),
        object_class=int_property,
        flags=ObjectFlags.DEFAULT_EXPORT,
    )

    class_default = UObject(
        name=FName("Default__ExampleClass"),
        object_class=example_class.reference(),
        flags=ObjectFlags.CDO_EXPORT,
        archetype=default_object,
    )

    package.add_export(example_class)
    package.add_export(value_property)
    package.add_export(class_default)

    # Declare: var int Value;
    value_property.payload = UIntPropertyPayload(
        array_dimension=1, property_flags=PropertyFlags.NONE
    )

    # No overrides: Value inherits its normal zero default.
    class_default.payload = ObjectInstancePayload()

    # Describe the class and connect its field and CDO.
    example_class.payload = UClassPayload(
        super_struct=object_cls,
        children=value_property.reference(),
        within=object_cls,
        default_object=class_default.reference(),
        class_flags=ClassFlags.COMPILED | ClassFlags.PARSED,
        state_flags=StateFlags.AUTO,
    )

    # Import the classes used by the new exports.
    function_class = ExternalReference(
        name=FName("Function"),
        outer=core_package,
        class_package=FName("Core"),
        class_name=FName("Class"),
    )
    package.add_import(function_class)

    # Reserve the function and its parameter.
    test_function = UObject(
        name=FName("Test"),
        outer=example_class.reference(),
        object_class=function_class.reference(),
        flags=ObjectFlags.DEFAULT_EXPORT,
    )

    number_parameter = UObject(
        name=FName("Number"),
        outer=test_function.reference(),
        object_class=int_property,
        flags=ObjectFlags.DEFAULT_EXPORT,
    )
    return_value = package.add_export(
        UObject(
            name=FName("ReturnValue"),
            outer=test_function.reference(),
            object_class=int_property,
            flags=ObjectFlags.DEFAULT_EXPORT,
            payload=UIntPropertyPayload(
                property_flags=(PropertyFlags.PARAM | PropertyFlags.RETURN_PARAM)
            ),
        )
    )

    package.add_export(test_function)
    package.add_export(number_parameter)

    # Declare the input parameter.
    number_parameter.payload = UIntPropertyPayload(
        property_flags=PropertyFlags.PARAM, next_field=return_value
    )

    # Return number * value
    script = Bytecode()

    script += ScriptOpcode.RETURN
    with script.native_function(NativeFunction.MULTIPLY_INT):
        script.add_local_variable(number_parameter.reference())
        script.add_instance_variable(value_property.reference())
    script += ScriptOpcode.END_OF_SCRIPT

    test_function.payload = UFunctionPayload(
        friendly_name=FName("Test"),
        function_flags=FunctionFlags.DEFINED,
        children=number_parameter.reference(),
        next_field=value_property.reference(),
        script=script,
    )

    # Replace the earlier class payload assignment to include Test.
    example_class.payload = UClassPayload(
        super_struct=object_cls,
        children=test_function.reference(),
        within=object_cls,
        default_object=class_default.reference(),
        class_flags=ClassFlags.COMPILED | ClassFlags.PARSED,
        state_flags=StateFlags.AUTO,
        function_map={FName("Test"): test_function.reference()},
    )

    return package


package = build_example_package()
(Path(__file__).parent / "ExampleClasses.upk").write_bytes(package.serialize())
