from copy import deepcopy
from typing import TYPE_CHECKING

from .values import ArrayValue, EmptyValue, StructValue, Value

if TYPE_CHECKING:
    from willow_package_builder.upackage import FName


def merge_values(defaults: dict[FName, Value], overrides: dict[FName, Value]) -> dict[FName, Value]:
    """Apply overrides without modifying either input."""
    result: dict[FName, Value] = {}

    for name, previous in defaults.items():
        if name not in overrides:
            result[name] = deepcopy(previous)
            continue

        supplied = overrides[name]

        match previous, supplied:
            case StructValue(), StructValue():
                result[name] = StructValue(
                    merge_values(previous.values, supplied.values),
                    struct_path=supplied.struct_path or previous.struct_path,
                )

            case StructValue(), EmptyValue():
                result[name] = deepcopy(previous)

            case ArrayValue(), EmptyValue():
                result[name] = ArrayValue()

            case _:
                result[name] = deepcopy(supplied)

    for name, supplied in overrides.items():
        if name not in defaults:
            result[name] = deepcopy(supplied)

    return result
