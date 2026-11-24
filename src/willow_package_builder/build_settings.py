from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import KW_ONLY, dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator


@dataclass(frozen=True)
class BuildSettings:
    """Options shared by the current build."""

    _: KW_ONLY
    debug: bool = False
    silent_console: bool = False
    log_objects: bool = False
    force: bool = False
    re_cache: bool = False


_active_settings: ContextVar[BuildSettings | None] = ContextVar(
    "active_build_settings", default=None
)


def get_build_settings() -> BuildSettings:
    """Return the settings for the current build."""
    settings = _active_settings.get()
    if settings is None:
        msg = "No build settings are active"
        raise RuntimeError(msg)

    return settings


@contextmanager
def select_build_settings(settings: BuildSettings) -> Generator[BuildSettings]:
    """Activate settings for the duration of a build."""
    if _active_settings.get() is not None:
        msg = "Build settings are already active"
        raise RuntimeError(msg)

    token = _active_settings.set(settings)
    try:
        yield settings
    finally:
        _active_settings.reset(token)
