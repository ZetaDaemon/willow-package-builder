from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterable


class ClassLoading(Protocol):
    """Class-loading operations required by the build pipeline."""

    def class_names(self, package_name: str) -> tuple[str, ...]: ...

    def load_classes(
        self, class_names: Iterable[str], current_package: str, visible_packages: set[str]
    ) -> None: ...

    def load_property_dependencies(
        self, class_path: str, properties: dict[str, object], current_package: str
    ) -> None: ...
