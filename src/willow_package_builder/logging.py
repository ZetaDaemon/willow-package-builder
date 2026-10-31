import sys
import traceback
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, TextIO, overload

from willow_package_builder.source_location import SourceLocation

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


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


class LogPrefix(StrEnum):
    INFO = "[INFO] "
    WARN = "[WARN] "
    ERROR = "[ERROR]"


@dataclass
class Logger:
    log_file: Path
    debug: bool = False

    warning_actions: dict[WarningCode, WarningAction] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.log_file.exists():
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            self.log_file.open("x").close()
        if not self.log_file.is_file():
            msg = f"{self.log_file} exists and is not a file."
            raise RuntimeError(msg)

        self.log_file.open("w").close()

    def _log_to_file(self, message: str, prefix: LogPrefix) -> None:
        with self.log_file.open("a", encoding="utf-8") as file:
            for line in message.splitlines() or [""]:
                print(f"{prefix} {line}", file=file)

    def _log(self, message: str, console_out: TextIO, file_prefix: LogPrefix) -> None:
        print(message, file=console_out)
        self._log_to_file(message, file_prefix)

    @overload
    def warning(self, code: WarningCode, message: str) -> None: ...
    @overload
    def warning(
        self, code: WarningCode, message: str, source: Path, line: int, column: int
    ) -> None: ...
    def warning(
        self,
        code: WarningCode,
        message: str,
        source: Path | None = None,
        line: int = 0,
        column: int = 0,
    ) -> None:
        action = self.warning_actions.get(code, WarningAction.WARN)

        if source is not None:
            message = f"{source}: {message} at {line}:{column}"

        match action:
            case WarningAction.IGNORE:
                return
            case WarningAction.WARN:
                self._log(f"warning [{code.value}]: {message}", sys.stderr, LogPrefix.WARN)
            case WarningAction.ERROR:
                msg = f"[{code.value}]: {message}"
                raise CompilationError(msg)

    def info(self, message: str) -> None:
        self._log(message, sys.stdout, LogPrefix.INFO)

    @contextmanager
    def catch_errors_and_warnings(self) -> Generator[None]:
        token = _active_logger.set(self)

        try:
            yield
        except (CompilationError, ConfigError) as error:
            self._log(f"{type(error).__name__}: {error}", sys.stderr, LogPrefix.ERROR)
            if self.debug:
                raise
            raise SystemExit(1) from None
        except Exception:
            self._log_to_file(traceback.format_exc(), LogPrefix.ERROR)
            raise
        finally:
            _active_logger.reset(token)


_active_logger: ContextVar[Logger | None] = ContextVar("active_logger", default=None)


@overload
def warn(code: WarningCode, message: str) -> None: ...
@overload
def warn(code: WarningCode, message: str, source: Path, line: int, column: int) -> None: ...
def warn(
    code: WarningCode, message: str, source: Path | None = None, line: int = 0, column: int = 0
) -> None:
    logger = _active_logger.get()
    if logger is None:
        msg = "No compiler logger is active."
        raise RuntimeError(msg)

    logger.warning(code, message, source, line, column)  # pyright: ignore[reportArgumentType]


def info(message: str):
    logger = _active_logger.get()
    if logger is None:
        msg = "No compiler logger is active."
        raise RuntimeError(msg)

    logger.info(message)
