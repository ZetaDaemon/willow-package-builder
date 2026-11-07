from willow_package_builder.logging import ValueBuildError
from willow_package_builder.upackage import ReferencePath


def parse_reference_text(
    context: str, value: str, reference_base: ReferencePath | None
) -> tuple[ReferencePath | None, ReferencePath]:
    """Parse a reference and expand an explicitly relative object path."""
    text = value.strip()
    annotation_text, separator, remainder = text.partition("'")

    if separator:
        annotation_text = annotation_text.strip()

        if not annotation_text or not remainder.endswith("'"):
            msg = f"{context}: Invalid reference syntax: {value!r}"
            raise ValueBuildError(msg)

        path_text = remainder[:-1].strip()

        if "'" in path_text:
            msg = f"{context}: Invalid reference syntax: {value!r}"
            raise ValueBuildError(msg)
    else:
        annotation_text = ""
        path_text = text

    if not path_text:
        msg = f"{context}: Reference path cannot be empty"
        raise ValueBuildError(msg)

    path_text = path_text.replace(":", ".")
    outer = None

    if path_text.startswith("./"):
        if reference_base is None or reference_base.is_none():
            msg = f"{context}: Relative reference requires a containing object"
            raise ValueBuildError(msg)

        path_text = path_text[2:]
        outer = reference_base

    if "/" in path_text or "\\" in path_text:
        msg = f"{context}: Invalid reference path: {value!r}"
        raise ValueBuildError(msg)

    try:
        annotation = ReferencePath(annotation_text) if annotation_text else None
        path = ReferencePath(path_text, outer)
    except ValueError as error:
        msg = f"{context}: Invalid reference {value!r}: {error}"
        raise ValueBuildError(msg) from error

    return annotation, path
