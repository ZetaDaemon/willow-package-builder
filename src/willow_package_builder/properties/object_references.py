from typing import TYPE_CHECKING

from willow_package_builder.compiler.semantics.intrinsics import IntrinsicDefinition
from willow_package_builder.logging import ObjectDefinitionError
from willow_package_builder.upackage import FName, Package, ReferencePath, UObject

if TYPE_CHECKING:
    from willow_package_builder.builder.build_context import BuildContext
    from willow_package_builder.properties.values import ObjectValue


def import_external_object(
    value: ObjectValue, package: Package, context: BuildContext
) -> ReferencePath:
    """Import an external object, assuming unknown nested outers are Objects."""
    path = value.path
    segments = path.full_split()

    if len(segments) < 2 or any(not segment for segment in segments):  # noqa: PLR2004
        msg = f"External object reference requires a full path: {value.path}"
        raise ValueError(msg)

    package_name, *nested_names, object_name = segments

    package_reference = ReferencePath(package_name)

    try:
        existing_package = package.lookup_object_by_path(package_reference)
    except KeyError:
        existing_package = None

    if isinstance(existing_package, UObject):
        msg = (
            f"Unknown object reference {value.path!r}; "
            f"package {package_name!r} is defined in this build"
        )
        raise ObjectDefinitionError(msg)

    outer = package.ensure_import(package_name, ReferencePath(), FName("Core"), FName("Package"))

    for name in nested_names:
        reference = outer + name

        try:
            existing = package.lookup_object_by_path(reference)
        except KeyError:
            outer = package.ensure_import(name, outer, FName("Core"), FName("Object"))
        else:
            # Preserve class information for already registered outers.
            outer = existing.reference()

    package_key = value.class_name.get_outer().name

    definition = context.references.lookup_class(value.class_name)

    if isinstance(definition, IntrinsicDefinition):
        class_package, class_name = definition.path.split(require_outer=True)
        class_package = class_package.name
    else:
        config = next(config for config in context.packages if config.name == package_key)
        class_package = config.name
        class_name = definition.name

    return package.ensure_import(object_name, outer, class_package, class_name)
