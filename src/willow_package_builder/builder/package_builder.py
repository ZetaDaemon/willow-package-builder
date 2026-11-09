from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from willow_package_builder.builder.defaults_builder import DefaultsBuilder
from willow_package_builder.builder.value_builder import ValueBuilder
from willow_package_builder.games import get_game
from willow_package_builder.logging import info
from willow_package_builder.objects.definitions import ObjectDefinition, ObjectDefinitionFlag
from willow_package_builder.package_config import collect_visible_packages
from willow_package_builder.upackage import Package, ReferencePath

from .build_state import PackageBuildState
from .classes.class_builder import ClassBuilder
from .classes.enum_builder import EnumBuilder
from .classes.function_builder import FunctionBuilder
from .classes.property_builder import PropertyBuilder
from .classes.struct_builder import StructBuilder
from .objects.object_builder import ObjectBuilder
from .references import PackageReferences

if TYPE_CHECKING:
    from collections.abc import Iterable

    from willow_package_builder.builder.classes.exports import ClassExport, StructExport
    from willow_package_builder.package_config import PackageConfig

    from .build_context import BuildContext


@dataclass
class PackageBuilder:
    """Package builder class.

    The different parts of building a package are delegated to different classes.
    The classes share a PackageBuildState to track progress.
    """

    context: BuildContext
    config: PackageConfig

    state: PackageBuildState = field(init=False)
    references: PackageReferences = field(init=False)
    properties: PropertyBuilder = field(init=False)
    functions: FunctionBuilder = field(init=False)
    struct_builder: StructBuilder = field(init=False)
    enums: EnumBuilder = field(init=False)
    values: ValueBuilder = field(init=False)
    defaults: DefaultsBuilder = field(init=False)
    object_builder: ObjectBuilder = field(init=False)
    class_builder: ClassBuilder = field(init=False)

    @property
    def package(self) -> Package:
        """Access package from state."""
        return self.state.package

    @property
    def classes(self) -> dict[ReferencePath, ClassExport]:
        """Access classes from state."""
        return self.state.classes

    @property
    def structs(self) -> dict[ReferencePath, StructExport]:
        """Access structs from state."""
        return self.state.structs

    def __post_init__(self) -> None:  # noqa: D105
        game = get_game()
        package = Package(self.config.name, game.package_format(), game.PACKAGE_FLAGS)

        self.state = PackageBuildState(self.context, self.config, package)
        self.references = PackageReferences(self.state)
        self.properties = PropertyBuilder(self.state, self.references)
        self.functions = FunctionBuilder(self.state, self.references, self.properties)
        self.enums = EnumBuilder(self.state, self.references)
        self.struct_builder = StructBuilder(
            self.state, self.references, self.properties, self.enums
        )
        self.values = ValueBuilder(self.state, self.enums, self.struct_builder)
        self.object_builder = ObjectBuilder(
            self.state, self.references, self.struct_builder, self.values
        )
        self.defaults = DefaultsBuilder(
            self.state, self.values, self.struct_builder, self.object_builder
        )
        self.class_builder = ClassBuilder(
            self.state, self.references, self.properties, self.object_builder
        )

    def manifest(self) -> dict[str, object]:
        """Create the package manifest."""
        return {
            "classes": [
                f"{self.config.name}.{exports.class_object.reference()}"
                for exports in self.classes.values()
            ],
            "keep_alive": [
                str(obj.reference())
                for declaration, obj in self.object_builder.exports.items()
                if isinstance(declaration, ObjectDefinition)
                and ObjectDefinitionFlag.KEEP_ALIVE in declaration.flags
            ],
        }

    def prepare_class_defaults(self, class_names: Iterable[ReferencePath]) -> None:
        """Build default records for classes needed by this package."""
        visible = collect_visible_packages(self.config, self.context.packages)

        for name in dict.fromkeys(class_names):
            path, _ = self.context.references.resolve_class(name, self.config.name, visible)
            self.defaults.build_class_defaults(path)

    def compile_classes(self) -> None:
        """Create class definitions, CDOs, fields, and function bytecode exports."""
        self.class_builder.reserve_classes()
        self.class_builder.link_classes()
        self.struct_builder.reserve_structs()
        self.struct_builder.link_structs()
        self.struct_builder.validate_struct_layouts()
        self.enums.build_class_enums()
        self.struct_builder.build_struct_fields()
        self.class_builder.build_class_fields()
        self.functions.build_class_functions()

    def build(self) -> Package:
        """Build custom classes, then load references and construct objects."""
        info(f"Preparing package {self.config.name}")
        self.prepare_class_defaults(self.context.loader.class_names(self.config.name))

        info("Compiling classes")
        self.compile_classes()

        info("Reading objects")
        self.object_builder.read_objects()
        self.object_builder.prepare_definitions()
        declarations = [
            declaration
            for declaration in self.object_builder.definitions
            if isinstance(declaration, ObjectDefinition)
        ]

        self.prepare_class_defaults(declaration.class_name for declaration in declarations)

        info("Constructing objects")
        self.object_builder.construct_objects()
        self.object_builder.link_archetypes()
        self.object_builder.validate_archetype_cycles()
        self.object_builder.build_all_properties()
        self.object_builder.prepare_handlers()

        return self.package
