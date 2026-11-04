from copy import deepcopy

from willow_package_builder.upackage import FName

from .values import ArrayValue, EmptyValue, StructValue, Value


def merge_values(defaults: dict[FName, Value], overrides: dict[FName, Value]) -> dict[FName, Value]:
    """Apply overrides without modifying either input."""
    result = deepcopy(defaults)

    for name, supplied in overrides.items():
        previous = result.get(name)

        match previous, supplied:
            case StructValue(), StructValue():
                result[name] = StructValue(
                    merge_values(previous.values, supplied.values),
                    struct_path=supplied.struct_path or previous.struct_path,
                )

            case StructValue(), EmptyValue():
                # An empty struct update preserves its existing fields.
                pass

            case ArrayValue(), EmptyValue():
                result[name] = ArrayValue()

            case _:
                result[name] = deepcopy(supplied)

    return result
