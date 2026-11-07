from abc import ABC
from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True)
class SourceLocation:
    line: int
    column: int

    def __str__(self) -> str:
        return f"{self.line}:{self.column}"


class WarningCode(StrEnum):
    """Warning category."""

    UNQUALIFIED_CLASS = "unqualified-class"
    SHADOWED_INSTANCE_VARIABLE = "shadowed-instance-variable"
    EXPLICIT_ENUM_SENTINEL = "explicit-enum-sentinel"
    PLACEHOLDER_FUNCTION_BODY = "placeholder-function-body"
    UNSUPPORTED_INTERFACE_COMPILATION = "unsupported-interface-compilation"
    INVALID_REFERENCE_DEFAULT = "invalid-reference-default"
    EXTERNAL_ARCHETYPE_DEFAULTS = "external-archetype-defaults"


class WarningAction(StrEnum):
    """Warning action."""

    WARN = "warn"
    IGNORE = "ignore"
    ERROR = "error"


class PackageBuilderError(Exception, ABC):
    """Base class for errors thrown by the package builder.

    To be collected by the logger.
    """


class CompilationError(PackageBuilderError):
    """An error in the source being compiled."""

    location: SourceLocation | None
    context: str | None = None

    def __init__(
        self, message: str, location: SourceLocation | None = None, context: str | None = None
    ) -> None:
        super().__init__(message)
        self.location = location
        self.context = context

    def __str__(self) -> str:
        message = super().__str__()

        if self.location is not None:
            message = f"({self.location.line}, {self.location.column}) {message}"

        if self.context is not None:
            message = f"{self.context} {message}"

        return message


class ConfigError(PackageBuilderError):
    """An error in the package configuration."""


class ObjectDefinitionError(PackageBuilderError):
    """An error in the object definition."""


class ValueBuildError(PackageBuilderError):
    """Supplied property data cannot be converted to its declared type."""


class UnknownPropertyError(CompilationError):
    """A property or struct field could not be found."""


class UnsupportedFeatureError(NotImplementedError):
    """An unsupported feature whose declaration context has been attached."""
