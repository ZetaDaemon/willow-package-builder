import sys
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from inspect import isabstract
from typing import TYPE_CHECKING

from willow_package_builder.games import get_game
from willow_package_builder.handlers.classes.class_handler import ClassHandler
from willow_package_builder.logging import CompilationError
from willow_package_builder.package_config import PackageConfig

from .classes import CLASS_HANDLERS

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path

    from willow_package_builder.compiler.semantics.reference_database import ReferenceDatabase
    from willow_package_builder.games import TargetGame
    from willow_package_builder.upackage import ReferencePath


def _build_class_registry(
    handlers: Iterable[type[ClassHandler]],
) -> dict[tuple[TargetGame | None, ReferencePath], type[ClassHandler]]:
    """Index class handlers and reject conflicting registrations."""
    registry: dict[tuple[TargetGame | None, ReferencePath], type[ClassHandler]] = {}

    for handler in handlers:
        key = (handler.GAME, handler.CLASS_PATH)
        existing = registry.get(key)

        if existing is not None:
            msg = (
                f"Handlers {existing.__name__} and {handler.__name__} "
                f"both target {handler.CLASS_PATH} for game {handler.GAME}"
            )
            raise ValueError(msg)

        overlap = handler.EXTRA_FIELDS.keys() & handler.HANDLED_PROPERTIES

        if overlap:
            names = ", ".join(sorted(str(name) for name in overlap))
            msg = (
                f"{handler.__name__} declares fields as both extra fields "
                f"and handled properties: {names}"
            )
            raise ValueError(msg)

        registry[key] = handler

    return registry


CLASS_HANDLER_REGISTRY = _build_class_registry(CLASS_HANDLERS)


def configure_class_handlers(packages: Iterable[PackageConfig]) -> None:
    """Register built-in handlers and handlers supplied by build packages."""
    handlers = list(CLASS_HANDLERS)
    for config in packages:
        handlers.extend(load_package_handlers(config.directory))

    registry = _build_class_registry(handlers)
    CLASS_HANDLER_REGISTRY.clear()
    CLASS_HANDLER_REGISTRY.update(registry)


def get_class_handler(
    class_path: ReferencePath,
    references: ReferenceDatabase,
    parents: Mapping[ReferencePath, ReferencePath | None],
) -> type[ClassHandler] | None:
    """Find the nearest applicable handler in the class hierarchy."""
    target = get_game().TARGET

    for path, _ in references.iter_class_hierarchy(class_path, parents):
        handler = CLASS_HANDLER_REGISTRY.get((target, path))

        if handler is None:
            handler = CLASS_HANDLER_REGISTRY.get((None, path))

        if handler is not None:
            return handler

    return None


def load_package_handlers(directory: Path) -> tuple[type[ClassHandler], ...]:
    """Load handlers exported by a package's Handlers module."""
    handler_directory = directory / "Handlers"
    initializer = handler_directory / "__init__.py"
    if not initializer.is_file():
        return ()

    module_name = "_wpb_handlers_" + sha256(str(directory.resolve()).encode("utf-8")).hexdigest()
    spec = spec_from_file_location(
        module_name, initializer, submodule_search_locations=[str(handler_directory)]
    )
    if spec is None or spec.loader is None:
        msg = f"Cannot load handlers from {initializer}"
        raise CompilationError(msg)

    module = module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
    except Exception as error:
        msg = f"Failed to load {initializer}: {error}"
        raise CompilationError(msg) from error

    handlers = getattr(module, "CLASS_HANDLERS", ())
    if not isinstance(handlers, tuple):
        msg = f"{initializer}: CLASS_HANDLERS must be a tuple"
        raise CompilationError(msg)

    for handler in handlers:
        if (
            not isinstance(handler, type)
            or not issubclass(handler, ClassHandler)
            or isabstract(handler)  # pyright: ignore[reportUnknownArgumentType]
        ):
            msg = f"{initializer}: {handler!r} must be a concrete ClassHandler subclass"
            raise CompilationError(msg)

    return handlers
