from collections.abc import Generator
from contextlib import contextmanager

from .diagnostics import CompilationError, SourceLocation, UnsupportedFeatureError


@contextmanager
def declaration_context(path: str, location: SourceLocation | None) -> Generator[None]:
    try:
        yield
    except CompilationError as error:
        if error.context is None:
            error.context = path

            if error.location is None:
                error.location = location

        raise
    except UnsupportedFeatureError:
        raise
    except NotImplementedError as error:
        position = ""

        if location is not None:
            position = f" ({location.line}, {location.column})"

        msg = f"{path}{position} {error}"
        raise UnsupportedFeatureError(msg) from error
