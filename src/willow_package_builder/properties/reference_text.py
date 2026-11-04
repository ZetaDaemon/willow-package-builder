from willow_package_builder.logging import ValueBuildError


def parse_reference_text(context: str, value: str) -> tuple[str | None, str]:
    """Extract an optional class annotation and the referenced path."""
    text = value.strip()
    annotation, separator, remainder = text.partition("'")

    if not separator:
        if not text:
            msg = f"{context}: Reference path cannot be empty"
            raise ValueBuildError(msg)

        return None, text.replace(":", ".")

    annotation = annotation.strip()

    if not annotation or not remainder.endswith("'"):
        msg = f"{context}: Invalid reference syntax: {value!r}"
        raise ValueBuildError(msg)

    path = remainder[:-1].strip()

    if not path or "'" in path:
        msg = f"{context}: Invalid reference syntax: {value!r}"
        raise ValueBuildError(msg)

    return annotation, path.replace(":", ".")
