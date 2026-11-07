from collections import deque
from dataclasses import dataclass, field
from time import perf_counter
from typing import TYPE_CHECKING, cast

from willow_package_builder.compiler.source import decode_source
from willow_package_builder.compiler.syntax.keyword import ScriptKeywords
from willow_package_builder.compiler.syntax.lexer import Lexer, TokenCategory
from willow_package_builder.compiler.syntax.modifiers import StructModifier
from willow_package_builder.compiler.syntax.parser import FunctionParser
from willow_package_builder.compiler.syntax.parser.defaults_parser import IndexedArrayDefaults
from willow_package_builder.compiler.syntax.punctuation import Punctuation
from willow_package_builder.logging import (
    CompilationError,
    UnknownPropertyError,
    ValueBuildError,
    WarningCode,
    declaration_context,
    info,
    warn,
)
from willow_package_builder.package_config import collect_visible_packages
from willow_package_builder.properties.reference_text import parse_reference_text
from willow_package_builder.upackage import FName, ReferencePath

from .cache.cache import load_or_parse_class
from .semantics.intrinsics import IMPLICIT_EXPORT_CLASS_PATH
from .semantics.reference_database import (
    ARRAY_TYPE,
    CLASS_TYPE,
    DELEGATE_TYPE,
    MAP_TYPE,
    PRIMITIVE_TYPES,
)
from .semantics.types import ResolvedType, TypeCategory
from .syntax.declarations import (
    ClassDeclaration,
    FunctionDeclaration,
    OperatorDeclaration,
    ParameterDeclaration,
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

    sources: dict[ReferencePath, ClassSource] = field(default_factory=dict, init=False, repr=False)
    _member_type_sources: dict[FName, list[ReferencePath]] = field(
        default_factory=dict, init=False, repr=False
    )
    _indexed_member_packages: set[FName] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self) -> None:
        """Index source paths without parsing their contents."""
        for config in self.packages:
            for source_path in config.source_files():
                key = ReferencePath(f"{config.name}.{source_path.stem}")

                if key in self.sources:
                    msg = f"Duplicate class source: {key}"
                    raise CompilationError(msg)

                self.sources[key] = ClassSource(config, source_path)

    def class_names(self, package_name: FName) -> tuple[ReferencePath, ...]:
        """Return indexed class names belonging to a package."""
        return tuple(path for path in self.sources if path.get_outer().name == package_name)

    def load_classes(
        self,
        class_names: Iterable[ReferencePath],
        current_package: FName,
        visible_packages: set[FName],
    ) -> None:
        """Validate class names against the prepared declaration registry."""
        for name in class_names:
            self.references.resolve_class_path(
                name, current_package, visible_packages, include_intrinsics=True
            )

    def _load_known_class(
        self, name: ReferencePath, config: PackageConfig, visible: set[FName]
    ) -> bool:
        """Load a name if it identifies an indexed class or an intrinsic."""
        available = (
            self.sources.keys() | self.references.classes.keys() | self.references.intrinsics.keys()
        )

        if name.outer is not None:
            known = name in available
        else:
            known = any(path.name == name.name for path in available)

        if not known:
            return False

        self.load_classes((name,), config.name, visible)
        return True

    def _load_type_dependencies(
        self,
        type_ref: TypeReference,
        owner_class: ReferencePath,
        config: PackageConfig,
        visible: set[FName],
        parents: dict[ReferencePath, ReferencePath | None],
    ) -> None:
        key = type_ref.name

        if key == MAP_TYPE:
            return

        if key == DELEGATE_TYPE:
            if len(type_ref.arguments) == 1:
                signature = type_ref.arguments[0]
                owner_name = signature.name.outer

                if owner_name:
                    self._load_known_class(owner_name, config, visible)

            return

        for argument in type_ref.arguments:
            self._load_type_dependencies(argument, owner_class, config, visible, parents)

        if key in PRIMITIVE_TYPES or key in (ARRAY_TYPE, CLASS_TYPE):
            return

        if key.outer is None:
            member = self.references.find_member_type(owner_class, type_ref.name.name, parents)

            if member is not None:
                return

            if self._load_known_member_type(type_ref.name.name, config, visible):
                return

            self._load_known_class(type_ref.name, config, visible)
            return

        if self._load_known_class(type_ref.name, config, visible):
            return

        # Object.Vector and Core.Object.Vector reference a class member type.
        owner_name = type_ref.name.get_outer()
        self._load_known_class(owner_name, config, visible)

    def _load_function_body_dependencies(
        self,
        class_path: ReferencePath,
        function: FunctionDeclaration | OperatorDeclaration,
        config: PackageConfig,
    ) -> None:
        if config.directory not in self.build_packages:
            return

        if function.body_tokens is None:
            return

        owner = class_path
        function_path = owner + function.fname

        with declaration_context(function_path, function.location):
            parser = FunctionParser.from_tokens(function.body_tokens)
            variables = parser.parse_local_declarations()

            visible = collect_visible_packages(config, self.packages)
            parents = self.references.resolve_parent_classes(self.packages)

            for variable in variables:
                variable_path = function_path + variable.name

                with declaration_context(variable_path, variable.location):
                    self._load_dimension_dependencies(variable, class_path, config, visible)
                    self._load_type_dependencies(
                        variable.type_ref, class_path, config, visible, parents
                    )

    def _load_declaration_dependencies(
        self, class_path: ReferencePath, declaration: ClassDeclaration, config: PackageConfig
    ) -> None:
        visible = collect_visible_packages(config, self.packages)

        if declaration.within is not None:
            with declaration_context(class_path, declaration.location):
                self.load_classes((declaration.within,), config.name, visible)

        parents = self.references.resolve_parent_classes(self.packages)
        self.references.inheritance_order(parents)

        for variable in declaration.variables:
            path = class_path + variable.name

            with declaration_context(path, variable.location):
                self._load_dimension_dependencies(variable, class_path, config, visible)
                self._load_type_dependencies(
                    variable.type_ref, class_path, config, visible, parents
                )

        for struct in declaration.structs:
            struct_path = class_path + struct.name

            with declaration_context(struct_path, struct.location):
                if struct.parent is not None:
                    self._load_type_dependencies(
                        TypeReference(struct.parent), class_path, config, visible, parents
                    )

                for variable in struct.variables:
                    path = struct_path + variable.name

                    with declaration_context(path, variable.location):
                        self._load_dimension_dependencies(variable, class_path, config, visible)
                        self._load_type_dependencies(
                            variable.type_ref, class_path, config, visible, parents
                        )

        for function in (*declaration.functions, *declaration.operators):
            function_path = class_path + function.fname

            with declaration_context(function_path, function.location):
                if function.return_type is not None:
                    self._load_type_dependencies(
                        function.return_type, class_path, config, visible, parents
                    )

                for parameter in function.parameters:
                    parameter_path = function_path + parameter.name

                    with declaration_context(parameter_path, parameter.location):
                        self._load_dimension_dependencies(parameter, class_path, config, visible)
                        self._load_type_dependencies(
                            parameter.type_ref, class_path, config, visible, parents
                        )

                self._load_function_body_dependencies(class_path, function, config)

    def _load_default_dependencies(
        self,
        properties: dict[FName, object],
        owner_class: ReferencePath,
        config: PackageConfig,
        struct_path: ReferencePath | None = None,
    ) -> None:
        visible = collect_visible_packages(config, self.packages)

        for name, raw_value in tuple(properties.items()):
            parents = self.references.resolve_parent_classes(self.packages)

            try:
                if struct_path is None:
                    member = self.references.resolve_variable(owner_class, name, parents)
                else:
                    member = self.references.resolve_struct_variable(
                        struct_path, name, parents, visible
                    )
            except UnknownPropertyError as error:
                if config.directory in self.build_packages:
                    raise

                display_path = owner_class if struct_path is None else struct_path

                msg = f"{display_path}: Skipped default for {name!r}: {error}"
                warn(WarningCode.INVALID_REFERENCE_DEFAULT, msg)

                del properties[name]
                continue

            field_config = next(
                package
                for package in self.packages
                if package.name == member.owner_class.get_outer().name
            )
            field_visible = collect_visible_packages(field_config, self.packages)
            definition = member.declaration

            owner = member.owner_class if struct_path is None else struct_path

            path = owner + definition.name

            with declaration_context(path, definition.location):
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
                    if not all(isinstance(name, (str, FName)) for name in value):
                        msg = "Default struct field names must be strings or FNames"
                        raise CompilationError(msg)

                    raw_properties = cast("dict[str|FName, object]", value)
                    properties: dict[FName, object] = {}
                    for raw_key, raw_value in raw_properties.items():
                        key = FName(raw_key) if isinstance(raw_key, str) else raw_key

                        if key in properties:
                            msg = f"Duplicate property {key}"
                            raise CompilationError(msg)

                        properties[key] = raw_value

                    path = resolved.declaration_path
                    if path is None:
                        msg = "Resolved struct has no declaration path"
                        raise ValueError(msg)

                    self._load_default_dependencies(properties, path.get_outer(), config, path)
                    value.clear()
                    value.update(properties)  # pyright: ignore[reportUnknownMemberType]

            case TypeCategory.OBJECT | TypeCategory.CLASS:
                if not isinstance(value, str):
                    return

                context = f"Default reference in {config.name}"
                try:
                    annotation, path = parse_reference_text(context, value, None)
                except ValueBuildError as error:
                    msg = str(error)
                    raise CompilationError(msg) from error

                visible = collect_visible_packages(config, self.packages)
                is_class_reference = resolved.category is TypeCategory.CLASS

                if annotation is not None:
                    annotation_path = self.references.resolve_class_path(
                        annotation, config.name, visible, self.sources, include_intrinsics=True
                    )
                    self.load_classes((annotation_path,), config.name, visible)

                    if (
                        annotation_path not in self.references.classes
                        and annotation_path not in self.references.intrinsics
                    ):
                        return

                    parents = self.references.resolve_parent_classes(self.packages)
                    is_class_reference |= self.references.is_subclass(
                        annotation_path, IMPLICIT_EXPORT_CLASS_PATH, parents
                    )

                if is_class_reference:
                    self.load_classes((path,), config.name, visible)

            case _:
                pass

    def load_property_dependencies(
        self, class_path: ReferencePath, properties: dict[FName, object], current_package: FName
    ) -> None:
        """Load classes referenced by supplied property values."""
        config = next(config for config in self.packages if config.name == current_package)

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

    def index_member_types(self, package_name: FName) -> None:
        """Index struct and enum owners in a package without parsing classes."""
        if package_name in self._indexed_member_packages:
            return

        discovered: dict[ReferencePath, list[ReferencePath]] = {}

        for owner, source in self.sources.items():
            if owner.get_outer().name != package_name:
                continue

            source_text = decode_source(source.path.read_bytes(), source.path)
            tokens = Lexer(source_text).tokenize()
            depth = 0

            for index, token in enumerate(tokens):
                if token.category is TokenCategory.SYMBOL:
                    if token == Punctuation.LEFT_BRACE:
                        depth += 1
                    elif token == Punctuation.RIGHT_BRACE:
                        depth -= 1

                if depth or token.category is not TokenCategory.IDENTIFIER:
                    continue

                keyword = token.keyword

                if keyword not in (ScriptKeywords.STRUCT, ScriptKeywords.ENUM):
                    continue

                position = index + 1

                if keyword == ScriptKeywords.STRUCT:
                    while tokens[position].keyword in StructModifier:
                        position += 1

                name = tokens[position]

                if name.category is not TokenCategory.IDENTIFIER:
                    msg = f"{source.path}: Expected {keyword} name at {name.line}:{name.column}"
                    raise CompilationError(msg)

                owners = discovered.setdefault(ReferencePath(name.fname), [])

                if owner not in owners:
                    owners.append(owner)

        for name, owners in discovered.items():
            self._member_type_sources.setdefault(name.name, []).extend(owners)

        self._indexed_member_packages.add(package_name)

    def _load_known_member_type(
        self, name: FName, config: PackageConfig, visible: set[FName]
    ) -> bool:
        """Find an unqualified struct or enum and load its declaring class."""
        package_key = config.name
        allowed = {package_key, *(package for package in visible)}

        for package in sorted(allowed):
            self.index_member_types(package)

        candidates = [
            owner
            for owner in self._member_type_sources.get(name, ())
            if owner.get_outer().name in allowed
        ]

        local = [owner for owner in candidates if owner.get_outer().name == package_key]
        candidates = local or candidates

        if not candidates:
            return False

        if len(candidates) > 1:
            paths = ", ".join(str(owner + name) for owner in candidates)
            msg = f"Ambiguous struct or enum {name!r}: {paths}"
            raise CompilationError(msg)

        self.load_classes((candidates[0],), config.name, visible)
        return True

    def _load_dimension_dependencies(
        self,
        declaration: VariableDeclaration | ParameterDeclaration,
        owner_class: ReferencePath,
        config: PackageConfig,
        visible: set[FName],
    ) -> None:
        name = declaration.array_dimension_name

        if name is None:
            return

        parents = self.references.resolve_parent_classes(self.packages)
        self._load_type_dependencies(TypeReference(name), owner_class, config, visible, parents)

    def _resolve_declaration_dimension(
        self,
        declaration: VariableDeclaration | ParameterDeclaration,
        owner_class: ReferencePath,
        visible: set[FName],
        parents: dict[ReferencePath, ReferencePath | None],
    ) -> None:
        name = declaration.array_dimension_name

        if name is None:
            return

        declaration.array_dimension = self.references.resolve_array_dimension(
            name, owner_class, visible, parents
        )

    def _load_class_declaration(self, key: ReferencePath) -> ClassDeclaration | None:
        """Parse and register one class without traversing dependencies."""
        if key in self.references.classes or key in self.references.intrinsics:
            return None

        source = self.sources.get(key)

        if source is None:
            msg = f"No class source found: {key}"
            raise CompilationError(msg)

        with declaration_context(source.path, None):
            cached = load_or_parse_class(
                source.config,
                source.path,
                include_body_tokens=source.config.directory in self.build_packages,
            )
        declaration = cached.declaration

        if declaration.name != FName(source.path.stem):
            msg = (
                f"{source.path}: Declared class {declaration.name!r} "
                "does not match the source filename"
            )
            raise CompilationError(msg)

        self.references.add_class(source.config.name, declaration)

        if source.config.directory not in self.build_packages:
            class_path = f"{source.config.name}.{declaration.name}"

            for definition in (declaration, *declaration.structs):
                if definition.default_parse_error is None:
                    continue

                display_path = class_path

                if definition is not declaration:
                    display_path = f"{class_path}.{definition.name}"

                msg = (
                    f"{source.path}: {display_path}: "
                    "Skipped invalid default block: "
                    f"{definition.default_parse_error}"
                )
                warn(WarningCode.INVALID_REFERENCE_DEFAULT, msg)

        return declaration

    def _load_declared_default_dependencies(
        self, class_path: ReferencePath, declaration: ClassDeclaration, config: PackageConfig
    ) -> None:
        """Discover dependencies referenced by class and struct defaults."""
        self._load_default_dependencies(declaration.parsed_defaults, class_path, config)

        for struct in declaration.structs:
            self._load_default_dependencies(
                struct.parsed_defaults, class_path, config, class_path + struct.name
            )

    def _resolve_declaration_dimensions(
        self, class_path: ReferencePath, declaration: ClassDeclaration, config: PackageConfig
    ) -> None:
        owner = class_path
        visible = collect_visible_packages(config, self.packages)
        parents = self.references.resolve_parent_classes(self.packages)

        targets: list[tuple[ReferencePath, VariableDeclaration | ParameterDeclaration]] = [
            (owner + variable.name, variable) for variable in declaration.variables
        ]

        for struct in declaration.structs:
            targets.extend(
                (owner + struct.name + variable.name, variable) for variable in struct.variables
            )

        for function in (*declaration.functions, *declaration.operators):
            targets.extend(
                (owner + function.fname + parameter.name, parameter)
                for parameter in function.parameters
            )

        for path, target in targets:
            with declaration_context(path, target.location):
                self._resolve_declaration_dimension(target, class_path, visible, parents)

    def load_declarations(self) -> None:
        """Load all configured declarations in package dependency order."""
        for config in self.packages:
            reference_only = config.directory not in self.build_packages
            category = "reference package" if reference_only else "package"
            info(f"Loading declarations for {category} {config.name}")

            start = perf_counter()
            count = 0

            for key in sorted((self.class_names(config.name))):
                if self._load_class_declaration(key) is not None:
                    count += 1

            elapsed = perf_counter() - start
            info(f"Loaded {count} class declarations from {config.name} in {elapsed:.3f}s")

    def resolve_dimensions(self, class_order: Iterable[ReferencePath]) -> None:
        """Resolve named dimensions after all declarations are registered."""
        info("Resolving named array dimensions")
        start = perf_counter()

        for key in class_order:
            self._resolve_declaration_dimensions(
                key, self.references.classes[key], self.sources[key].config
            )

        info(f"Resolved named array dimensions in {perf_counter() - start:.3f}s")
