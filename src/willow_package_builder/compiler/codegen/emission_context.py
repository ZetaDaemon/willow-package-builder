from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    from willow_package_builder.compiler.build_context import BuildContext
    from willow_package_builder.package_config import PackageConfig
    from willow_package_builder.upackage import Package, ReferencePath


class EmissionContext(Protocol):
    config: PackageConfig
    context: BuildContext

    @property
    def package(self) -> Package: ...

    def class_object_reference(
        self, class_path: str, *, default_object: bool = False
    ) -> ReferencePath: ...

    def ensure_import(
        self, *, name: str, outer: ReferencePath, class_package: str, class_name: str
    ) -> ReferencePath: ...
