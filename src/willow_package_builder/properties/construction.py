from willow_package_builder.compiler.semantics.types import ResolvedType, TypeCategory
from willow_package_builder.properties.values import (
    ArrayValue,
    BoolValue,
    ByteValue,
    FloatValue,
    IntValue,
    NameValue,
    NullValue,
    StringValue,
    Value,
)


def initial_scalar_value(resolved_type: ResolvedType) -> Value:
    match resolved_type.category:
        case TypeCategory.INT:
            return IntValue()

        case TypeCategory.BYTE:
            return ByteValue()

        case TypeCategory.FLOAT:
            return FloatValue()

        case TypeCategory.BOOL:
            return BoolValue()

        case TypeCategory.STRING:
            return StringValue()

        case TypeCategory.NAME:
            return NameValue()

        case TypeCategory.OBJECT | TypeCategory.CLASS:
            return NullValue()

        case TypeCategory.ARRAY:
            return ArrayValue()
        case _:
            msg = f"Initial values for {resolved_type.category.value} are not implemented"
            raise NotImplementedError(msg)
