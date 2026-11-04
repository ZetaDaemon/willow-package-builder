from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from willow_package_builder.compiler.syntax.parser import FunctionParser
from willow_package_builder.compiler.syntax.parser.defaults_parser import IndexedArrayDefaults
from willow_package_builder.logging import CompilationError, ValueBuildError
from willow_package_builder.package_config import collect_visible_packages
from willow_package_builder.properties.reference_text import parse_reference_text

from .cache.cache import load_or_parse_class
from .semantics.intrinsics import IMPLICIT_EXPORT_CLASS_PATH
from .semantics.reference_database import PRIMITIVE_TYPES
from .semantics.types import ResolvedType, TypeCategory
from .syntax.declarations import (
    ClassDeclaration,
    FunctionDeclaration,
    OperatorDeclaration,
    TypeReference,
    VariableDeclaration,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from willow_package_builder.package_config import PackageConfig

    from .semantics.reference_database import ReferenceDatabase


@dataclass
class ClassSource:
    config: PackageConfig
    path: Path


@dataclass
class ClassLoader:
    packages: tuple[PackageConfig, ...]
    build_packages: set[Path]
    references: ReferenceDatabase

    sources: dict[str, ClassSource] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        """Index source paths without parsing their contents."""
        for config in self.packages:
            for source_path in config.source_files():
                key = f"{config.name}.{source_path.stem}".casefold()

                if key in self.sources:
                    msg = f"Duplicate class source: {key}"
                    raise CompilationError(msg)

                self.sources[key] = ClassSource(config, source_path)

    def class_names(self, package_name: str) -> tuple[str, ...]:
        """Return indexed class names belonging to a package."""
        package_key = package_name.casefold()

        return tuple(path for path in self.sources if path.partition(".")[0] == package_key)

    def load_classes(
        self, class_names: Iterable[str], current_package: str, visible_packages: set[str]
    ) -> None:
        """Ensure qualified class names have registered declarations."""
        for name in class_names:
            key = self.references.resolve_class_path(
                name, current_package, visible_packages, self.sources, include_intrinsics=True
            )

            if key in self.references.classes:
                continue

            if key in self.references.intrinsics:
                continue

            source = self.sources.get(key)

            if source is None:
                msg = f"No class source found: {name}"
                raise CompilationError(msg)

            cached = load_or_parse_class(
                source.config,
                source.path,
                include_body_tokens=(source.config.directory in self.build_packages),
            )
            declaration = cached.declaration

            if declaration.name.casefold() != source.path.stem.casefold():
                msg = (
                    f"{source.path}: Declared class {declaration.name!r} "
                    "does not match the source filename"
                )
                raise CompilationError(msg)

            self.references.add_class(source.config.name, declaration)

            parent_name = self.references.parent_class_name(key, declaration)

            if parent_name is not None:
                parent_visibility = collect_visible_packages(source.config, self.packages)

                self.load_classes((parent_name,), source.config.name, parent_visibility)

            self._load_declaration_dependencies(key, declaration, source.config)

    def _load_known_class(self, name: str, config: PackageConfig, visible: set[str]) -> bool:
        """Load a name if it identifies an indexed class or an intrinsic."""
        key = name.casefold()
        available = (
            self.sources.keys() | self.references.classes.keys() | self.references.intrinsics.keys()
        )

        if "." in key:
            known = key in available
        else:
            known = any(path.rpartition(".")[2] == key for path in available)

        if not known:
            return False

        self.load_classes((name,), config.name, visible)
        return True

    def _load_type_dependencies(
        self,
        type_ref: TypeReference,
        owner_class: str,
        config: PackageConfig,
        visible: set[str],
        parents: dict[str, str | None],
    ) -> None:
        for argument in type_ref.arguments:
            self._load_type_dependencies(argument, owner_class, config, visible, parents)

        key = type_ref.name.casefold()
        if key in PRIMITIVE_TYPES or key in (TypeCategory.ARRAY.value, TypeCategory.CLASS.value):
            return

        if "." not in key:
            member = self.references.find_member_type(owner_class, type_ref.name, parents)
            if member is not None:
                return
            self._load_known_class(type_ref.name, config, visible)
            return

        if self._load_known_class(type_ref.name, config, visible):
            return

        # Object.Vector and Core.Object.Vector reference a class member type.
        owner_name = type_ref.name.rpartition(".")[0]
        self._load_known_class(owner_name, config, visible)

    def _load_function_body_dependencies(
        self,
        class_path: str,
        function: FunctionDeclaration | OperatorDeclaration,
        config: PackageConfig,
    ) -> None:
        if config.directory not in self.build_packages:
            return

        if function.body_tokens is None:
            return

        parser = FunctionParser.from_tokens(function.body_tokens)

        try:
            variables = parser.parse_local_declarations()
        except CompilationError as error:
            msg = f"{class_path}.{function.name}: {error}"
            raise CompilationError(msg) from error

        visible = collect_visible_packages(config, self.packages)
        parents = self.references.resolve_parent_classes(self.packages)

        for variable in variables:
            self._load_type_dependencies(variable.type_ref, class_path, config, visible, parents)

    def _load_declaration_dependencies(
        self, class_path: str, declaration: ClassDeclaration, config: PackageConfig
    ) -> None:
        visible = collect_visible_packages(config, self.packages)

        if declaration.within is not None:
            self.load_classes((declaration.within,), config.name, visible)

        parents = self.references.resolve_parent_classes(self.packages)
        self.references.inheritance_order(parents)

        for variable in declaration.variables:
            self._load_type_dependencies(variable.type_ref, class_path, config, visible, parents)

        for struct in declaration.structs:
            if struct.parent is not None:
                self._load_type_dependencies(
                    TypeReference(struct.parent), class_path, config, visible, parents
                )
            for variable in struct.variables:
                self._load_type_dependencies(
                    variable.type_ref, class_path, config, visible, parents
                )

        for function in (*declaration.functions, *declaration.operators):
            if function.return_type is not None:
                self._load_type_dependencies(
                    function.return_type, class_path, config, visible, parents
                )
            for parameter in function.parameters:
                self._load_type_dependencies(
                    parameter.type_ref, class_path, config, visible, parents
                )
            self._load_function_body_dependencies(class_path, function, config)

        self._load_default_dependencies(declaration.parsed_defaults, class_path, config)
        for struct in declaration.structs:
            self._load_default_dependencies(
                struct.parsed_defaults, class_path, config, f"{class_path}.{struct.name}"
            )

    def _load_default_dependencies(
        self,
        properties: dict[str, object],
        owner_class: str,
        config: PackageConfig,
        struct_path: str | None = None,
    ) -> None:
        visible = collect_visible_packages(config, self.packages)

        for name, raw_value in properties.items():
            parents = self.references.resolve_parent_classes(self.packages)
            if struct_path is None:
                member = self.references.resolve_variable(owner_class, name, parents)
            else:
                member = self.references.resolve_struct_variable(
                    struct_path, name, parents, visible
                )

            field_config = next(
                package
                for package in self.packages
                if package.name.casefold() == member.owner_class.partition(".")[0]
            )
            field_visible = collect_visible_packages(field_config, self.packages)
            definition = member.declaration
            self._load_type_dependencies(
                definition.type_ref, member.owner_class, field_config, field_visible, parents
            )
            parents = self.references.resolve_parent_classes(self.packages)
            resolved = self.references.resolve_type(
                definition.type_ref, member.owner_class, field_visible, parents
            )

            self._load_field_default_dependencies(definition, resolved, raw_value, config)

    def _load_default_value_dependencies(
        self, value: object, resolved: ResolvedType, config: PackageConfig
    ) -> None:
        match resolved.category:
            case TypeCategory.ARRAY:
                if isinstance(value, list):
                    for element in cast("list[object]", value):
                        self._load_default_value_dependencies(
                            element, resolved.arguments[0], config
                        )

            case TypeCategory.STRUCT:
                if isinstance(value, dict):
                    if not all(isinstance(name, str) for name in value):
                        msg = "Default struct field names must be strings"
                        raise CompilationError(msg)

                    path = resolved.declaration_path
                    if path is None:
                        msg = "Resolved struct has no declaration path"
                        raise ValueError(msg)

                    self._load_default_dependencies(
                        cast("dict[str, object]", value), path.rpartition(".")[0], config, path
                    )

            case TypeCategory.OBJECT | TypeCategory.CLASS:
                if not isinstance(value, str):
                    return

                context = f"Default reference in {config.name}"
                try:
                    annotation, path = parse_reference_text(context, value)
                except ValueBuildError as error:
                    msg = str(error)
                    raise CompilationError(msg) from error

                visible = collect_visible_packages(config, self.packages)
                is_class_reference = resolved.category is TypeCategory.CLASS

                if annotation is not None:
                    self.load_classes((annotation,), config.name, visible)
                    annotation_path = self.references.resolve_class_path(
                        annotation, config.name, visible, include_intrinsics=True
                    )
                    parents = self.references.resolve_parent_classes(self.packages)
                    is_class_reference |= self.references.is_subclass(
                        annotation_path, IMPLICIT_EXPORT_CLASS_PATH, parents
                    )

                if is_class_reference:
                    self.load_classes((path,), config.name, visible)

            case _:
                pass

    def load_property_dependencies(
        self, class_path: str, properties: dict[str, object], current_package: str
    ) -> None:
        """Load classes referenced by supplied property values."""
        config = next(
            config
            for config in self.packages
            if config.name.casefold() == current_package.casefold()
        )

        self._load_default_dependencies(properties, class_path, config)

    def _load_field_default_dependencies(
        self,
        definition: VariableDeclaration,
        resolved: ResolvedType,
        raw_value: object,
        config: PackageConfig,
    ) -> None:
        if isinstance(raw_value, IndexedArrayDefaults):
            if raw_value.has_initial:
                self._load_field_default_dependencies(
                    definition, resolved, raw_value.initial, config
                )

            if definition.array_dimension == 1:
                if resolved.category is not TypeCategory.ARRAY:
                    return
                element_type = resolved.arguments[0]
            else:
                element_type = resolved

            for _, element in raw_value.updates:
                self._load_default_value_dependencies(element, element_type, config)
            return

        if definition.array_dimension == 1:
            self._load_default_value_dependencies(raw_value, resolved, config)
        elif isinstance(raw_value, list):
            for element in cast("list[object]", raw_value):
                self._load_default_value_dependencies(element, resolved, config)
        else:
            # UC may assign element zero of a fixed array without an index.
            self._load_default_value_dependencies(raw_value, resolved, config)
