from willow_package_builder.compiler.semantics.types import ResolvedType, TypeCategory
from willow_package_builder.compiler.syntax.defaults import (
    DefaultValue,
    LiteralDefaultValue,
    NameDefaultValue,
)
from willow_package_builder.payloads.instance_payload import (
    BoolPropertyOverride,
    BytePropertyOverride,
    PropertyOverride,
)
from willow_package_builder.payloads.property_values import (
    BoolValue,
    ByteValue,
    FloatValue,
    IntValue,
    NameValue,
    StringValue,
)
from willow_package_builder.upackage import FName


def build_scalar_default_override(
    name: FName, resolved_type: ResolvedType, value: DefaultValue
) -> PropertyOverride:
    """Convert an already validated scalar default into a property override."""
    match resolved_type.category, value:
        case TypeCategory.INT, LiteralDefaultValue(value=int() as number):
            return PropertyOverride(name, FName("IntProperty"), IntValue(number))

        case TypeCategory.BYTE, LiteralDefaultValue(value=int() as number):
            return BytePropertyOverride(name, FName("ByteProperty"), ByteValue(number))

        case TypeCategory.FLOAT, LiteralDefaultValue(value=float() as number):
            return PropertyOverride(name, FName("FloatProperty"), FloatValue(number))

        case TypeCategory.BOOL, LiteralDefaultValue(value=bool() as boolean):
            return BoolPropertyOverride(name, FName("BoolProperty"), BoolValue(boolean))

        case TypeCategory.STRING, LiteralDefaultValue(value=str() as text):
            return PropertyOverride(name, FName("StrProperty"), StringValue(text))

        case TypeCategory.NAME, NameDefaultValue(value=text):
            return PropertyOverride(name, FName("NameProperty"), NameValue(FName(text)))

        case _:
            msg = f"CDO default serialization for {resolved_type.category.value} is not implemented"
            raise NotImplementedError(msg)
