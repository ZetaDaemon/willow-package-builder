from typing import TYPE_CHECKING

from willow_package_builder.games import get_game

from .classes import CLASS_HANDLERS

if TYPE_CHECKING:
    from collections.abc import Mapping

    from willow_package_builder.compiler.semantics.reference_database import ReferenceDatabase
    from willow_package_builder.games import TargetGame
    from willow_package_builder.handlers.classes.class_handler import ClassHandler
    from willow_package_builder.upackage import ReferencePath


def _build_class_registry() -> dict[tuple[TargetGame | None, ReferencePath], type[ClassHandler]]:
    """Index class handlers and reject conflicting registrations."""
    registry: dict[tuple[TargetGame | None, ReferencePath], type[ClassHandler]] = {}

    for handler in CLASS_HANDLERS:
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


CLASS_HANDLER_REGISTRY = _build_class_registry()


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
