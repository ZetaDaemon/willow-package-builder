from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterable

    from willow_package_builder.upackage import FName, ReferencePath


class ClassLoading(Protocol):
    """Class-loading operations required by the build pipeline."""

    def class_names(self, package_name: FName) -> tuple[ReferencePath, ...]: ...

    def load_classes(
        self,
        class_names: Iterable[ReferencePath],
        current_package: FName,
        visible_packages: set[FName],
    ) -> None: ...

    def load_property_dependencies(
        self, class_path: ReferencePath, properties: dict[FName, object], current_package: FName
    ) -> None: ...
