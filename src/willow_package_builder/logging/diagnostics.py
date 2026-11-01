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


class WarningAction(StrEnum):
    """Warning action."""

    WARN = "warn"
    IGNORE = "ignore"
    ERROR = "error"


class CompilationError(Exception):
    """An error in the source being compiled."""

    location: SourceLocation | None

    def __init__(self, message: str, location: SourceLocation | None = None) -> None:
        super().__init__(message)
        self.location = location

    def __str__(self) -> str:
        message = super().__str__()

        if self.location is not None:
            return f"({self.location.line}, {self.location.column}) {message}"

        return message


class ConfigError(Exception):
    """An error in the package configuration."""


class ObjectDefinitionError(Exception):
    """An error in the object definition."""
