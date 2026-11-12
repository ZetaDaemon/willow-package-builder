from typing import TYPE_CHECKING, Protocol

from willow_package_builder.upackage import FName

if TYPE_CHECKING:
    from willow_package_builder.builder.build_context import BuildContext
    from willow_package_builder.package_config import PackageConfig
    from willow_package_builder.upackage import Package, ReferencePath


class EmissionContext(Protocol):
    @property
    def package(self) -> Package: ...

    @property
    def config(self) -> PackageConfig: ...

    @property
    def context(self) -> BuildContext: ...

    def class_object_reference(
        self, class_path: ReferencePath, *, default_object: bool = False
    ) -> ReferencePath: ...

    def ensure_import(
        self, name: FName, outer: ReferencePath, class_package: FName, class_name: FName
    ) -> ReferencePath: ...

    def function_reference(self, function_path: ReferencePath) -> ReferencePath: ...

    def struct_reference(self, struct_path: ReferencePath) -> ReferencePath: ...
