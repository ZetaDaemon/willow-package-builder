from willow_package_builder.properties.values import (
    ArrayValue,
    BoolValue,
    ByteValue,
    EnumValue,
    FloatValue,
    IntValue,
    NameValue,
    NullValue,
    ObjectValue,
    StringValue,
    StructValue,
    Value,
)


def value_to_python(value: Value) -> object:
    """Expose a constructed property value as Python data."""
    match value:
        case IntValue() | ByteValue() | FloatValue() | BoolValue() | StringValue() | NameValue():
            return value.value

        case NullValue():
            return None

        case ObjectValue():
            return value.path if value.reference is None else value.reference

        case EnumValue():
            return value.member_name

        case ArrayValue():
            return [value_to_python(element) for element in value.elements]

        case StructValue():
            return {name: value_to_python(element) for name, element in value.values.items()}

        case _:
            msg = f"Python access for {type(value).__name__} is not implemented"
            raise NotImplementedError(msg)
