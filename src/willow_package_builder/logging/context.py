from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from .diagnostics import CompilationError, SourceLocation, UnsupportedFeatureError

if TYPE_CHECKING:
    from willow_package_builder.upackage import ReferencePath


@contextmanager
def declaration_context(
    path: ReferencePath | Path, location: SourceLocation | None
) -> Generator[None]:
    try:
        yield
    except CompilationError as error:
        if error.context is None:
            error.context = str(path)

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
